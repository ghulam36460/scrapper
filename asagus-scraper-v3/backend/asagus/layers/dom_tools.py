from __future__ import annotations

import re
from html import unescape


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

    def clean(self, value: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", unescape(value or ""))).strip()

    def state(self) -> dict[str, object]:
        return {
            "implemented": ["dom_feature_extraction", "css_selector_matching", "xpath_querying"],
            "primary_parser": "selectolax",
            "xpath_adapter": "lxml when installed",
        }
