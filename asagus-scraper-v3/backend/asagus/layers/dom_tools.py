from __future__ import annotations

import hashlib
import platform
import re
from html import unescape
from urllib.parse import urlparse


class DOMTools:
    """DOM parsing, CSS selector matching and XPath querying adapters."""

    def text_by_css(self, html: str, selector: str) -> list[str]:
        try:
            from selectolax.parser import HTMLParser  # type: ignore

            tree = HTMLParser(html or "")
            return [self.clean(node.text()) for node in tree.css(selector)]
        except Exception:
            if selector in {"title", "h1", "h2"}:
                return [self.clean(match) for match in re.findall(fr"<{selector}[^>]*>(.*?)</{selector}>", html or "", flags=re.I | re.S)]
            return []

    def text_by_xpath(self, html: str, xpath: str) -> list[str]:
        try:
            from lxml import html as lxml_html  # type: ignore

            tree = lxml_html.fromstring(html or "")
            values = tree.xpath(xpath)
            out = []
            for value in values:
                if hasattr(value, "text_content"):
                    out.append(self.clean(value.text_content()))
                else:
                    out.append(self.clean(str(value)))
            return out
        except Exception:
            return []

    def dom_features(self, html: str) -> dict[str, object]:
        tags = re.findall(r"<([a-zA-Z0-9]+)(?:\s|>)", html or "")
        scripts = len(re.findall(r"<script\b", html or "", flags=re.I))
        links = len(re.findall(r"<a\b", html or "", flags=re.I))
        forms = len(re.findall(r"<form\b", html or "", flags=re.I))
        return {
            "tag_count": len(tags),
            "unique_tags": len(set(tag.lower() for tag in tags)),
            "script_count": scripts,
            "link_count": links,
            "form_count": forms,
            "js_complexity_score": round(min(1.0, scripts / 20 + forms / 10), 3),
            "link_density": round(min(1.0, links / max(len(tags), 1) * 5), 3),
        }

    def fingerprint(self, html: str, url: str = "") -> dict[str, object]:
        """Stable structural page signature for selector healing and replay."""
        html = html or ""
        tags = [tag.lower() for tag in re.findall(r"<([a-zA-Z0-9]+)(?:\s|>)", html)]
        headings = [self.clean(text)[:80] for text in re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", html, flags=re.I | re.S)]
        labels = [self.clean(text)[:80] for text in re.findall(r"<label[^>]*>(.*?)</label>", html, flags=re.I | re.S)]
        json_ld_count = len(re.findall(r'application/ld\+json', html, flags=re.I))
        email_links = len(re.findall(r"mailto:", html, flags=re.I))
        tel_links = len(re.findall(r"(?:tel:|wa\.me/|whatsapp)", html, flags=re.I))
        social_links = len(re.findall(r"(facebook|instagram|linkedin|twitter|x\.com)\.com", html, flags=re.I))
        tag_sequence = " ".join(tags[:800])
        text_signature = " | ".join([*headings[:8], *labels[:8]])
        domain = urlparse(url).netloc.lower()
        return {
            "domain": domain,
            "dom_hash": hashlib.sha256(tag_sequence.encode("utf-8")).hexdigest()[:24],
            "text_hash": hashlib.sha256(text_signature.lower().encode("utf-8")).hexdigest()[:16],
            "tag_count": len(tags),
            "unique_tags": len(set(tags)),
            "json_ld_count": json_ld_count,
            "email_link_count": email_links,
            "phone_or_whatsapp_link_count": tel_links,
            "social_link_count": social_links,
            "heading_sample": headings[:5],
            "label_sample": labels[:5],
            "page_type": self.classify_page(html, url),
        }

    def device_stamp(self, *, fetch_mode: str, render_time_ms: int, status_code: int) -> dict[str, object]:
        """Debug stamp for reproducibility; not an anti-detection fingerprint."""
        return {
            "runtime": "python",
            "python": platform.python_version(),
            "system": platform.system().lower(),
            "machine": platform.machine(),
            "fetch_mode": fetch_mode,
            "status_code": status_code,
            "render_time_ms": render_time_ms,
            "viewport": "1365x900",
            "javascript_enabled": fetch_mode == "dynamic",
            "browser_profile": "asagus-dedicated",
        }

    def detect_challenge(self, html: str, status_code: int = 0) -> dict[str, object]:
        text = self.clean(html).lower()
        patterns = [
            "captcha",
            "verify you are human",
            "access denied",
            "unusual traffic",
            "checking your browser",
            "too many requests",
            "rate limit",
            "login required",
            "awswaf",
            "aws-waf-token",
            "amazon web services waf",
            "waf token",
            "x-amzn-waf",
        ]
        matches = [pattern for pattern in patterns if pattern in text]
        if "javascript is disabled" in text and any(token in text for token in ("awswaf", "aws-waf", "waf token")):
            matches.append("javascript_waf_challenge")
        if status_code in {401, 403, 429} and "status_code" not in matches:
            matches.append(f"status_{status_code}")
        return {
            "challenge_detected": bool(matches),
            "signals": matches[:8],
            "manual_review_required": bool(matches),
            "bypass_attempted": False,
        }

    def classify_page(self, html: str, url: str = "") -> str:
        lower = f"{url} {self.clean(html[:10000])}".lower()
        if any(token in lower for token in ["contact", "phone", "email", "whatsapp", "address"]):
            return "contact"
        if any(token in lower for token in ["menu", "reservation", "restaurant", "cuisine"]):
            return "restaurant"
        if any(token in lower for token in ["clinic", "doctor", "appointment", "patient"]):
            return "clinic"
        if any(token in lower for token in ["directory", "listing", "profile"]):
            return "directory"
        if any(token in lower for token in ["about us", "our story", "team"]):
            return "about"
        return "generic"

    def clean(self, value: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", unescape(value or ""))).strip()

    def state(self) -> dict[str, object]:
        return {
            "implemented": [
                "dom_feature_extraction",
                "dom_fingerprint",
                "device_render_stamp",
                "challenge_detection_manual_review",
                "css_selector_matching",
                "xpath_querying",
            ],
            "primary_parser": "selectolax",
            "xpath_adapter": "lxml when installed",
            "safety_boundary": "fingerprints are used for selector healing/debugging only; no CAPTCHA bypass or anti-bot evasion",
        }
