from __future__ import annotations

import asyncio
import logging

from asagus.config import get_settings


logger = logging.getLogger(__name__)


async def main() -> None:
    """Validate dedicated-indexer mode.

    Indexing currently happens from the API pipeline when infra persistence is
    enabled. This command exits loudly instead of running an infinite no-op loop.
    """
    settings = get_settings()
    if not settings.enable_infra_persistence:
        logger.warning("Indexer worker disabled: ENABLE_INFRA_PERSISTENCE=false; indexing stays local-only.")
        return

    raise NotImplementedError(
        "Dedicated Redis/OpenSearch/Qdrant indexer workers are not implemented in the active runtime. "
        "Use the API pipeline indexing path, or implement a real queue consumer before enabling this worker."
    )


if __name__ == "__main__":
    asyncio.run(main())
