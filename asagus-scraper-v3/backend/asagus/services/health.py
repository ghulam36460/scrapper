from __future__ import annotations

import asyncio
import time

import httpx

from asagus.config import Settings
from asagus.models import SystemHealth


_health_cache: tuple[float, SystemHealth] | None = None


async def collect_health(settings: Settings) -> SystemHealth:
    global _health_cache
    now = time.monotonic()
    if _health_cache and now - _health_cache[0] < 10:
        return _health_cache[1]

    services: dict[str, str] = {}

    async def probe_http(name: str, url: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=0.7) as client:
                response = await client.get(url)
            services[name] = "ok" if response.status_code < 500 else "degraded"
        except Exception:
            services[name] = "unreachable"

    await asyncio.gather(
        probe_http("opensearch", settings.opensearch_host),
        probe_http("qdrant", f"{settings.qdrant_host}/healthz"),
    )

    services.setdefault("postgres", "configured")
    services.setdefault("redis", "configured")
    services.setdefault("minio", "configured")
    services.setdefault("neo4j", "optional")
    services["network_fetch"] = "enabled" if settings.enable_network_fetch else "disabled"
    services["search_discovery"] = "enabled" if settings.enable_search_discovery else "disabled"

    status = "ok"
    if any(value == "unreachable" for value in services.values()):
        status = "degraded"
    if not settings.enable_network_fetch or not settings.enable_search_discovery:
        status = "degraded"
    health = SystemHealth(status=status, services=services)
    _health_cache = (now, health)
    return health
