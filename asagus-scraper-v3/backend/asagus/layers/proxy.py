from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlparse

from asagus.models import ProxyEndpoint, ProxyTier, URLCandidate, utc_now


class ProxyPoolManager:
    """Layer 3 proxy tier selector with ban-rate backoff and geo hints."""

    tier_order = [
        ProxyTier.residential,
        ProxyTier.isp_static,
        ProxyTier.datacenter,
        ProxyTier.budget_residential,
    ]

    def __init__(self) -> None:
        self.endpoints: list[ProxyEndpoint] = [
            ProxyEndpoint(id="direct-local", tier=ProxyTier.datacenter, provider="direct", endpoint="", active=True),
            ProxyEndpoint(id="residential-slot", tier=ProxyTier.residential, provider="byo", endpoint="", active=False),
            ProxyEndpoint(id="isp-static-slot", tier=ProxyTier.isp_static, provider="byo", endpoint="", active=False),
            ProxyEndpoint(id="budget-res-slot", tier=ProxyTier.budget_residential, provider="byo", endpoint="", active=False),
        ]

    def choose(self, candidate: URLCandidate, strategy: str = "auto") -> ProxyEndpoint:
        desired_tier = self._desired_tier(candidate, strategy)
        now = utc_now()
        candidates = [
            proxy
            for proxy in self.endpoints
            if proxy.active and (proxy.cooldown_until is None or proxy.cooldown_until <= now)
        ]
        if not candidates:
            return self.endpoints[0]
        tier_matches = [proxy for proxy in candidates if proxy.tier == desired_tier]
        pool = tier_matches or candidates
        return sorted(pool, key=lambda proxy: (proxy.ban_rate, -proxy.success_rate))[0]

    def register_result(self, proxy_id: str, success: bool, blocked: bool = False, error: str = "") -> None:
        for proxy in self.endpoints:
            if proxy.id != proxy_id:
                continue
            proxy.success_rate = self._ema(proxy.success_rate, 1.0 if success else 0.0, 0.18)
            proxy.ban_rate = self._ema(proxy.ban_rate, 1.0 if blocked else 0.0, 0.25)
            proxy.last_error = error
            if blocked or proxy.ban_rate > 0.40:
                minutes = min(240, 5 * (1 + int(proxy.ban_rate * 10)))
                proxy.cooldown_until = utc_now() + timedelta(minutes=minutes)
            return

    def _desired_tier(self, candidate: URLCandidate, strategy: str) -> ProxyTier:
        if strategy in {tier.value for tier in ProxyTier}:
            return ProxyTier(strategy)
        host = urlparse(candidate.url).netloc.lower()
        if "google.com" in host or candidate.js_complexity_score >= 0.75:
            return ProxyTier.residential
        if candidate.domain_ban_rate >= 0.25:
            return ProxyTier.isp_static
        if candidate.depth <= 1 and candidate.domain_yield_rate >= 0.55:
            return ProxyTier.datacenter
        return ProxyTier.budget_residential

    def _ema(self, old: float, new: float, weight: float) -> float:
        return round(max(0.0, min(1.0, old * (1 - weight) + new * weight)), 4)

    def state(self) -> dict[str, object]:
        return {
            "tiers": [tier.value for tier in ProxyTier],
            "tier_order": [tier.value for tier in self.tier_order],
            "endpoints": [endpoint.model_dump(mode="json") for endpoint in self.endpoints],
            "backoff": "exponential cooldown when ban_rate exceeds 0.40",
        }
