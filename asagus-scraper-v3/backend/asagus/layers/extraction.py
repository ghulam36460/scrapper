from __future__ import annotations

import hashlib
import json
import re
from html import unescape
from urllib.parse import urljoin, urlparse

from asagus.llm.providers import LLMClient
from asagus.models import (
    ExtractedRecord,
    ExtractionMethod,
    ExtractionStageResult,
    FetchResult,
    PolicyDecision,
    SelectorFingerprint,
    utc_now,
)


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?:\+|00)?\d[\d\s().-]{7,}\d")
WA_RE = re.compile(r"(?:wa\.me/|whatsapp://send\?phone=|api\.whatsapp\.com/send\?phone=)(\+?\d{8,16})", re.I)
TEL_RE = re.compile(r"href=[\"']tel:([^\"']+)", re.I)
MAILTO_RE = re.compile(r"href=[\"']mailto:([^\"'?]+)", re.I)
HREF_RE = re.compile(r"href=[\"']([^\"']+)", re.I)
CFEMAIL_RE = re.compile(r"data-cfemail=[\"']([0-9a-fA-F]+)[\"']")
OBFUSCATED_EMAIL_RE = re.compile(
    r"\b([a-z0-9._%+-]{2,})\s*(?:\(|\[)?\s*at\s*(?:\)|\])?\s+([a-z0-9.-]+?)\s*(?:\(|\[)?\s*dot\s*(?:\)|\])?\s*([a-z]{2,})\b",
    re.I,
)
TITLE_RE = re.compile(r"<h[12][^>]*>(.*?)</h[12]>", re.I | re.S)
TITLE_TAG_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
META_TITLE_RE = re.compile(r"<meta[^>]+property=[\"']og:title[\"'][^>]+content=[\"']([^\"']+)", re.I)
ADDRESS_RE = re.compile(r"<(?:address|p|div)[^>]*(?:address|location)[^>]*>(.*?)</(?:address|p|div)>", re.I | re.S)
META_DESC_RE = re.compile(r"<meta[^>]+(?:name|property)=[\"'](?:description|og:description)[\"'][^>]+content=[\"']([^\"']+)", re.I)
LD_JSON_RE = re.compile(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.I | re.S)
SOCIAL_FIELDS = {
    "facebook_url": ("facebook.com", "fb.com"),
    "instagram_url": ("instagram.com",),
    "twitter_url": ("x.com", "twitter.com"),
    "linkedin_url": ("linkedin.com",),
}
PLACEHOLDER_EMAIL_DOMAINS = {
    "example.com",
    "example.org",
    "example.net",
    "domain.com",
    "email.com",
    "yourdomain.com",
    "test.com",
    "localhost",
}
PLACEHOLDER_EMAIL_USERS = {"hello", "test", "example", "name", "user", "email", "you", "yourname"}
ROLE_EMAIL_USERS = {
    "admin",
    "admission",
    "bookings",
    "care",
    "contact",
    "hello",
    "help",
    "hr",
    "info",
    "mail",
    "marketing",
    "office",
    "sales",
    "support",
    "team",
}
INVALID_EMAIL_TLDS = {"href", "src", "value", "click", "html", "css", "js"}


class ExtractionLayer:
    """Layer 4 self-healing extraction cascade."""

    CSS_ACCEPT = 0.78
    FINGERPRINT_ACCEPT = 0.68
    STRUCTURAL_ACCEPT = 0.48
    LLM_ACCEPT = 0.50
    _selector_store: dict[str, SelectorFingerprint] = {}

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client
        self.llm_cache: dict[str, ExtractedRecord] = {}

    async def extract(self, fetch: FetchResult, decision: PolicyDecision, llm_enabled: bool) -> ExtractedRecord:
        trace: list[ExtractionStageResult] = []

        css_record = self._extract_css_xpath(fetch)
        css_stage = self._stage_result(ExtractionMethod.css, css_record, self.CSS_ACCEPT, "CSS/XPath fast path")
        trace.append(css_stage)
        if css_stage.accepted:
            return self._with_trace(css_record, trace)

        fp_record = self._extract_dom_fingerprint(fetch, css_record)
        fp_stage = self._stage_result(
            ExtractionMethod.dom_fingerprint,
            fp_record,
            self.FINGERPRINT_ACCEPT,
            "Scrapling-style DOM fingerprint recovery",
        )
        trace.append(fp_stage)
        if fp_stage.accepted:
            return self._with_trace(fp_record, trace)

        heuristic_record = self._extract_structural(fetch, fp_record)
        heuristic_stage = self._stage_result(
            ExtractionMethod.structural_heuristic,
            heuristic_record,
            self.STRUCTURAL_ACCEPT,
            "Structural contact heuristics",
        )
        trace.append(heuristic_stage)
        if heuristic_stage.accepted:
            return self._with_trace(heuristic_record, trace)

        if llm_enabled and self.llm_client:
            llm_record = await self._extract_llm(fetch)
            if llm_record:
                llm_stage = self._stage_result(ExtractionMethod.llm, llm_record, self.LLM_ACCEPT, "LLM typed JSON fallback")
                trace.append(llm_stage)
                if llm_stage.accepted and llm_record.confidence >= heuristic_record.confidence:
                    return self._with_trace(llm_record, trace)

        manual = heuristic_record.model_copy(
            update={
                "method": ExtractionMethod.manual_review,
                "manual_review_required": True,
                "confidence": min(heuristic_record.confidence, 0.49),
            }
        )
        trace.append(
            ExtractionStageResult(
                stage=ExtractionMethod.manual_review,
                accepted=True,
                confidence=manual.confidence,
                fields_found=self._fields_found(manual),
                reason="All automated stages were below confidence threshold",
            )
        )
        return self._with_trace(manual, trace)

    def _extract_css_xpath(self, fetch: FetchResult) -> ExtractedRecord:
        html = fetch.html or ""
        json_ld = self._extract_json_ld_fields(html)
        links = self._links_from_html(html, fetch.url)
        social_links = self._social_links(links + [fetch.url])
        email = self._first_email(
            [
                str(json_ld.get("email") or ""),
                *MAILTO_RE.findall(html),
                *self._decode_cloudflare_emails(html),
                *EMAIL_RE.findall(self._visible_text(html)),
                *self._obfuscated_emails(self._visible_text(html)),
            ]
        )
        whatsapp_match = WA_RE.search(html)
        whatsapp = whatsapp_match.group(1) if whatsapp_match else str(json_ld.get("whatsapp") or "")
        phone = (
            str(json_ld.get("phone") or "")
            or next(iter(TEL_RE.findall(html)), "")
            or self._first_phone(self._visible_text(html), exclude=whatsapp)
        )
        title_match = TITLE_RE.search(html)
        title = (
            str(json_ld.get("name") or "")
            or (self._clean(title_match.group(1)) if title_match else "")
            or self._meta_title(html)
        )
        address_match = ADDRESS_RE.search(html)
        address = str(json_ld.get("address") or "") or (self._clean(address_match.group(1)) if address_match else "")
        parsed = urlparse(fetch.url)
        website_url = str(json_ld.get("website_url") or "")
        if not website_url and parsed.scheme and parsed.netloc and not self._is_social_url(fetch.url):
            website_url = f"{parsed.scheme}://{parsed.netloc}"
        if self._is_social_url(fetch.url):
            social_links = {**social_links, **self._social_links([fetch.url])}
        confidence = self._confidence(
            {
                "name": title,
                "email": email,
                "phone": phone,
                "whatsapp": whatsapp,
                "address": address,
                "website_url": website_url,
                "facebook_url": social_links.get("facebook_url", ""),
                "instagram_url": social_links.get("instagram_url", ""),
                "twitter_url": social_links.get("twitter_url", ""),
                "linkedin_url": social_links.get("linkedin_url", ""),
            },
            base=0.28,
        )

        record = ExtractedRecord(
            source_url=fetch.url,
            source="google_maps" if "google.com/maps" in fetch.url else "website_crawl",
            name=title,
            phone=phone,
            email=email,
            whatsapp=whatsapp,
            address=address,
            website_url=website_url,
            facebook_url=social_links.get("facebook_url", ""),
            instagram_url=social_links.get("instagram_url", ""),
            twitter_url=social_links.get("twitter_url", ""),
            linkedin_url=social_links.get("linkedin_url", ""),
            raw_fields={
                "content_type": fetch.content_type,
                "status_code": fetch.status_code,
                "links_found": len(links),
                "json_ld": bool(json_ld),
            },
            method=ExtractionMethod.css,
            confidence=confidence,
        )
        if record.confidence >= 0.55:
            self._store_fingerprints(fetch, record)
        return record

    def _extract_dom_fingerprint(self, fetch: FetchResult, base: ExtractedRecord) -> ExtractedRecord:
        domain = urlparse(fetch.url).netloc.lower()
        stored = [fp for fp in self._selector_store.values() if fp.domain == domain]
        confidence_boost = 0.14 if stored else 0.05
        signature_match = self._dom_signature(fetch.html)
        if stored and any(fp.dom_hash[:8] == signature_match[:8] for fp in stored):
            confidence_boost += 0.10

        record = base.model_copy(
            update={
                "method": ExtractionMethod.dom_fingerprint,
                "confidence": min(1.0, base.confidence + confidence_boost),
                "raw_fields": {
                    **base.raw_fields,
                    "dom_fingerprint": signature_match,
                    "selector_healing": "stored_match" if stored else "new_domain_signature",
                },
            }
        )
        if record.confidence >= self.FINGERPRINT_ACCEPT:
            self._store_fingerprints(fetch, record)
        return record

    def _extract_structural(self, fetch: FetchResult, base: ExtractedRecord) -> ExtractedRecord:
        html = fetch.html or ""
        meta_match = META_DESC_RE.search(html)
        meta_text = self._clean(meta_match.group(1)) if meta_match else ""
        inferred_category = self._infer_category(" ".join([base.name, meta_text, html[:3000]]))
        confidence = base.confidence
        if not base.category and inferred_category:
            confidence += 0.08
        if not base.name and meta_text:
            confidence += 0.07
        return base.model_copy(
            update={
                "name": base.name or self._title_from_meta(meta_text),
                "category": base.category or inferred_category,
                "method": ExtractionMethod.structural_heuristic,
                "confidence": min(1.0, confidence),
                "raw_fields": {**base.raw_fields, "meta_description": meta_text[:300]},
            }
        )

    async def _extract_llm(self, fetch: FetchResult) -> ExtractedRecord | None:
        cache_key = self._cache_key(fetch)
        if cache_key in self.llm_cache:
            return self.llm_cache[cache_key]
        text = self._html_to_markdownish(fetch.markdown or fetch.html)
        record = await self.llm_client.extract_business(text, fetch.url) if self.llm_client else None
        if record:
            record.raw_fields["llm_cache_key"] = cache_key
            self.llm_cache[cache_key] = record
        return record

    def _stage_result(
        self,
        method: ExtractionMethod,
        record: ExtractedRecord,
        threshold: float,
        reason: str,
    ) -> ExtractionStageResult:
        return ExtractionStageResult(
            stage=method,
            accepted=record.confidence >= threshold,
            confidence=round(record.confidence, 3),
            fields_found=self._fields_found(record),
            reason=f"{reason}; threshold={threshold}",
        )

    def _with_trace(self, record: ExtractedRecord, trace: list[ExtractionStageResult]) -> ExtractedRecord:
        return record.model_copy(update={"extraction_trace": trace})

    def _store_fingerprints(self, fetch: FetchResult, record: ExtractedRecord) -> None:
        domain = urlparse(fetch.url).netloc.lower()
        dom_hash = self._dom_signature(fetch.html)
        for field_name, value in {
            "name": record.name,
            "email": record.email,
            "phone": record.phone,
            "whatsapp": record.whatsapp,
            "address": record.address,
            "facebook_url": record.facebook_url,
            "instagram_url": record.instagram_url,
            "twitter_url": record.twitter_url,
            "linkedin_url": record.linkedin_url,
        }.items():
            if not value:
                continue
            key = f"{domain}:{field_name}"
            self._selector_store[key] = SelectorFingerprint(
                domain=domain,
                field_name=field_name,
                selector=f"auto::{field_name}",
                dom_hash=dom_hash,
                text_signature=self._stable_hash(str(value))[:16],
                confidence=record.confidence,
                last_seen_at=utc_now(),
            )

    def _confidence(self, fields: dict[str, str], base: float = 0.25) -> float:
        weights = {
            "name": 0.18,
            "email": 0.20,
            "phone": 0.16,
            "whatsapp": 0.18,
            "address": 0.12,
            "website_url": 0.08,
            "category": 0.08,
            "facebook_url": 0.06,
            "instagram_url": 0.06,
            "twitter_url": 0.05,
            "linkedin_url": 0.05,
        }
        value = base + sum(weight for key, weight in weights.items() if fields.get(key))
        return round(max(0.0, min(1.0, value)), 3)

    def _fields_found(self, record: ExtractedRecord) -> list[str]:
        fields = [
            "name",
            "phone",
            "whatsapp",
            "email",
            "address",
            "city",
            "website_url",
            "facebook_url",
            "instagram_url",
            "twitter_url",
            "linkedin_url",
            "category",
        ]
        return [field for field in fields if getattr(record, field)]

    def _first_phone(self, html: str, exclude: str = "") -> str:
        for match in PHONE_RE.findall(html):
            digits = re.sub(r"\D+", "", match)
            if exclude and digits.endswith(re.sub(r"\D+", "", exclude)):
                continue
            if 8 <= len(digits) <= 16:
                return match.strip()
        return ""

    def _first_email(self, values: list[str]) -> str:
        for value in values:
            email = self._normalize_email(value)
            if email and not self._is_placeholder_email(email):
                return email
        return ""

    def _normalize_email(self, value: str) -> str:
        email = unescape(value or "").strip().split("?", 1)[0].strip(".,;:()[]<>\"'").lower()
        if EMAIL_RE.fullmatch(email):
            return self._repair_email_user(email)
        match = EMAIL_RE.search(email)
        return self._repair_email_user(match.group(0).strip(".,;:").lower()) if match else ""

    def _repair_email_user(self, email: str) -> str:
        if "@" not in email:
            return email
        user, domain = email.rsplit("@", 1)
        stripped = re.sub(r"^\d+", "", user)
        if stripped in ROLE_EMAIL_USERS:
            return f"{stripped}@{domain}"
        return email

    def _is_placeholder_email(self, email: str) -> bool:
        if "@" not in email:
            return True
        user, domain = email.rsplit("@", 1)
        domain = domain.lower().removeprefix("www.")
        tld = domain.rsplit(".", 1)[-1] if "." in domain else ""
        if domain in PLACEHOLDER_EMAIL_DOMAINS:
            return True
        if tld in INVALID_EMAIL_TLDS:
            return True
        if user.lower() in PLACEHOLDER_EMAIL_USERS and domain.startswith(("example", "your", "test")):
            return True
        if domain.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg")):
            return True
        return False

    def _decode_cloudflare_emails(self, html: str) -> list[str]:
        emails: list[str] = []
        for encoded in CFEMAIL_RE.findall(html or ""):
            try:
                key = int(encoded[:2], 16)
                decoded = "".join(chr(int(encoded[index : index + 2], 16) ^ key) for index in range(2, len(encoded), 2))
                emails.append(decoded)
            except Exception:
                continue
        return emails

    def _obfuscated_emails(self, text: str) -> list[str]:
        emails: list[str] = []
        for user, domain, tld in OBFUSCATED_EMAIL_RE.findall(text or ""):
            emails.append(f"{user}@{domain}.{tld}")
        return emails

    def _title_from_meta(self, meta_text: str) -> str:
        if not meta_text:
            return ""
        return meta_text.split(".")[0][:90].strip()

    def _infer_category(self, text: str) -> str:
        lowered = text.lower()
        categories = {
            "restaurant": ["restaurant", "cafe", "food", "menu", "dining"],
            "clinic": ["clinic", "doctor", "dentist", "health", "medical"],
            "real estate": ["real estate", "property", "broker", "realtor"],
            "auto repair": ["auto", "mechanic", "garage", "repair", "vehicle"],
            "wedding venue": ["wedding", "banquet", "hall", "venue"],
        }
        for category, markers in categories.items():
            if any(marker in lowered for marker in markers):
                return category
        return ""

    def _extract_json_ld_fields(self, html: str) -> dict[str, str]:
        fields: dict[str, str] = {}
        for raw in LD_JSON_RE.findall(html or ""):
            try:
                payload = json.loads(unescape(raw.strip()))
            except json.JSONDecodeError:
                continue
            for item in self._walk_json_ld(payload):
                if not isinstance(item, dict):
                    continue
                item_type = " ".join(self._as_list(item.get("@type"))).lower()
                if item_type and not any(token in item_type for token in ["business", "organization", "restaurant", "store", "local"]):
                    continue
                fields.setdefault("name", str(item.get("name") or ""))
                fields.setdefault("email", str(item.get("email") or ""))
                fields.setdefault("phone", str(item.get("telephone") or item.get("phone") or ""))
                fields.setdefault("website_url", str(item.get("url") or ""))
                address = item.get("address")
                if isinstance(address, dict):
                    fields.setdefault(
                        "address",
                        ", ".join(
                            str(address.get(key) or "")
                            for key in ["streetAddress", "addressLocality", "addressRegion", "postalCode", "addressCountry"]
                            if address.get(key)
                        ),
                    )
                elif address:
                    fields.setdefault("address", str(address))
                same_as = [str(value) for value in self._as_list(item.get("sameAs"))]
                for key, value in self._social_links(same_as).items():
                    fields.setdefault(key, value)
        return {key: value for key, value in fields.items() if value}

    def _walk_json_ld(self, payload: object) -> list[object]:
        if isinstance(payload, list):
            return [child for item in payload for child in self._walk_json_ld(item)]
        if isinstance(payload, dict):
            graph = payload.get("@graph")
            if isinstance(graph, list):
                return [payload, *graph]
            return [payload]
        return []

    def _as_list(self, value: object) -> list[object]:
        if value is None:
            return []
        return value if isinstance(value, list) else [value]

    def _links_from_html(self, html: str, base_url: str) -> list[str]:
        links: list[str] = []
        for raw in HREF_RE.findall(html or ""):
            href = unescape(raw).strip()
            if not href or href.startswith(("#", "javascript:", "data:")):
                continue
            links.append(urljoin(base_url, href))
        return links

    def _social_links(self, urls: list[str]) -> dict[str, str]:
        found: dict[str, str] = {}
        for url in urls:
            lower = url.lower()
            if any(token in lower for token in ["/share", "/sharer", "/intent/", "/plugins/", "/login"]):
                continue
            for field, domains in SOCIAL_FIELDS.items():
                if field not in found and any(domain in lower for domain in domains):
                    found[field] = url.split("#", 1)[0]
        return found

    def _is_social_url(self, url: str) -> bool:
        lower = url.lower()
        return any(domain in lower for domains in SOCIAL_FIELDS.values() for domain in domains)

    def _meta_title(self, html: str) -> str:
        meta_match = META_TITLE_RE.search(html or "")
        if meta_match:
            return self._clean(meta_match.group(1))
        title_match = TITLE_TAG_RE.search(html or "")
        if title_match:
            return self._clean(title_match.group(1))
        return ""

    def _visible_text(self, html: str) -> str:
        text = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", html or "", flags=re.I | re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        return unescape(text)

    def _html_to_markdownish(self, text: str) -> str:
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.I | re.S)
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
        text = re.sub(r"</(p|div|li|h1|h2|h3|address)>", "\n", text, flags=re.I)
        return re.sub(r"\n{3,}", "\n\n", self._clean(text))

    def _clean(self, value: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", unescape(value or ""))).strip()

    def _dom_signature(self, html: str) -> str:
        tags = re.findall(r"<([a-zA-Z0-9]+)(?:\s|>)", html or "")
        signature = "|".join(tag.lower() for tag in tags[:300])
        return self._stable_hash(signature)

    def _cache_key(self, fetch: FetchResult) -> str:
        return self._stable_hash(f"{urlparse(fetch.url).netloc}:{fetch.html[:20000]}")

    def _stable_hash(self, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()
