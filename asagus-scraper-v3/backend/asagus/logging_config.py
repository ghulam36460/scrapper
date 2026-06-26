"""Centralized logging configuration for the ASAGUS backend.

Keeping logging setup in a single module follows the scraper-architecture
SKILL ("Always log actions using a logger module, not print statements")
and ensures every layer's ``logging.getLogger(__name__)`` logger actually
emits records through a consistent handler and format.
"""

from __future__ import annotations

import logging

_CONFIGURED = False

_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging once for the whole application.

    Idempotent: calling it more than once (e.g. in tests or reloads) will
    not stack duplicate handlers.

    Args:
        level: Logging level name (e.g. ``"INFO"``, ``"DEBUG"``).
    """
    global _CONFIGURED

    resolved_level = logging.getLevelName(level.upper())
    if not isinstance(resolved_level, int):
        resolved_level = logging.INFO

    if _CONFIGURED:
        logging.getLogger().setLevel(resolved_level)
        return

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))

    root_logger = logging.getLogger()
    root_logger.setLevel(resolved_level)
    root_logger.addHandler(handler)

    _CONFIGURED = True
