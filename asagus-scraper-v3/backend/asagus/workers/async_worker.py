from __future__ import annotations

import asyncio
import logging

from asagus.config import get_settings


logger = logging.getLogger(__name__)


async def main() -> None:
    """Validate async-worker mode.

    The active API runner is still intentionally in-process. This command now
    exits loudly instead of running an infinite no-op loop that looks healthy.
    """
    settings = get_settings()
    if not settings.enable_infra_persistence:
        logger.warning("Async worker disabled: ENABLE_INFRA_PERSISTENCE=false; jobs run in the API process.")
        return

    raise NotImplementedError(
        "Redis Streams job workers are not implemented in the active runtime. "
        "Use the FastAPI in-process job runner, or implement a real stream consumer before enabling this worker."
    )


if __name__ == "__main__":
    asyncio.run(main())
