from __future__ import annotations

import asyncio


async def main() -> None:
    """Dedicated indexer placeholder for OpenSearch, Qdrant and Neo4j writes."""

    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
