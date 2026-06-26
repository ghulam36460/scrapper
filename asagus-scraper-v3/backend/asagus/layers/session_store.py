"""Per-domain browser session (cookie) store for challenge avoidance.

When a stealth browser successfully passes a Cloudflare / DataDome style
interstitial, the response sets clearance cookies (e.g. ``cf_clearance``,
``__cf_bm``, ``datadome``). Re-sending those cookies on subsequent requests
to the *same domain* lets us skip the challenge entirely, which is the whole
point of the avoidance ladder: solve the interstitial once, reuse the result.

This module persists Playwright ``storage_state`` JSON per domain on disk
with a TTL, so sessions survive across requests and process restarts. It is
deliberately framework-agnostic about *how* the state was obtained; it only
stores and serves the JSON blob.

Follows the database-patterns / performance-optimization SKILLs: cheap local
cache, no globals (the store is injected), and safe concurrent access.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Cookies that signal a passed bot-challenge; their presence makes a session
# worth persisting and reusing.
CLEARANCE_COOKIE_NAMES = frozenset(
    {
        "cf_clearance",
        "__cf_bm",
        "datadome",
        "datadome-cookie",
        "_px3",
        "_pxvid",
        "ak_bmsc",
        "incap_ses",
        "visid_incap",
    }
)


def domain_of(url: str) -> str:
    """Return the lowercase registrable host for ``url`` (no port)."""
    host = urlparse(url).netloc.lower()
    return host.split(":", 1)[0] if host else ""


def _safe_filename(domain: str) -> str:
    """Map a domain to a filesystem-safe filename."""
    return "".join(ch if ch.isalnum() or ch in {".", "-", "_"} else "_" for ch in domain)


class SessionStore:
    """Disk-backed, TTL'd store of Playwright ``storage_state`` per domain.

    Args:
        sessions_dir: Directory where ``<domain>.json`` files are written.
        ttl_seconds: How long a stored session stays valid. Cloudflare's
            ``cf_clearance`` typically lasts ~30 minutes, so the default is
            conservative.
    """

    def __init__(self, sessions_dir: str | Path, ttl_seconds: int = 1500) -> None:
        self.sessions_dir = Path(sessions_dir)
        self.ttl_seconds = max(60, int(ttl_seconds))
        self._locks: dict[str, asyncio.Lock] = {}
        try:
            self.sessions_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:  # pragma: no cover - environment dependent
            logger.warning("Could not create session dir %s: %s", self.sessions_dir, exc)

    def _lock_for(self, domain: str) -> asyncio.Lock:
        lock = self._locks.get(domain)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[domain] = lock
        return lock

    def _path_for(self, domain: str) -> Path:
        return self.sessions_dir / f"{_safe_filename(domain)}.json"

    @staticmethod
    def has_clearance_cookies(storage_state: dict) -> bool:
        """True if ``storage_state`` carries any known challenge-clearance cookie."""
        for cookie in storage_state.get("cookies", []) or []:
            if cookie.get("name") in CLEARANCE_COOKIE_NAMES:
                return True
        return False

    async def path_if_valid(self, url: str) -> str:
        """Return a filesystem path to a fresh session for ``url`` or "".

        Playwright accepts ``storage_state`` as a file path, so this returns
        the path (not the parsed JSON) when a non-expired session exists.
        """
        domain = domain_of(url)
        if not domain:
            return ""
        path = self._path_for(domain)
        async with self._lock_for(domain):
            if not path.exists():
                return ""
            age = time.time() - path.stat().st_mtime
            if age > self.ttl_seconds:
                logger.debug("Session for %s expired (age %.0fs > ttl %ds)", domain, age, self.ttl_seconds)
                return ""
            return str(path)

    async def save(self, url: str, storage_state: dict, *, require_clearance: bool = True) -> bool:
        """Persist ``storage_state`` for the domain of ``url``.

        Args:
            url: Any URL on the target domain.
            storage_state: Playwright ``context.storage_state()`` dict.
            require_clearance: When True, only persist sessions that actually
                contain a challenge-clearance cookie (avoids caching useless,
                empty sessions). Set False to always persist.

        Returns:
            True if the session was written, False otherwise.
        """
        domain = domain_of(url)
        if not domain or not isinstance(storage_state, dict):
            return False
        if require_clearance and not self.has_clearance_cookies(storage_state):
            return False
        path = self._path_for(domain)
        async with self._lock_for(domain):
            try:
                path.write_text(json.dumps(storage_state), encoding="utf-8")
            except OSError as exc:  # pragma: no cover - environment dependent
                logger.warning("Failed to persist session for %s: %s", domain, exc)
                return False
        logger.info("Saved reusable browser session for %s", domain)
        return True

    async def invalidate(self, url: str) -> None:
        """Delete a stored session (e.g. after it stops passing challenges)."""
        domain = domain_of(url)
        if not domain:
            return
        path = self._path_for(domain)
        async with self._lock_for(domain):
            try:
                path.unlink(missing_ok=True)
            except OSError:  # pragma: no cover
                pass
        logger.debug("Invalidated session for %s", domain)

    def state(self) -> dict[str, object]:
        """Diagnostics snapshot for API/UI."""
        try:
            count = len(list(self.sessions_dir.glob("*.json")))
        except OSError:
            count = 0
        return {
            "sessions_dir": str(self.sessions_dir),
            "ttl_seconds": self.ttl_seconds,
            "stored_sessions": count,
            "purpose": "reuse passed-challenge cookies per domain to avoid repeat challenges",
        }
