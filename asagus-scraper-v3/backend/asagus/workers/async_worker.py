from __future__ import annotations

import asyncio


async def main() -> None:
    """Async worker placeholder.

    Production mode consumes Redis Streams:
    frontier_stream -> fetch_complete -> extract_complete -> enrich_complete.
    The API currently runs a local in-process pipeline for first-run usability.
    """

    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
