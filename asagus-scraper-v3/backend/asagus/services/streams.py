from __future__ import annotations

from typing import Any


STREAMS = {
    "frontier": "frontier_stream",
    "fetch_complete": "fetch_complete",
    "extract_complete": "extract_complete",
    "enrich_complete": "enrich_complete",
    "index_queue": "index_queue",
    "policy_feedback": "policy_feedback",
}


class StreamBus:
    """Redis Streams facade with a no-op fallback for local development."""

    def __init__(self, redis_url: str, enabled: bool = False) -> None:
        self.redis_url = redis_url
        self.enabled = enabled

    async def publish(self, stream: str, message: dict[str, Any]) -> str:
        if not self.enabled:
            return "local-noop"
        try:
            import redis.asyncio as redis

            client = redis.from_url(self.redis_url, decode_responses=True)
            message_id = await client.xadd(STREAMS[stream], message)
            await client.aclose()
            return str(message_id)
        except Exception:
            return "local-fallback"
