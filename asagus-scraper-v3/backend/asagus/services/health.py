from __future__ import annotations

import asyncio
import time

import httpx

from asagus.config import Settings
from asagus.models import SystemHealth


_health_cache: tuple[float, tuple[object, ...], SystemHealth] | None = None


async def collect_health(settings: Settings) -> SystemHealth:
    global _health_cache
    now = time.monotonic()
    cache_key = (
        settings.enable_infra_persistence,
        settings.enable_network_fetch,
        settings.enable_search_discovery,
        settings.postgres_url,
        settings.redis_url,
        settings.opensearch_host,
        settings.qdrant_host,
        settings.minio_endpoint,
    )
    if _health_cache and _health_cache[1] == cache_key and now - _health_cache[0] < 10:
        return _health_cache[2]

    services: dict[str, str] = {}

    def local_optional(value: str) -> str:
        if settings.environment == "local" and value in {"unreachable", "degraded"}:
            return f"optional_{value}"
        return value

    def with_scheme(endpoint: str) -> str:
        if endpoint.startswith(("http://", "https://")):
            return endpoint
        return f"http://{endpoint}"

    async def probe_http(name: str, url: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=0.7) as client:
                response = await client.get(url)
            services[name] = local_optional("ok" if response.status_code < 500 else "degraded")
        except Exception:
            services[name] = local_optional("unreachable")

    async def probe_postgres() -> None:
        try:
            import asyncpg

            conn = await asyncpg.connect(settings.postgres_url, timeout=0.7)
            try:
                await conn.execute("SELECT 1")
            finally:
                await conn.close()
            services["postgres"] = "ok"
        except Exception:
            services["postgres"] = local_optional("unreachable")

    async def probe_redis() -> None:
        try:
            import redis.asyncio as redis

            client = redis.from_url(settings.redis_url, socket_connect_timeout=0.7, socket_timeout=0.7)
            try:
                await client.ping()
            finally:
                await client.aclose()
            services["redis"] = "ok"
        except Exception:
            services["redis"] = local_optional("unreachable")

    if settings.enable_infra_persistence:
        await asyncio.gather(
            probe_http("opensearch", settings.opensearch_host),
            probe_http("qdrant", f"{settings.qdrant_host}/healthz"),
            probe_http("minio", f"{with_scheme(settings.minio_endpoint).rstrip('/')}/minio/health/live"),
            probe_postgres(),
            probe_redis(),
        )
        services.setdefault("neo4j", "optional")
    else:
        services.update(
            {
                "postgres": "disabled",
                "redis": "disabled",
                "opensearch": "disabled",
                "qdrant": "disabled",
                "minio": "disabled",
                "neo4j": "disabled",
            }
        )
    services["network_fetch"] = "enabled" if settings.enable_network_fetch else "disabled"
    services["search_discovery"] = "enabled" if settings.enable_search_discovery else "disabled"

    status = "ok"
    if any(value in {"unreachable", "degraded"} for value in services.values()):
        status = "degraded"
    health = SystemHealth(status=status, services=services)
    _health_cache = (now, cache_key, health)
    return health
