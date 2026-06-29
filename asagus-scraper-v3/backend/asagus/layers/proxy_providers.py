"""Residential proxy providers abstraction layer.

Allows registering and generating fully-authenticated proxy connection strings
for gateway residential proxy providers (Bright Data, Oxylabs, Smartproxy, etc.)
without changing the scraper or fetch layers.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import quote_plus


@dataclass
class ProviderPreset:
    """Preset settings for a known residential proxy provider."""
    name: str
    default_host: str
    default_port: int
    session_template: str = "-session-{session_id}"  # Template added to username
    country_template: str = "-country-{country}"
    region_template: str = "-region-{region}"
    default_scheme: str = "http"


# Presets for popular providers, using their official gateway configurations
PROVIDER_PRESETS: dict[str, ProviderPreset] = {
    "brightdata": ProviderPreset(
        name="brightdata",
        default_host="zproxy.lum-superproxy.io",
        default_port=22225,
        session_template="-session-{session_id}",
        country_template="-country-{country}",
        region_template="-region-{region}",
    ),
    "oxylabs": ProviderPreset(
        name="oxylabs",
        default_host="pr.oxylabs.io",
        default_port=7777,
        session_template="-session-{session_id}",
        country_template="-cc-{country}",
        region_template="",  # Oxylabs handles regions differently or via country codes
    ),
    "smartproxy": ProviderPreset(
        name="smartproxy",
        default_host="gate.smartproxy.com",
        default_port=7000,
        session_template="_session-{session_id}_lifetime-10m",
        country_template="-country-{country}",
        region_template="",
    ),
    "soax": ProviderPreset(
        name="soax",
        default_host="proxy.soax.com",
        default_port=9000,
        session_template="_session-{session_id}",
        country_template="-country-{country}",
        region_template="",
    ),
}


class BaseProxyProvider:
    """Abstract base class for all proxy providers."""

    def __init__(
        self,
        username: str = "",
        password: str = "",
        rotation_mode: Literal["sticky", "gateway"] = "sticky",
        sticky_duration: int = 900,
        country: str = "",
        region: str = "",
        host_override: str = "",
        port_override: int | None = None,
    ) -> None:
        self.username = username
        self.password = password
        self.rotation_mode = rotation_mode
        self.sticky_duration = max(30, sticky_duration)
        self.country = country.strip().lower()
        self.region = region.strip().lower()
        self.host_override = host_override.strip()
        self.port_override = port_override
        
        # Track active sticky sessions: domain -> (session_id, created_at)
        self._sticky_sessions: dict[str, tuple[str, float]] = {}

    def get_session_id(self, domain: str) -> str:
        """Get or generate a valid sticky session ID for the given domain."""
        now = time.time()
        domain = domain.lower().strip()
        
        if domain in self._sticky_sessions:
            session_id, created_at = self._sticky_sessions[domain]
            if now - created_at < self.sticky_duration:
                return session_id

        # Generate a fresh random/hashed session ID
        hash_input = f"{domain}-{now}-{hash(domain)}"
        session_id = hashlib.md5(hash_input.encode("utf-8")).hexdigest()[:12]
        self._sticky_sessions[domain] = (session_id, now)
        return session_id

    def invalidate_session(self, domain: str) -> None:
        """Invalidate the current sticky session for a domain to force an IP rotation."""
        domain = domain.lower().strip()
        self._sticky_sessions.pop(domain, None)

    def rotate_all_sessions(self) -> None:
        """Clear all active sticky sessions to force new IPs on subsequent requests."""
        self._sticky_sessions.clear()

    @property
    def active_sessions_count(self) -> int:
        """Get the number of currently active sticky sessions."""
        return len(self._sticky_sessions)

    def get_endpoint(self, url: str) -> str:
        """Generate a fully formatted and authenticated proxy URL for the target URL."""
        raise NotImplementedError


class GenericGatewayProvider(BaseProxyProvider):
    """Generic username-modifying gateway proxy provider.
    
    Handles Bright Data, Oxylabs, Smartproxy, SOAX, and any generic provider
    that accepts session IDs and geo targeting flags via username manipulation.
    """

    def __init__(
        self,
        preset: ProviderPreset | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        # Default fallback preset if none matched
        self.preset = preset or ProviderPreset(
            name="generic",
            default_host="localhost",
            default_port=8080,
            session_template="-session-{session_id}",
            country_template="-country-{country}",
            region_template="-region-{region}",
        )

    def get_endpoint(self, url: str) -> str:
        # 1. Resolve host and port
        host = self.host_override or self.preset.default_host
        port = self.port_override or self.preset.default_port

        if not self.username:
            # If no authentication is configured, return the raw gateway endpoint
            return f"{self.preset.default_scheme}://{host}:{port}"

        # 2. Extract domain from the target URL
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower().split(":", 1)[0] or "default"

        # 3. Construct modified username based on geo/session parameters
        modified_username = self.username

        if self.country and self.preset.country_template:
            # e.g., -country-us or -cc-us
            country_flag = self.preset.country_template.format(country=self.country)
            modified_username += country_flag

        if self.region and self.preset.region_template:
            # e.g., -region-ny
            region_flag = self.preset.region_template.format(region=self.region)
            modified_username += region_flag

        if self.rotation_mode == "sticky":
            session_id = self.get_session_id(domain)
            session_flag = self.preset.session_template.format(session_id=session_id)
            modified_username += session_flag

        # 4. URL encode user and pass safely
        encoded_user = quote_plus(modified_username)
        encoded_pass = quote_plus(self.password)

        return f"{self.preset.default_scheme}://{encoded_user}:{encoded_pass}@{host}:{port}"
