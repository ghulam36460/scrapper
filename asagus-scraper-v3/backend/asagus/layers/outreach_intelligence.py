from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse


SERVICE_NICHES: dict[str, tuple[str, ...]] = {
    "auto_repair": ("auto repair", "mechanic", "garage", "vehicle service", "car repair"),
    "plumbing": ("plumber", "plumbing", "drain", "pipe repair"),
    "electrical": ("electrician", "electrical", "wiring", "generator"),
    "dental": ("dentist", "dental", "orthodont", "teeth"),
    "hvac": ("hvac", "air conditioning", "heating", "cooling", "ac repair"),
    "salon": ("salon", "barber", "beauty", "hair", "spa", "nails"),
    "pest_control": ("pest control", "exterminator", "fumigation"),
    "mobile_repair": ("mobile repair", "phone repair", "screen repair"),
    "real_estate": ("real estate", "property", "realtor", "estate agent"),
    "restaurant": ("restaurant", "cafe", "food", "burger", "catering"),
    "clinic": ("clinic", "doctor", "medical", "health", "skin specialist"),
    "wedding_venue": ("wedding", "banquet", "marquee", "event hall", "venue"),
}

HIGH_INTENT_NICHES = {"auto_repair", "plumbing", "electrical", "dental", "hvac", "clinic"}
MEDIUM_INTENT_NICHES = {"salon", "pest_control", "mobile_repair", "wedding_venue"}
LOW_INTENT_NICHES = {"real_estate", "restaurant"}
SOCIAL_FIELDS = ("facebook_url", "instagram_url", "twitter_url", "linkedin_url")


@dataclass(frozen=True)
class OutreachProfile:
    score: int
    segment: str
    niche: str
    recommended_channel: str
    public_presence: str
    channels: dict[str, bool] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "score": self.score,
            "segment": self.segment,
            "niche": self.niche,
            "recommended_channel": self.recommended_channel,
            "public_presence": self.public_presence,
            "channels": self.channels,
            "reasons": self.reasons,
            "blockers": self.blockers,
            "source": "native_outreach_intelligence",
        }


def outreach_profile_for(record: Any) -> dict[str, object]:
    raw_fields = _as_dict(_value(record, "raw_fields", {}))
    website_url = str(_value(record, "website_url", "") or "")
    email = str(_value(record, "email", "") or "")
    phone = str(_value(record, "phone", "") or "")
    whatsapp = str(_value(record, "whatsapp", "") or "")
    city = str(_value(record, "city", "") or "")
    category = str(_value(record, "category", "") or "")
    name = str(_value(record, "name", "") or "")
    review_count = _as_int(_value(record, "review_count", raw_fields.get("review_count", 0)))
    confidence = _as_float(_value(record, "confidence", 0.0))
    completeness = _as_float(_value(record, "record_completeness", 0.0))
    decision_makers = raw_fields.get("decision_makers", [])
    has_decision_maker = isinstance(decision_makers, list) and bool(decision_makers)
    has_social = any(str(_value(record, field, "") or "") for field in SOCIAL_FIELDS)
    has_website = bool(_domain(website_url))
    niche = detect_niche(name, category, raw_fields)

    channels = {
        "email": bool(email),
        "phone": bool(phone),
        "whatsapp": bool(whatsapp),
        "website": has_website,
        "social": has_social,
        "decision_maker": has_decision_maker,
    }
    reasons: list[str] = []
    blockers: list[str] = []
    score = 0

    if email or phone or whatsapp:
        score += 25
        reasons.append("direct_contact_found")
    if whatsapp:
        score += 15
        reasons.append("whatsapp_ready")
    elif phone:
        score += 8
        reasons.append("phone_available")
    if email:
        score += 10
        reasons.append("email_available")

    if not has_website:
        score += 22
        reasons.append("no_owned_website_opportunity")
    elif not _looks_like_strong_website(website_url):
        score += 6
        reasons.append("weak_or_generic_website_signal")

    if niche in HIGH_INTENT_NICHES:
        score += 20
        reasons.append("high_intent_local_service_niche")
    elif niche in MEDIUM_INTENT_NICHES:
        score += 15
        reasons.append("medium_intent_local_service_niche")
    elif niche in LOW_INTENT_NICHES:
        score += 10
        reasons.append("local_business_niche")

    if has_decision_maker:
        score += 10
        reasons.append("decision_maker_signal")
    if review_count >= 100:
        score += 15
        reasons.append("strong_review_volume")
    elif review_count >= 30:
        score += 10
        reasons.append("healthy_review_volume")
    elif review_count > 0:
        score += 5
        reasons.append("some_review_volume")
    if city:
        score += 8
        reasons.append("city_known")
    if not has_social and not has_website:
        score += 5
        reasons.append("low_public_presence")
    if confidence >= 0.75:
        score += 8
        reasons.append("high_extraction_confidence")
    elif confidence >= 0.55:
        score += 4
        reasons.append("usable_extraction_confidence")
    if completeness >= 0.60:
        score += 5
        reasons.append("complete_record")

    if bool(_value(record, "gdpr_flag", False)) or bool(_value(record, "pdpa_flag", False)):
        score -= 8
        blockers.append("privacy_region_review")
    if not (email or phone or whatsapp or has_social):
        score -= 18
        blockers.append("no_contact_channel")

    score = max(0, min(100, score))
    return OutreachProfile(
        score=score,
        segment=_segment(score),
        niche=niche,
        recommended_channel=_recommended_channel(email, phone, whatsapp, has_social, has_website),
        public_presence=_public_presence(has_website, has_social),
        channels=channels,
        reasons=reasons[:10],
        blockers=blockers,
    ).as_dict()


def detect_niche(name: str, category: str, raw_fields: dict[str, Any] | None = None) -> str:
    raw_fields = raw_fields or {}
    haystack = " ".join(
        [
            name,
            category,
            str(raw_fields.get("meta_description", "")),
            str(raw_fields.get("source_url", "")),
            str(raw_fields.get("candidate_metadata", "")),
        ]
    ).lower()
    haystack = re.sub(r"[_-]+", " ", haystack)
    for niche, markers in SERVICE_NICHES.items():
        if any(marker in haystack for marker in markers):
            return niche
    return ""


def _recommended_channel(email: str, phone: str, whatsapp: str, has_social: bool, has_website: bool) -> str:
    if whatsapp:
        return "whatsapp"
    if email and _email_user(email) not in {"", "info", "admin", "support", "contact", "office"}:
        return "email_direct"
    if email:
        return "email_generic"
    if phone:
        return "phone"
    if has_social:
        return "social_dm_review"
    if has_website:
        return "website_form_review"
    return "research_more"


def _segment(score: int) -> str:
    if score >= 75:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


def _public_presence(has_website: bool, has_social: bool) -> str:
    if has_website and has_social:
        return "website_and_social"
    if has_website:
        return "website_only"
    if has_social:
        return "social_only"
    return "low_public_presence"


def _looks_like_strong_website(url: str) -> bool:
    host = _domain(url)
    if not host:
        return False
    generic_hosts = ("facebook.com", "instagram.com", "linktr.ee", "beacons.ai", "sites.google.com")
    return not any(host == domain or host.endswith(f".{domain}") for domain in generic_hosts)


def _domain(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return (parsed.netloc or "").lower().split(":", 1)[0].removeprefix("www.")


def _email_user(email: str) -> str:
    return email.split("@", 1)[0].lower() if "@" in email else ""


def _value(record: Any, name: str, default: Any = "") -> Any:
    if isinstance(record, dict):
        return record.get(name, default)
    return getattr(record, name, default)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_int(value: Any) -> int:
    try:
        if value in {"", None}:
            return 0
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return 0


def _as_float(value: Any) -> float:
    try:
        if value in {"", None}:
            return 0.0
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0
