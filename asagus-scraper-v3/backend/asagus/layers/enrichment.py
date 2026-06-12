from __future__ import annotations

import importlib.util
import re
from difflib import SequenceMatcher
from urllib.parse import urlparse

import httpx

from asagus.layers.lead_intelligence import whatsapp_link
from asagus.layers.outreach_intelligence import outreach_profile_for
from asagus.models import EnrichedRecord, ExtractedRecord


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
EU_COUNTRIES = {"AT", "BE", "DE", "DK", "ES", "FI", "FR", "IE", "IT", "NL", "PL", "PT", "SE"}
PDPA_COUNTRIES = {"PK", "SG", "TH", "MY", "PH"}
GENERIC_EMAIL_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "live.com",
    "icloud.com",
    "aol.com",
    "proton.me",
    "protonmail.com",
}


class EnrichmentLayer:
    """Layer 5 validation, GLiNER-ready NER, geo/category and dedupe signals."""

    def __init__(self, google_geocoding_api_key: str = "") -> None:
        self.google_geocoding_api_key = google_geocoding_api_key

    async def enrich(self, record: ExtractedRecord, default_city: str = "") -> EnrichedRecord:
        phone = self._normalize_phone(record.phone or record.whatsapp)
        country_code = record.country_code or self._country_from_phone(phone)
        city = record.city or default_city
        category = record.category or self._zero_shot_category(record)
        entities = self._extract_entities(record)
        email_verified, mx_checked = self._verify_email(record.email, allow_dns=bool(record.raw_fields.get("mx_lookup_enabled")))
        website_alive = bool(record.website_url and urlparse(record.website_url).netloc)
        existing_lat = getattr(record, "lat", None)
        existing_lng = getattr(record, "lng", None)
        lat, lng, geocoding_status = await self._geocode_if_configured(record, city, country_code, existing_lat, existing_lng)
        whatsapp_candidate = record.whatsapp or phone
        wa_link = whatsapp_link(whatsapp_candidate)
        whatsapp_status = "provided" if record.whatsapp else "candidate_from_phone" if wa_link else "missing"
        whatsapp_valid = bool(wa_link)
        completeness = self._completeness(record, phone, category, city)
        tags = sorted({token for token in [category, city, country_code, *entities.get("organization", [])] if token})
        outreach_record = record.model_copy(
            update={
                "phone": phone or record.phone,
                "whatsapp": record.whatsapp or (phone if wa_link else ""),
                "city": city,
                "country_code": country_code,
                "category": category,
            }
        )
        outreach_profile = outreach_profile_for(outreach_record)

        data = record.model_dump()
        data.update(
            {
                "phone": phone or record.phone,
                "whatsapp": record.whatsapp or (phone if wa_link else ""),
                "phone_valid": bool(phone),
                "whatsapp_valid": whatsapp_valid,
                "city": city,
                "country_code": country_code,
                "category": category,
                "email_verified": email_verified,
                "email_mx_checked": mx_checked,
                "website_alive": website_alive,
                "lat": lat,
                "lng": lng,
                "record_completeness": completeness,
                "gdpr_flag": country_code in EU_COUNTRIES,
                "pdpa_flag": country_code in PDPA_COUNTRIES,
                "entity_tags": tags,
                "ner_entities": entities,
                "raw_fields": {
                    **record.raw_fields,
                    "wa_link": wa_link,
                    "whatsapp_status": whatsapp_status,
                    "whatsapp_normalized": wa_link.rsplit("/", 1)[-1] if wa_link else "",
                    "outreach_profile": outreach_profile,
                    "outreach_fit_score": outreach_profile["score"],
                    "outreach_segment": outreach_profile["segment"],
                    "outreach_niche": outreach_profile["niche"],
                    "recommended_outreach_channel": outreach_profile["recommended_channel"],
                    "geocoding_status": geocoding_status,
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

    async def _geocode_if_configured(
        self,
        record: ExtractedRecord,
        city: str,
        country_code: str,
        existing_lat: float | None,
        existing_lng: float | None,
    ) -> tuple[float | None, float | None, str]:
        if existing_lat is not None and existing_lng is not None:
            return existing_lat, existing_lng, "existing"
        if not self.google_geocoding_api_key:
            return existing_lat, existing_lng, "disabled"
        address = ", ".join(part for part in [record.address, city, country_code] if part)
        if not address:
            return existing_lat, existing_lng, "missing_address"
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.get(
                    "https://maps.googleapis.com/maps/api/geocode/json",
                    params={"address": address, "key": self.google_geocoding_api_key},
                )
            payload = response.json()
            status = str(payload.get("status") or "UNKNOWN")
            if response.status_code >= 400 or status != "OK":
                return existing_lat, existing_lng, f"google:{status.lower()}"
            results = payload.get("results") or []
            location = (results[0].get("geometry", {}).get("location", {}) if results else {})
            lat = location.get("lat")
            lng = location.get("lng")
            if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
                return float(lat), float(lng), "ok"
            return existing_lat, existing_lng, "google:missing_location"
        except Exception:
            return existing_lat, existing_lng, "unreachable"

    def dedupe_score(self, left: EnrichedRecord, right: EnrichedRecord) -> tuple[float, list[str]]:
        scores: list[float] = []
        reasons: list[str] = []

        if left.phone and right.phone and left.phone == right.phone:
            scores.append(0.95)
            reasons.append("phone_exact")
        if left.website_url and right.website_url and self._domain(left.website_url) == self._domain(right.website_url):
            scores.append(0.95)
            reasons.append("website_domain")
        left_email_domain = self._email_domain(left.email)
        right_email_domain = self._email_domain(right.email)
        if left_email_domain and left_email_domain == right_email_domain and left_email_domain not in GENERIC_EMAIL_DOMAINS:
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
