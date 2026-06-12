"""Challenge detection for CAPTCHA, rate limiting, and access blocks."""

from __future__ import annotations

import re
from enum import Enum
from typing import Optional

from asagus.models import utc_now


class ChallengeType(str, Enum):
    recaptcha_v2 = "recaptcha_v2"
    recaptcha_v3 = "recaptcha_v3"
    cloudflare_turnstile = "cloudflare_turnstile"
    cloudflare_challenge = "cloudflare_challenge"
    akamai_bot_manager = "akamai_bot_manager"
    perimeter_x = "perimeter_x"
    datadome = "datadome"
    imperva = "imperva"
    unknown_challenge = "unknown_challenge"


class ChallengeDetector:
    """Detects bot challenges, rate limiting, and access blocks for research analysis."""

    CAPTCHA_PATTERNS = {
        ChallengeType.recaptcha_v2: [
            r'g-recaptcha(?!-enterprise)',
            r"grecaptcha\.render",
            r'data-sitekey="[^"]+"',
        ],
        ChallengeType.recaptcha_v3: [
            r'g-recaptcha-enterprise',
            r"grecaptcha\.enterprise",
            r'window\["grecaptcha"\]\.execute',
        ],
        ChallengeType.cloudflare_turnstile: [
            r'Cloudflare Turnstile',
            r'cf_clearance',
            r'window\.turnstile',
            r"window\['cf'\]",
        ],
        ChallengeType.cloudflare_challenge: [
            r'<title>Attention Required!',
            r'Cloudflare',
            r'Checking your browser before accessing',
            r'__cf_bm',
        ],
        ChallengeType.akamai_bot_manager: [
            r"akamai\.require",
            r"_bm\.js",
            r"sen\.js",
        ],
        ChallengeType.perimeter_x: [
            r"/_px\.js",
            r"px\.js",
            r"PXScript",
        ],
        ChallengeType.datadome: [
            r"dd_js",
            r"datadome",
        ],
        ChallengeType.imperva: [
            r"imspx\.js",
            r"_Incapsula_Resource",
        ],
    }

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def detect(self, html: str, status_code: int = 200, headers: dict | None = None, final_url: str = "") -> dict[str, object]:
        """Analyze page for challenges."""
        challenges = []
        headers = headers or {}

        # 1. Check status codes
        if status_code in {403, 429, 503}:
            challenges.append({
                "type": "http_status",
                "status_code": status_code,
                "message": self._status_message(status_code),
            })

        # 2. Check headers
        header_challenges = self._check_headers(headers)
        challenges.extend(header_challenges)

        # 3. Check HTML patterns
        detected_types = self._detect_html_patterns(html)
        for ctype, patterns in detected_types.items():
            challenges.append({
                "type": ctype.value,
                "detected_patterns": patterns,
                "confidence": round(len(patterns) / len(self.CAPTCHA_PATTERNS[ctype]), 2),
            })

        # 4. Check redirect logic
        if self._is_redirect_page(html):
            challenges.append({
                "type": "redirect",
                "message": "Page appears to be a challenge redirect",
            })

        # 5. Check frame/iframe injection
        if self._has_challenge_frames(html):
            challenges.append({
                "type": "challenge_frame_detected",
                "message": "Challenge widget iframe detected",
            })

        is_challenged = bool(challenges)
        severity = self._calculate_severity(challenges, status_code)

        return {
            "timestamp": utc_now().isoformat(),
            "url": final_url,
            "status_code": status_code,
            "is_challenged": is_challenged,
            "severity": severity,
            "challenges": challenges,
            "recommendation": self._recommend_action(challenges, severity),
        }

    def _detect_html_patterns(self, html: str) -> dict[ChallengeType, list[str]]:
        """Detect CAPTCHA and bot challenge patterns in HTML."""
        detected = {}
        for ctype, patterns in self.CAPTCHA_PATTERNS.items():
            matches = []
            for pattern in patterns:
                if re.search(pattern, html, re.IGNORECASE):
                    matches.append(pattern[:50])
            if matches:
                detected[ctype] = matches
        return detected

    def _check_headers(self, headers: dict) -> list[dict]:
        """Check response headers for challenge indicators."""
        challenges = []
        headers_lower = {k.lower(): v for k, v in headers.items()}

        if "cf_ray" in headers_lower or "cf-ray" in headers_lower:
            challenges.append({
                "type": "cloudflare_signature",
                "header": "CF-Ray",
                "confidence": 0.8,
            })

        if "x-challenge" in headers_lower:
            challenges.append({
                "type": "generic_challenge_header",
                "header": "X-Challenge",
                "confidence": 0.7,
            })

        if "retry-after" in headers_lower:
            challenges.append({
                "type": "rate_limited",
                "header": "Retry-After",
                "message": f"Rate limit detected: {headers_lower['retry-after']}",
            })

        return challenges

    def _is_redirect_page(self, html: str) -> bool:
        """Check if page is a redirect/challenge page."""
        redirect_keywords = [
            "Checking your browser",
            "Please wait while we check",
            "temporarily unavailable",
            "security check",
            "verify you",
            "challenge",
            "access denied",
        ]

        html_lower = html.lower()
        title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        if title_match:
            title = title_match.group(1).lower()
            for keyword in redirect_keywords:
                if keyword in title:
                    return True

        for keyword in redirect_keywords:
            if keyword in html_lower:
                return True

        return False

    def _has_challenge_frames(self, html: str) -> bool:
        """Detect challenge widget iframes."""
        challenge_domains = [
            "recaptcha",
            "challenges.cloudflare",
            "cdn.cookielaw",
            "_challenge",
            "akamai",
        ]
        for domain in challenge_domains:
            if domain.lower() in html.lower():
                return True
        return False

    def _calculate_severity(self, challenges: list[dict], status_code: int) -> str:
        """Determine severity of challenge."""
        if not challenges:
            return "none"

        has_high = any(c.get("type") in {
            "recaptcha_v2", "recaptcha_v3", "cloudflare_challenge"
        } for c in challenges)

        has_rate_limit = any("rate_limit" in c.get("type", "") for c in challenges)
        has_block = status_code in {403, 429}

        if has_high:
            return "high"
        if has_block:
            return "high"
        if has_rate_limit:
            return "medium"

        return "low"

    def _recommend_action(self, challenges: list, severity: str) -> str:
        """Recommend next action."""
        if severity == "high":
            return "manual_review_required"
        if severity == "medium":
            return "wait_and_retry"
        return "proceed"

    def _status_message(self, status: int) -> str:
        """Get message for status code."""
        messages = {
            403: "Access Forbidden - likely blocked",
            429: "Too Many Requests - rate limited",
            503: "Service Unavailable - temporary block",
        }
        return messages.get(status, f"HTTP {status}")

    def state(self) -> dict[str, object]:
        return {
            "purpose": "Detect CAPTCHA, rate limiting, and bot challenge indicators",
            "supported_challenges": [c.value for c in ChallengeType],
            "methods": [
                "http_status_analysis",
                "response_header_analysis",
                "html_pattern_matching",
                "redirect_detection",
                "frame_injection_detection",
            ],
            "manual_review_on": ["high_severity_challenges"],
            "note": "Does not bypass challenges; detects for research analysis only",
        }
