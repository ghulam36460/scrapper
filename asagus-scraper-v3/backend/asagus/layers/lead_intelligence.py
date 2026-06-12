from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import parse_qs, unquote, urljoin, urlparse

from asagus.layers.external_adapters import external_adapter_state


EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-z]{2,}", re.I)
OBFUSCATED_EMAIL_RE = re.compile(
    r"([a-zA-Z0-9._%+-]{1,64})\s*(?:\(|\[)?\s*(?:at|@)\s*(?:\)|\])?\s*"
    r"([a-zA-Z0-9.-]{1,253})\s*(?:\(|\[)?\s*(?:dot|\.)\s*(?:\)|\])?\s*"
    r"([a-zA-Z]{2,24})",
    re.I,
)
PHONE_RE = re.compile(r"(?:\+|00)?\d[\d\s().-]{7,}\d")
HREF_RE = re.compile(r"href=[\"']([^\"']+)", re.I)
DIGIT_RE = re.compile(r"\d+")
WHATSAPP_REF_RE = re.compile(
    r"(?:wa\.me/|api\.whatsapp\.com/send\?phone=|whatsapp://send\?phone=|phone=)(\+?\d[\d\s().-]{5,18})",
    re.I,
)

SOCIAL_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "instagram": (
        re.compile(r"(?:https?://)?(?:www\.)?instagram\.com/([a-zA-Z0-9_.]{1,30})(?:[/?#\"']|$)", re.I),
    ),
    "facebook": (
        re.compile(r"(?:https?://)?(?:www\.)?(?:facebook|fb)\.com/([a-zA-Z0-9_.-]{1,60})(?:[/?#\"']|$)", re.I),
    ),
    "twitter": (
        re.compile(r"(?:https?://)?(?:www\.)?(?:twitter|x)\.com/([a-zA-Z0-9_]{1,15})(?:[/?#\"']|$)", re.I),
    ),
    "linkedin": (
        re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/(?:company|in)/([a-zA-Z0-9_-]{1,80})(?:[/?#\"']|$)", re.I),
    ),
    "tiktok": (
        re.compile(r"(?:https?://)?(?:www\.)?tiktok\.com/@([a-zA-Z0-9_.]{1,40})(?:[/?#\"']|$)", re.I),
    ),
    "youtube": (
        re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/(?:@|channel/|c/|user/)?([a-zA-Z0-9_-]{1,80})(?:[/?#\"']|$)", re.I),
    ),
}
INVALID_SOCIAL_HANDLES = {
    "share",
    "sharer",
    "intent",
    "dialog",
    "login",
    "signup",
    "home",
    "accounts",
    "help",
    "privacy",
    "terms",
    "legal",
    "contact",
    "plugins",
    "search",
}

CHATBOT_MARKERS = (
    "tidio",
    "intercom",
    "drift",
    "crisp",
    "livechat",
    "zendesk",
    "freshchat",
    "hubspot",
    "tawk.to",
    "olark",
    "smartsupp",
    "chatra",
    "jivochat",
    "whatsapp-widget",
    "click-to-chat",
    "wati.io",
)
ANALYTICS_MARKERS = {
    "google_analytics": ("google-analytics.com", "gtag", "analytics.js", "G-", "UA-", "GTM-"),
    "meta_pixel": ("facebook.com/tr", "fbevents.js", "fbq("),
    "hotjar": ("hotjar.com", "hj.js"),
    "mixpanel": ("mixpanel.com", "mixpanel.init"),
    "hubspot": ("hs-scripts.com", "hs-analytics"),
}
CMS_MARKERS = {
    "wordpress": ("wp-content", "wp-includes", "wordpress"),
    "wix": ("wix.com", "wixstatic.com", "_wix"),
    "squarespace": ("squarespace.com", "sqsp.net"),
    "shopify": ("shopify.com", "cdn.shopify"),
    "webflow": ("webflow.com", "webflow.io"),
    "godaddy": ("godaddy.com", "secureserver.net"),
    "weebly": ("weebly.com",),
    "duda": ("dudaone.com",),
}
NON_BUSINESS_DOMAINS = (
    "instagram.com",
    "facebook.com",
    "fb.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "tiktok.com",
    "youtube.com",
    "youtu.be",
    "wa.me",
    "whatsapp.com",
    "api.whatsapp.com",
    "telegram.me",
    "t.me",
    "linktr.ee",
    "beacons.ai",
    "bio.site",
)

GLOBAL_AREA_PATTERNS = (
    "Downtown {city}",
    "{city} City Center",
    "Central {city}",
    "{city} Business District",
    "{city} North",
    "{city} South",
    "{city} East",
    "{city} West",
    "Greater {city}",
    "{city} Nearby",
    "{city} Industrial Area",
    "{city} Market Area",
)
GLOBAL_DISCOVERY_MODIFIERS = ("best", "top rated", "local", "nearby", "popular", "trusted")
RADIUS_HINTS_KM = (3, 5, 8, 12, 20, 30)
COUNTRY_ALIASES = {
    "usa": "United States",
    "us": "United States",
    "uk": "United Kingdom",
    "uae": "United Arab Emirates",
    "ksa": "Saudi Arabia",
    "sa": "Saudi Arabia",
}


@dataclass(frozen=True)
class WebsiteIntelligence:
    emails: list[str]
    whatsapp_numbers: list[str]
    social_links: dict[str, str]
    has_chatbot: bool
    chatbot_type: str
    has_google_analytics: bool
    has_meta_pixel: bool
    other_analytics: list[str]
    cms_platform: str


def build_citywide_queries(keyword: str, location: str, max_queries: int = 14) -> list[str]:
    cleaned_keyword = re.sub(r"\s+", " ", (keyword or "").strip())
    cleaned_location = _normalize_country_aliases(location)
    if not cleaned_keyword or not cleaned_location:
        return []

    max_queries = max(1, min(max_queries, 72))
    city = _extract_city_anchor(cleaned_location)
    variants = _location_variants(cleaned_location)
    queries: list[str] = []
    seen: set[str] = set()

    for loc in variants[:5]:
        _append_query(queries, seen, f"{cleaned_keyword} in {loc}", max_queries)
        _append_query(queries, seen, f"{cleaned_keyword} near {loc}", max_queries)

    if variants:
        for radius in (5, 12):
            _append_query(queries, seen, f"{cleaned_keyword} within {radius} km of {variants[0]}", max_queries)

    if city:
        for pattern in GLOBAL_AREA_PATTERNS:
            area = pattern.format(city=city)
            _append_query(queries, seen, f"{cleaned_keyword} in {area}", max_queries)

    for loc in variants[:3]:
        for radius in RADIUS_HINTS_KM:
            _append_query(queries, seen, f"{cleaned_keyword} within {radius} km of {loc}", max_queries)

    if city:
        for modifier in GLOBAL_DISCOVERY_MODIFIERS:
            _append_query(queries, seen, f"{modifier} {cleaned_keyword} in {city}", max_queries)
        _append_query(queries, seen, f"{cleaned_keyword} in and around {city}", max_queries)

    _append_query(queries, seen, f"{cleaned_keyword} {cleaned_location}", max_queries)
    return queries[:max_queries]


def is_business_website(url: str) -> bool:
    cleaned = (url or "").strip()
    if not cleaned.startswith(("http://", "https://")):
        return False
    host = _host(cleaned)
    if not host:
        return False
    return not any(host == domain or host.endswith(f".{domain}") for domain in NON_BUSINESS_DOMAINS)


def normalize_business_website(url: str) -> str:
    cleaned = (url or "").strip()
    if not cleaned:
        return ""
    if not cleaned.startswith(("http://", "https://")):
        cleaned = f"https://{cleaned}"
    return cleaned if is_business_website(cleaned) else ""


def normalize_phone_number(raw_value: str, default_country_code: str = "92") -> tuple[bool, str, str]:
    raw = str(raw_value or "").strip()
    if not raw:
        return False, "", "empty"
    digits = re.sub(r"[^0-9+]", "", raw).removeprefix("+")
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("0"):
        digits = f"{default_country_code}{digits.lstrip('0')}"
    elif not digits.startswith(default_country_code) and re.fullmatch(r"\d{10}", digits):
        digits = f"{default_country_code}{digits}"
    if not re.fullmatch(r"\d{8,16}", digits):
        return False, "", "invalid_length_or_format"
    return True, digits, "valid"


def whatsapp_link(raw_value: str, default_country_code: str = "92") -> str:
    valid, digits, _reason = normalize_phone_number(raw_value, default_country_code)
    return f"https://wa.me/{digits}" if valid else ""


class BusinessWebsiteAnalyzer:
    def __init__(self, html: str, url: str = "") -> None:
        self.html = html or ""
        self.text = unescape(self.html)
        self.lower = self.text.lower()
        self.url = url

    def analyze(self) -> WebsiteIntelligence:
        has_chatbot, chatbot_type = self.detect_chatbot()
        analytics = self.detect_analytics()
        return WebsiteIntelligence(
            emails=self.extract_emails(),
            whatsapp_numbers=self.extract_whatsapp_numbers(),
            social_links=self.extract_social_links(),
            has_chatbot=has_chatbot,
            chatbot_type=chatbot_type,
            has_google_analytics=analytics["google_analytics"],
            has_meta_pixel=analytics["meta_pixel"],
            other_analytics=analytics["other"],
            cms_platform=self.detect_cms(),
        )

    def extract_emails(self) -> list[str]:
        matches = [email.lower() for email in EMAIL_RE.findall(self.text)]
        for local, domain, tld in OBFUSCATED_EMAIL_RE.findall(self.text):
            matches.append(f"{local}@{domain}.{tld}".lower())
        return _dedupe([email for email in matches if _valid_email(email)])

    def extract_whatsapp_numbers(self) -> list[str]:
        found: list[str] = []
        hrefs = HREF_RE.findall(self.text)
        for href in hrefs:
            href = unquote(unescape(href))
            if not _looks_like_whatsapp(href):
                continue
            found.extend(_numbers_from_whatsapp_ref(href))
        if not found and any(marker in self.lower for marker in ("wa.me", "api.whatsapp.com", "whatsapp://", "wa.link")):
            for match in WHATSAPP_REF_RE.findall(self.text):
                normalized = _normalize_contact_number(match)
                if normalized:
                    found.append(normalized)
            if not found:
                for match in PHONE_RE.findall(self.text):
                    normalized = _normalize_contact_number(match)
                    if normalized:
                        found.append(normalized)
        return _dedupe(found)

    def extract_social_links(self) -> dict[str, str]:
        links: dict[str, str] = {}
        corpus = [self.url, *[unescape(href) for href in HREF_RE.findall(self.text)]]
        for raw in corpus:
            absolute = urljoin(self.url, raw) if self.url else raw
            for platform, patterns in SOCIAL_PATTERNS.items():
                if platform in links:
                    continue
                for pattern in patterns:
                    match = pattern.search(absolute)
                    if not match:
                        continue
                    handle = match.group(1).strip("/")
                    if not handle or handle.lower() in INVALID_SOCIAL_HANDLES:
                        continue
                    links[platform] = _social_url(platform, handle)
                    break
        return links

    def detect_chatbot(self) -> tuple[bool, str]:
        for marker in CHATBOT_MARKERS:
            if marker in self.lower:
                return True, marker
        return False, ""

    def detect_analytics(self) -> dict[str, object]:
        result: dict[str, object] = {"google_analytics": False, "meta_pixel": False, "other": []}
        other: list[str] = []
        for tool, markers in ANALYTICS_MARKERS.items():
            if any(marker.lower() in self.lower for marker in markers):
                if tool == "google_analytics":
                    result["google_analytics"] = True
                elif tool == "meta_pixel":
                    result["meta_pixel"] = True
                else:
                    other.append(tool)
        result["other"] = sorted(set(other))
        return result

    def detect_cms(self) -> str:
        for cms, markers in CMS_MARKERS.items():
            if any(marker.lower() in self.lower for marker in markers):
                return cms
        return ""


def extract_google_maps_fields(html: str, source_url: str = "") -> dict[str, object]:
    text = unescape(html or "")
    clean_text = _clean(text)
    fields: dict[str, object] = {}
    if "google." not in _host(source_url) and "/maps/" not in source_url.lower():
        return fields

    title = _first_match(text, [r"<h1[^>]*class=[\"'][^\"']*DUwDvf[^\"']*[\"'][^>]*>(.*?)</h1>", r"<h1[^>]*>(.*?)</h1>"])
    phone = _first_match(
        text,
        [
            r"data-item-id=[\"']phone:tel:[^\"']+[\"'][^>]*>(.*?)</(?:button|a)>",
            r"aria-label=[\"'](?:Phone|Call):?\s*([^\"']+)[\"']",
        ],
    )
    website = _first_match(
        text,
        [
            r"<a[^>]+data-item-id=[\"']authority[\"'][^>]+href=[\"']([^\"']+)",
            r"<a[^>]+aria-label=[\"'][^\"']*Website[^\"']*[\"'][^>]+href=[\"']([^\"']+)",
        ],
    )
    address = _first_match(
        text,
        [
            r"data-item-id=[\"']address[\"'][^>]*>(.*?)</(?:button|div)>",
            r"aria-label=[\"']Address:?\s*([^\"']+)[\"']",
        ],
    )
    category = _first_match(text, [r"<(?:button|span)[^>]+class=[\"'][^\"']*DkEaL[^\"']*[\"'][^>]*>(.*?)</(?:button|span)>"])
    rating_match = re.search(r"([0-5](?:\.\d)?)\s*(?:stars?|rating)", clean_text, flags=re.I)
    reviews_match = re.search(r"([\d,]+)\s+reviews?", clean_text, flags=re.I)

    if title:
        fields["name"] = title
    if phone:
        fields["phone"] = phone
    if website:
        fields["website_url"] = normalize_business_website(website)
    if address:
        fields["address"] = address
    if category:
        fields["category"] = category
    if rating_match:
        try:
            fields["rating"] = float(rating_match.group(1))
        except ValueError:
            pass
    if reviews_match:
        try:
            fields["review_count"] = int(reviews_match.group(1).replace(",", ""))
        except ValueError:
            pass
    if fields:
        fields["google_maps_html_parser"] = True
    return {key: value for key, value in fields.items() if value not in {"", None}}


def adapter_state() -> dict[str, object]:
    return external_adapter_state()


def _append_query(queries: list[str], seen: set[str], query: str, max_queries: int) -> None:
    if len(queries) >= max_queries:
        return
    cleaned = re.sub(r"\s+", " ", query or "").strip()
    key = re.sub(r"[^a-z0-9]+", " ", cleaned.lower()).strip()
    if cleaned and key not in seen:
        seen.add(key)
        queries.append(cleaned)


def _normalize_country_aliases(location: str) -> str:
    cleaned = re.sub(r"\s+", " ", (location or "").strip())
    parts = [part.strip() for part in cleaned.split(",") if part.strip()]
    if not parts:
        return cleaned
    return ", ".join(COUNTRY_ALIASES.get(part.lower(), part) for part in parts)


def _extract_city_anchor(location: str) -> str:
    first = (location or "").split(",", 1)[0]
    first = re.sub(r"\b(city|town|district|province|state|region|county|municipality)\b", "", first, flags=re.I)
    return re.sub(r"\s+", " ", first).strip(" ,")


def _location_variants(location: str) -> list[str]:
    variants = []
    city = _extract_city_anchor(location)
    parts = [part.strip() for part in location.split(",") if part.strip()]
    for value in [location, city]:
        if value and value not in variants:
            variants.append(value)
    if city and len(parts) >= 2:
        for value in [f"{city}, {parts[1]}", f"{city}, {parts[-1]}", f"{city} {parts[-1]}"]:
            if value not in variants:
                variants.append(value)
    return variants


def _host(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return (parsed.netloc or "").lower().split(":", 1)[0].removeprefix("www.")


def _valid_email(email: str) -> bool:
    if not EMAIL_RE.fullmatch(email):
        return False
    _local, domain = email.rsplit("@", 1)
    domain = domain.lower().removeprefix("www.")
    return domain not in {"example.com", "test.com", "email.com", "domain.com", "sentry.io"}


def _looks_like_whatsapp(value: str) -> bool:
    lower = value.lower()
    return any(marker in lower for marker in ("wa.me", "api.whatsapp.com", "whatsapp://", "chat.whatsapp.com", "wa.link"))


def _numbers_from_whatsapp_ref(href: str) -> list[str]:
    decoded = unquote((href or "").strip())
    numbers = [_normalize_contact_number(match) for match in WHATSAPP_REF_RE.findall(decoded)]
    try:
        parsed = urlparse(decoded)
        for key in ("phone", "phonenumber", "number"):
            numbers.extend(_normalize_contact_number(value) for value in parse_qs(parsed.query).get(key, []))
    except Exception:
        pass
    if not any(numbers):
        digits = "".join(DIGIT_RE.findall(decoded))
        if 8 <= len(digits) <= 16:
            numbers.append(digits)
    return [number for number in numbers if number]


def _normalize_contact_number(value: str) -> str:
    cleaned = re.sub(r"[^\d+]", "", value or "")
    digits = cleaned.removeprefix("+")
    if digits.startswith("00"):
        digits = digits[2:]
    return f"+{digits}" if 8 <= len(digits) <= 16 else ""


def _social_url(platform: str, handle: str) -> str:
    if platform == "linkedin":
        return f"https://www.linkedin.com/company/{handle}"
    if platform == "twitter":
        return f"https://x.com/{handle}"
    if platform == "tiktok":
        return f"https://www.tiktok.com/@{handle}"
    if platform == "youtube":
        return f"https://www.youtube.com/{handle}"
    return f"https://www.{platform}.com/{handle}"


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.lower()
        if value and key not in seen:
            seen.add(key)
            out.append(value)
    return out


def _first_match(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text or "", flags=re.I | re.S)
        if match:
            return _clean(match.group(1))
    return ""


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", unescape(value or ""))).strip()
