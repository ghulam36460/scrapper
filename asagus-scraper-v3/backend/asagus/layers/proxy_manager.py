"""
Proxy Integration with Residential IPs
=======================================
Manage residential proxy pools for IP rotation and geolocation matching.

Key Requirements from Requirements 14:
- Accept proxy URLs in format protocol://username:password@host:port
- Validate proxy connectivity before use
- Verify IP geolocation matches device timezone
- Rotate proxies after configurable interval
- Measure and avoid slow proxies
- Handle proxy failures with automatic rotation

Critical Insight from antibot.md Layer 3:
Even perfect stealth (Layer 2) and perfect TLS (Layer 3) fail if IP is from
datacenter ASN. Detection systems check:
- IP ASN (datacenter vs residential)
- IP geolocation vs declared timezone
- IP reputation and past behavior
- IP clustering (same IP across many devices)

Proxy Requirements:
★★★ Residential IPs (not datacenter)
★★ IP geo matches device timezone
★ IP rotation to avoid clustering
★ Fast response time (<3s threshold)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx


logger = logging.getLogger(__name__)


@dataclass
class ProxyInfo:
    """Information about a proxy."""
    url: str
    protocol: str
    host: str
    port: int
    username: str = ""
    password: str = ""
    
    # Performance metrics
    response_time_ms: float = 0.0
    success_count: int = 0
    failure_count: int = 0
    last_used: float = 0.0
    
    # Geolocation
    ip_address: str = ""
    country: str = ""
    city: str = ""
    timezone: str = ""
    
    # Status
    is_active: bool = True
    last_check: float = 0.0
    
    @classmethod
    def from_url(cls, url: str) -> ProxyInfo:
        """Parse proxy URL into ProxyInfo."""
        
        parsed = urlparse(url)
        
        return cls(
            url=url,
            protocol=parsed.scheme,
            host=parsed.hostname or "",
            port=parsed.port or 0,
            username=parsed.username or "",
            password=parsed.password or "",
        )
    
    def get_proxy_dict(self) -> dict[str, str]:
        """Get proxy dict for httpx/requests."""
        return {
            "http://": self.url,
            "https://": self.url,
        }
    
    def get_success_rate(self) -> float:
        """Calculate success rate percentage."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return (self.success_count / total) * 100


@dataclass
class ProxyPoolConfig:
    """Configuration for proxy pool management."""
    proxy_urls: list[str] = field(default_factory=list)
    rotation_interval_requests: int = 500  # Rotate after N requests
    response_time_threshold_seconds: float = 3.0  # Slow proxy threshold
    max_consecutive_failures: int = 3  # Deactivate after N failures
    health_check_interval_seconds: float = 300.0  # Check every 5 minutes
    verify_geolocation: bool = True
    require_residential: bool = True


class ProxyManager:
    """
    Manage residential proxy pool with rotation and health checking.
    
    Features:
    - Proxy pool management with rotation
    - Health checking and performance monitoring
    - Geolocation verification
    - Automatic failure handling
    - Statistics and reporting
    """
    
    def __init__(self, config: ProxyPoolConfig = ProxyPoolConfig()):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Proxy pool
        self.proxies: list[ProxyInfo] = []
        self.current_proxy_index = 0
        self.requests_since_rotation = 0
        
        # Load proxies from config
        for url in config.proxy_urls:
            proxy = ProxyInfo.from_url(url)
            self.proxies.append(proxy)
        
        self.logger.info(f"Initialized ProxyManager with {len(self.proxies)} proxies")
    
    async def get_next_proxy(self) -> ProxyInfo | None:
        """
        Get next proxy from pool with rotation.
        
        Returns:
            Next active proxy, or None if no proxies available
        """
        
        if not self.proxies:
            self.logger.warning("No proxies configured")
            return None
        
        # Check if rotation needed
        if self.requests_since_rotation >= self.config.rotation_interval_requests:
            await self.rotate_proxy()
        
        # Get current proxy
        active_proxies = [p for p in self.proxies if p.is_active]
        
        if not active_proxies:
            self.logger.error("No active proxies available")
            return None
        
        # Cycle through active proxies
        self.current_proxy_index = self.current_proxy_index % len(active_proxies)
        proxy = active_proxies[self.current_proxy_index]
        
        # Update usage
        proxy.last_used = time.time()
        self.requests_since_rotation += 1
        
        return proxy
    
    async def rotate_proxy(self) -> None:
        """Rotate to next proxy in pool."""
        
        active_proxies = [p for p in self.proxies if p.is_active]
        
        if len(active_proxies) <= 1:
            self.logger.warning("Cannot rotate - only 1 active proxy")
            return
        
        old_index = self.current_proxy_index
        self.current_proxy_index = (self.current_proxy_index + 1) % len(active_proxies)
        self.requests_since_rotation = 0
        
        self.logger.info(
            f"Rotated proxy from index {old_index} to {self.current_proxy_index}"
        )
    
    async def validate_proxy(self, proxy: ProxyInfo) -> bool:
        """
        Validate proxy connectivity and performance.
        
        Args:
            proxy: Proxy to validate
        
        Returns:
            True if proxy is valid and working
        """
        
        self.logger.info(f"Validating proxy {proxy.host}:{proxy.port}...")
        
        try:
            # Test connection
            start_time = time.time()
            
            async with httpx.AsyncClient(
                proxies=proxy.get_proxy_dict(),
                timeout=self.config.response_time_threshold_seconds
            ) as client:
                # Make test request
                response = await client.get("https://httpbin.org/ip")
                
                if response.status_code != 200:
                    self.logger.warning(f"Proxy validation failed: HTTP {response.status_code}")
                    return False
                
                # Measure response time
                proxy.response_time_ms = (time.time() - start_time) * 1000
                
                # Extract IP address
                data = response.json()
                proxy.ip_address = data.get("origin", "").split(",")[0].strip()
                
                self.logger.info(
                    f"Proxy valid: {proxy.ip_address} "
                    f"({proxy.response_time_ms:.0f}ms)"
                )
                
                # Optionally verify geolocation
                if self.config.verify_geolocation:
                    await self._fetch_geolocation(proxy)
                
                proxy.success_count += 1
                proxy.last_check = time.time()
                return True
        
        except asyncio.TimeoutError:
            self.logger.warning(f"Proxy timeout: {proxy.host}:{proxy.port}")
            proxy.failure_count += 1
            return False
        
        except Exception as e:
            self.logger.error(f"Proxy validation error: {e}")
            proxy.failure_count += 1
            return False
    
    async def _fetch_geolocation(self, proxy: ProxyInfo) -> None:
        """Fetch geolocation data for proxy IP."""
        
        try:
            async with httpx.AsyncClient(
                proxies=proxy.get_proxy_dict(),
                timeout=5.0
            ) as client:
                # Use ipapi.co for geolocation
                response = await client.get(f"https://ipapi.co/{proxy.ip_address}/json/")
                
                if response.status_code == 200:
                    data = response.json()
                    proxy.country = data.get("country_name", "")
                    proxy.city = data.get("city", "")
                    proxy.timezone = data.get("timezone", "")
                    
                    self.logger.info(
                        f"Proxy geolocation: {proxy.city}, {proxy.country} "
                        f"(TZ: {proxy.timezone})"
                    )
        
        except Exception as e:
            self.logger.debug(f"Geolocation fetch failed: {e}")
    
    async def verify_geolocation_match(
        self,
        proxy: ProxyInfo,
        expected_timezone: str
    ) -> bool:
        """
        Verify proxy IP geolocation matches expected timezone.
        
        Args:
            proxy: Proxy to check
            expected_timezone: Expected timezone (e.g., "America/New_York")
        
        Returns:
            True if geolocation matches
        """
        
        if not proxy.timezone:
            await self._fetch_geolocation(proxy)
        
        if proxy.timezone == expected_timezone:
            self.logger.info("✓ Proxy timezone matches device profile")
            return True
        else:
            self.logger.warning(
                f"✗ Proxy timezone mismatch: {proxy.timezone} != {expected_timezone}"
            )
            return False
    
    async def handle_proxy_failure(self, proxy: ProxyInfo) -> None:
        """
        Handle proxy failure - increment counter and deactivate if needed.
        
        Args:
            proxy: Proxy that failed
        """
        
        proxy.failure_count += 1
        
        # Check if consecutive failures exceed threshold
        consecutive_failures = proxy.failure_count
        if proxy.success_count > 0:
            # Reset if there were previous successes
            consecutive_failures = 1
        
        if consecutive_failures >= self.config.max_consecutive_failures:
            self.logger.warning(
                f"Deactivating proxy {proxy.host}:{proxy.port} after "
                f"{consecutive_failures} consecutive failures"
            )
            proxy.is_active = False
            
            # Rotate to next proxy
            await self.rotate_proxy()
    
    async def handle_proxy_success(self, proxy: ProxyInfo, response_time_ms: float) -> None:
        """
        Handle successful proxy request.
        
        Args:
            proxy: Proxy that succeeded
            response_time_ms: Response time in milliseconds
        """
        
        proxy.success_count += 1
        proxy.response_time_ms = response_time_ms
        proxy.last_used = time.time()
        
        # Check if response time is too slow
        if response_time_ms > (self.config.response_time_threshold_seconds * 1000):
            self.logger.warning(
                f"Proxy slow ({response_time_ms:.0f}ms): {proxy.host}:{proxy.port}"
            )
            # Could optionally rotate to faster proxy
    
    async def health_check_all(self) -> None:
        """Run health check on all proxies."""
        
        self.logger.info("Running health check on all proxies...")
        
        for proxy in self.proxies:
            # Skip if recently checked
            if (time.time() - proxy.last_check) < self.config.health_check_interval_seconds:
                continue
            
            is_valid = await self.validate_proxy(proxy)
            
            if not is_valid:
                await self.handle_proxy_failure(proxy)
            
            # Small delay between checks
            await asyncio.sleep(0.5)
    
    def get_statistics(self) -> dict[str, Any]:
        """Get proxy pool statistics."""
        
        active_count = sum(1 for p in self.proxies if p.is_active)
        total_requests = sum(p.success_count + p.failure_count for p in self.proxies)
        avg_response_time = 0.0
        
        if self.proxies:
            response_times = [p.response_time_ms for p in self.proxies if p.response_time_ms > 0]
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
        
        return {
            "total_proxies": len(self.proxies),
            "active_proxies": active_count,
            "inactive_proxies": len(self.proxies) - active_count,
            "total_requests": total_requests,
            "current_proxy_index": self.current_proxy_index,
            "requests_since_rotation": self.requests_since_rotation,
            "avg_response_time_ms": round(avg_response_time, 2),
            "proxies": [
                {
                    "host": p.host,
                    "port": p.port,
                    "ip": p.ip_address,
                    "country": p.country,
                    "city": p.city,
                    "timezone": p.timezone,
                    "success_rate": round(p.get_success_rate(), 2),
                    "response_time_ms": round(p.response_time_ms, 2),
                    "is_active": p.is_active,
                }
                for p in self.proxies
            ]
        }
    
    def add_proxy(self, proxy_url: str) -> None:
        """Add new proxy to pool."""
        
        proxy = ProxyInfo.from_url(proxy_url)
        self.proxies.append(proxy)
        self.logger.info(f"Added proxy: {proxy.host}:{proxy.port}")
    
    def remove_proxy(self, proxy_url: str) -> None:
        """Remove proxy from pool."""
        
        self.proxies = [p for p in self.proxies if p.url != proxy_url]
        self.logger.info(f"Removed proxy: {proxy_url}")


async def create_proxy_manager(proxy_urls: list[str]) -> ProxyManager:
    """
    Create and initialize proxy manager.
    
    Args:
        proxy_urls: List of proxy URLs
    
    Returns:
        Initialized ProxyManager
    """
    
    config = ProxyPoolConfig(proxy_urls=proxy_urls)
    manager = ProxyManager(config)
    
    # Validate all proxies
    for proxy in manager.proxies:
        await manager.validate_proxy(proxy)
    
    return manager
