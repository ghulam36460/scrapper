from __future__ import annotations

import asyncio

import httpx

from asagus.config import get_settings


async def main() -> None:
    settings = get_settings()
    payload = {
        "vectors": {
            "size": 384,
            "distance": "Cosine",
        }
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.put(f"{settings.qdrant_host.rstrip('/')}/collections/asagus_businesses", json=payload)
        response.raise_for_status()


if __name__ == "__main__":
    asyncio.run(main())
