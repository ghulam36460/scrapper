from __future__ import annotations

import importlib.util
import re
from difflib import SequenceMatcher
from urllib.parse import urlparse

from asagus.models import EnrichedRecord, ExtractedRecord


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
EU_COUNTRIES = {"AT", "BE", "DE", "DK", "ES", "FI", "FR", "IE", "IT", "NL", "PL", "PT", "SE"}
PDPA_COUNTRIES = {"PK", "SG", "TH", "MY", "PH"}


class EnrichmentLayer:
    """Layer 5 validation, GLiNER-ready NER, geo/category and dedupe signals."""

    async def enrich(self, record: ExtractedRecord, default_city: str = "") -> EnrichedRecord:
        phone = self._normalize_phone(record.phone or record.whatsapp)
        country_code = record.country_code or self._country_from_phone(phone)
        city = record.city or default_city
        category = record.category or self._zero_shot_category(record)
        entities = self._extract_entities(record)
        email_verified, mx_checked = self._verify_email(record.email, allow_dns=bool(record.raw_fields.get("mx_lookup_enabled")))
        website_alive = bool(record.website_url and urlparse(record.website_url).netloc)
        whatsapp_valid = self._validate_whatsapp(record.whatsapp or phone)
        completeness = self._completeness(record, phone, category, city)
        tags = sorted({token for token in [category, city, country_code, *entities.get("organization", [])] if token})

        data = record.model_dump()
        data.update(
            {
                "phone": phone or record.phone,
                "phone_valid": bool(phone),
                "whatsapp_valid": whatsapp_valid,
                "city": city,
                "country_code": country_code,
                "category": category,
                "email_verified": email_verified,
                "email_mx_checked": mx_checked,
                "website_alive": website_alive,
                "record_completeness": completeness,
                "gdpr_flag": country_code in EU_COUNTRIES,
                "pdpa_flag": country_code in PDPA_COUNTRIES,
                "entity_tags": tags,
                "ner_entities": entities,
                "raw_fields": {
                    **record.raw_fields,
                    "dedupe_weights": {
                        "phone": 0.95,
                        "email_domain": 0.80,
                        "name_fuzzy_with_address": 0.70,
                        "geo_proximity_with_name": 0.85,
                        "website_domain": 0.95,
                        "google_maps_cid": 1.0,
                    },
                    "gliner_available": importlib.util.find_spec("gliner") is not None,
                },
            }
        )
        return EnrichedRecord.model_validate(data)

    def dedupe_score(self, left: EnrichedRecord, right: EnrichedRecord) -> tuple[float, list[str]]:
        scores: list[float] = []
        reasons: list[str] = []

        if left.phone and right.phone and left.phone == right.phone:
            scores.append(0.95)
            reasons.append("phone_exact")
        if left.website_url and right.website_url and self._domain(left.website_url) == self._domain(right.website_url):
            scores.append(0.95)
            reasons.append("website_domain")
        if left.email and right.email and self._email_domain(left.email) == self._email_domain(right.email):
            scores.append(0.80)
            reasons.append("email_domain")
        if left.name and right.name:
            name_similarity = SequenceMatcher(None, left.name.lower(), right.name.lower()).ratio()
            address_similarity = SequenceMatcher(None, left.address.lower(), right.address.lower()).ratio() if left.address and right.address else 0
            if name_similarity >= 0.82 and address_similarity >= 0.45:
                scores.append(0.70)
                reasons.append("name_fuzzy_with_address")
        if left.raw_fields.get("google_maps_cid") and left.raw_fields.get("google_maps_cid") == right.raw_fields.get("google_maps_cid"):
            scores.append(1.0)
            reasons.append("google_maps_cid")

        if not scores:
            return 0.0, []
        return round(max(scores), 3), reasons

    def _normalize_phone(self, value: str) -> str:
        for chunk in re.findall(r"(?:\+|00)?\d[\d\s().-]{7,}\d", value or ""):
            digits = re.sub(r"\D+", "", chunk)
            if not digits:
                continue
            if digits.startswith("00"):
                digits = digits[2:]
            if not digits.startswith("92") and len(digits) == 10 and digits.startswith("3"):
                digits = "92" + digits
            if 8 <= len(digits) <= 16:
                return f"+{digits}"
        return ""

    def _country_from_phone(self, phone: str) -> str:
        if phone.startswith("+92"):
            return "PK"
        if phone.startswith("+1"):
            return "US"
        if phone.startswith("+44"):
            return "GB"
        if phone.startswith("+971"):
            return "AE"
        if phone.startswith("+966"):
            return "SA"
        return ""

    def _verify_email(self, email: str, allow_dns: bool = False) -> tuple[bool, bool]:
        if not email or not EMAIL_RE.match(email):
            return False, False
        if not allow_dns:
            return True, False
        try:
            import dns.resolver  # type: ignore

            answers = dns.resolver.resolve(self._email_domain(email), "MX", lifetime=3)
            return bool(answers), True
        except Exception:
            return False, True

    def _validate_whatsapp(self, value: str) -> bool:
        digits = re.sub(r"\D+", "", value or "")
        return 8 <= len(digits) <= 16

    def _zero_shot_category(self, record: ExtractedRecord) -> str:
        text = " ".join(
            [
                record.name,
                record.address,
                record.website_url,
                str(record.raw_fields.get("meta_description", "")),
            ]
        ).lower()
        labels = {
            "restaurant": ["restaurant", "food", "cafe", "menu", "dining", "burger"],
            "clinic": ["clinic", "dentist", "doctor", "health", "medical", "skin"],
            "real estate": ["real estate", "property", "plots", "realtor", "agency"],
            "auto repair": ["auto", "repair", "mechanic", "garage", "vehicle"],
            "wedding venue": ["wedding", "banquet", "hall", "marquee", "venue"],
            "retail": ["shop", "store", "retail", "market"],
        }
        for label, markers in labels.items():
            if any(marker in text for marker in markers):
                return label
        return ""

    def _extract_entities(self, record: ExtractedRecord) -> dict[str, list[str]]:
        text = " ".join([record.name, record.address, record.city, record.category])
        entities: dict[str, list[str]] = {"organization": [], "location": [], "service": []}
        if record.name:
            entities["organization"].append(record.name)
        if record.city:
            entities["location"].append(record.city)
        if record.category:
            entities["service"].append(record.category)
        if "gliner_entities" in record.raw_fields and isinstance(record.raw_fields["gliner_entities"], dict):
            for key, values in record.raw_fields["gliner_entities"].items():
                if isinstance(values, list):
                    entities.setdefault(str(key), []).extend(str(value) for value in values)
        return {key: sorted(set(values)) for key, values in entities.items() if values or key in text}

    def _completeness(self, record: ExtractedRecord, phone: str, category: str, city: str) -> float:
        fields = [
            record.name,
            record.email,
            phone or record.phone,
            record.whatsapp,
            record.website_url,
            record.facebook_url,
            record.instagram_url,
            record.twitter_url,
            record.linkedin_url,
            record.address,
            city,
            category,
        ]
        return round(sum(1 for field in fields if field) / len(fields), 2)

    def _domain(self, url: str) -> str:
        return urlparse(url if "://" in url else f"https://{url}").netloc.lower().removeprefix("www.")

    def _email_domain(self, email: str) -> str:
        return email.split("@")[-1].lower() if "@" in email else ""
