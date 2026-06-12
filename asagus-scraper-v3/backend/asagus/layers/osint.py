from __future__ import annotations

from urllib.parse import quote_plus


class SafeOSINTLayer:
    """Public-business OSINT helpers with strict guardrails."""

    blocked_dork_terms = {
        "password",
        "passwd",
        "secret",
        "token",
        "apikey",
        "api_key",
        "credential",
        "session",
        "cookie",
        "jwt",
        "filetype:env",
        "ext:env",
        "inurl:admin",
        "intitle:index of",
    }

    def build_public_business_dorks(self, query: str, location: str) -> list[str]:
        safe_query = self._sanitize(query)
        safe_location = self._sanitize(location)
        base = f"{safe_query} {safe_location}".strip()
        return [
            f'"{base}" "contact"',
            f'"{base}" "WhatsApp"',
            f'"{base}" site:facebook.com',
            f'"{base}" site:instagram.com',
            f'"{base}" site:linkedin.com/company',
            f'"{base}" "address" "phone"',
        ]

    def validate_operator_query(self, query: str) -> tuple[bool, list[str]]:
        lowered = query.lower()
        hits = sorted(term for term in self.blocked_dork_terms if term in lowered)
        return not hits, hits

    def public_api_session_policy(self) -> dict[str, object]:
        return {
            "api_session_exploitation": False,
            "supported": ["documented_public_api_keys", "oauth_for_owned_accounts", "rate_limited_public_endpoints"],
            "blocked": ["stolen_cookies", "session_replay", "auth_bypass", "private_api_abuse"],
            "review_required": True,
        }

    def fusion_policy(self) -> dict[str, object]:
        return {
            "cross_platform_osint_fusion": "guarded",
            "scope": "business entities and public pages only",
            "human_review_required": True,
            "pii_minimization": True,
            "sources": ["search_results", "business_websites", "public_social_business_pages", "maps_profiles"],
        }

    def discovery_url(self, query: str, location: str) -> str:
        dork = self.build_public_business_dorks(query, location)[0]
        return f"https://www.google.com/search?q={quote_plus(dork)}"

    def _sanitize(self, value: str) -> str:
        cleaned = " ".join(part for part in value.replace('"', " ").split() if part)
        valid, hits = self.validate_operator_query(cleaned)
        if not valid:
            for hit in hits:
                cleaned = cleaned.lower().replace(hit, "")
        return " ".join(cleaned.split())

    def state(self) -> dict[str, object]:
        return {
            "google_dorking": "public business discovery templates only",
            "blocked_dork_terms": sorted(self.blocked_dork_terms),
            "api_sessions": self.public_api_session_policy(),
            "fusion": self.fusion_policy(),
        }
