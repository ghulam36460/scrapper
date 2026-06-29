from __future__ import annotations

import logging
from datetime import timedelta
from urllib.parse import urlparse

from asagus.models import ProxyEndpoint, ProxyTier, URLCandidate, utc_now

logger = logging.getLogger(__name__)


class ProxyPoolManager:
    """Layer 3 proxy tier selector with ban-rate backoff and geo hints."""

    tier_order = [
        ProxyTier.residential,
        ProxyTier.isp_static,
        ProxyTier.datacenter,
        ProxyTier.budget_residential,
    ]

    def __init__(self, proxy_urls: dict[ProxyTier, str] | None = None) -> None:
        proxy_urls = proxy_urls or {}
        
        # Check residential proxy settings
        from asagus.config import get_settings
        try:
            settings = get_settings()
            self.use_residential_proxies = settings.use_residential_proxies
        except Exception as exc:
            logger.warning("Failed to load settings in ProxyPoolManager: %s", exc)
            self.use_residential_proxies = False
            settings = None

        self.provider = None
        if self.use_residential_proxies and settings is not None:
            try:
                from asagus.layers.proxy_providers import GenericGatewayProvider, PROVIDER_PRESETS
                provider_name = settings.active_proxy_provider or "brightdata"
                preset = PROVIDER_PRESETS.get(provider_name.lower())
                if settings.provider_username:
                    self.provider = GenericGatewayProvider(
                        preset=preset,
                        username=settings.provider_username,
                        password=settings.provider_password,
                        rotation_mode=settings.proxy_rotation_mode,
                        sticky_duration=settings.proxy_sticky_duration,
                        country=settings.proxy_country,
                        region=settings.proxy_region,
                    )
                    logger.info("Initialized dynamic residential proxy provider: %s", provider_name)
                else:
                    logger.warning("PROVIDER_USERNAME is empty; fallback to static residential proxy url")
            except Exception as exc:
                logger.error("Failed to initialize residential proxy provider %s: %s", settings.active_proxy_provider, exc)
                # Keep self.provider = None to ensure safe fallback behavior

        self.endpoints: list[ProxyEndpoint] = [
            ProxyEndpoint(id="direct-local", tier=ProxyTier.datacenter, provider="direct", endpoint="", active=True),
            ProxyEndpoint(
                id="residential-slot",
                tier=ProxyTier.residential,
                provider="byo",
                endpoint=proxy_urls.get(ProxyTier.residential, ""),
                active=bool(proxy_urls.get(ProxyTier.residential, "")) or (self.use_residential_proxies and self.provider is not None),
            ),
            ProxyEndpoint(
                id="isp-static-slot",
                tier=ProxyTier.isp_static,
                provider="byo",
                endpoint=proxy_urls.get(ProxyTier.isp_static, ""),
                active=bool(proxy_urls.get(ProxyTier.isp_static, "")),
            ),
            ProxyEndpoint(
                id="datacenter-slot",
                tier=ProxyTier.datacenter,
                provider="byo",
                endpoint=proxy_urls.get(ProxyTier.datacenter, ""),
                active=bool(proxy_urls.get(ProxyTier.datacenter, "")),
            ),
            ProxyEndpoint(
                id="budget-res-slot",
                tier=ProxyTier.budget_residential,
                provider="byo",
                endpoint=proxy_urls.get(ProxyTier.budget_residential, ""),
                active=bool(proxy_urls.get(ProxyTier.budget_residential, "")),
            ),
        ]

    def choose(self, candidate: URLCandidate, strategy: str = "auto") -> ProxyEndpoint:
        if strategy == "none":
            return self.endpoints[0]
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
        
        # Sort key handles empty static endpoints when dynamic provider is active
        selected = sorted(
            pool,
            key=lambda proxy: (
                not (bool(proxy.endpoint) or (proxy.id == "residential-slot" and self.use_residential_proxies and self.provider is not None)),
                proxy.ban_rate,
                -proxy.success_rate
            )
        )[0]

        if self.use_residential_proxies and self.provider is not None and selected.id == "residential-slot":
            target_url = getattr(candidate, "url", "") if candidate else ""
            if not target_url or not isinstance(target_url, str):
                target_url = "https://example.com"
                
            try:
                dynamic_url = self.provider.get_endpoint(target_url)
                
                provider_name = "residential"
                if hasattr(self.provider, "preset") and self.provider.preset and getattr(self.provider.preset, "name", None):
                    provider_name = self.provider.preset.name
                elif getattr(self.provider, "name", None):
                    provider_name = self.provider.name

                return ProxyEndpoint(
                    id=selected.id,
                    tier=selected.tier,
                    provider=provider_name,
                    endpoint=dynamic_url,
                    active=selected.active,
                    ban_rate=selected.ban_rate,
                    success_rate=selected.success_rate,
                    cooldown_until=selected.cooldown_until,
                    last_error=selected.last_error,
                )
            except Exception as exc:
                logger.error("Failed to generate dynamic residential proxy URL for target %s: %s", target_url, exc)
                # Fall back to returning the static selected slot (or direct connection if static is empty)

        return selected

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
            
            # Invalidate session on block/failure
            if self.use_residential_proxies and self.provider is not None and proxy_id == "residential-slot":
                if blocked or not success:
                    try:
                        self.provider.rotate_all_sessions()
                        logger.info("Invalidated all residential proxy sticky sessions due to request block or failure")
                    except Exception as exc:
                        logger.warning("Failed to clear residential proxy sessions: %s", exc)
            return

    def _desired_tier(self, candidate: URLCandidate, strategy: str) -> ProxyTier:
        if strategy in {tier.value for tier in ProxyTier}:
            return ProxyTier(strategy)
        
        target_url = getattr(candidate, "url", "") if candidate else ""
        if not target_url or not isinstance(target_url, str):
            target_url = "https://example.com"
            
        host = urlparse(target_url).netloc.lower()
        
        # Safe attribute checks for candidate fields
        js_complexity_score = getattr(candidate, "js_complexity_score", 0.0)
        domain_ban_rate = getattr(candidate, "domain_ban_rate", 0.0)
        depth = getattr(candidate, "depth", 0)
        domain_yield_rate = getattr(candidate, "domain_yield_rate", 0.0)
        
        if "google.com" in host or js_complexity_score >= 0.75:
            return ProxyTier.residential
        if domain_ban_rate >= 0.25:
            return ProxyTier.isp_static
        if depth <= 1 and domain_yield_rate >= 0.55:
            return ProxyTier.datacenter
        return ProxyTier.budget_residential

    def _ema(self, old: float, new: float, weight: float) -> float:
        return round(max(0.0, min(1.0, old * (1 - weight) + new * weight)), 4)

    def state(self) -> dict[str, object]:
        state_dict = {
            "tiers": [tier.value for tier in ProxyTier],
            "tier_order": [tier.value for tier in self.tier_order],
            "endpoints": [endpoint.model_dump(mode="json") for endpoint in self.endpoints],
            "backoff": "exponential cooldown when ban_rate exceeds 0.40",
        }
        if getattr(self, "use_residential_proxies", False) and getattr(self, "provider", None) is not None:
            provider_name = "generic"
            if hasattr(self.provider, "preset") and self.provider.preset and getattr(self.provider.preset, "name", None):
                provider_name = self.provider.preset.name
                
            state_dict["active_provider"] = {
                "name": provider_name,
                "rotation_mode": getattr(self.provider, "rotation_mode", "sticky"),
                "country": getattr(self.provider, "country", ""),
                "region": getattr(self.provider, "region", ""),
                "sticky_sessions_count": getattr(self.provider, "active_sessions_count", 0),
            }
        return state_dict
