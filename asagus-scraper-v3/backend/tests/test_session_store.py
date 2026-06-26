"""Unit tests for the per-domain browser SessionStore.

Uses a temporary directory (no real browser) and drives the async API with
asyncio.run, matching the project's existing test style.
"""

from __future__ import annotations

import asyncio
import time

from asagus.layers.session_store import SessionStore, domain_of


def _state_with_cookie(name: str = "cf_clearance") -> dict:
    return {"cookies": [{"name": name, "value": "abc", "domain": ".example.com"}], "origins": []}


def test_domain_of_strips_scheme_and_port() -> None:
    assert domain_of("https://Shop.Example.com:443/path") == "shop.example.com"
    assert domain_of("not a url") == ""


def test_has_clearance_cookies() -> None:
    assert SessionStore.has_clearance_cookies(_state_with_cookie("cf_clearance")) is True
    assert SessionStore.has_clearance_cookies(_state_with_cookie("session_id")) is False
    assert SessionStore.has_clearance_cookies({"cookies": []}) is False


def test_save_and_reload_valid_session(tmp_path) -> None:
    store = SessionStore(tmp_path, ttl_seconds=600)
    saved = asyncio.run(store.save("https://example.com/a", _state_with_cookie()))
    assert saved is True
    path = asyncio.run(store.path_if_valid("https://example.com/other"))
    assert path  # same domain returns the stored session path


def test_session_without_clearance_is_not_saved_by_default(tmp_path) -> None:
    store = SessionStore(tmp_path)
    saved = asyncio.run(store.save("https://example.com", _state_with_cookie("plain_cookie")))
    assert saved is False
    assert asyncio.run(store.path_if_valid("https://example.com")) == ""


def test_session_without_clearance_saved_when_not_required(tmp_path) -> None:
    store = SessionStore(tmp_path)
    saved = asyncio.run(
        store.save("https://example.com", _state_with_cookie("plain_cookie"), require_clearance=False)
    )
    assert saved is True


def test_expired_session_is_ignored(tmp_path) -> None:
    store = SessionStore(tmp_path, ttl_seconds=60)
    asyncio.run(store.save("https://example.com", _state_with_cookie()))
    # Backdate the file beyond the TTL.
    session_file = next(tmp_path.glob("*.json"))
    old = time.time() - 120
    import os

    os.utime(session_file, (old, old))
    assert asyncio.run(store.path_if_valid("https://example.com")) == ""


def test_invalidate_removes_session(tmp_path) -> None:
    store = SessionStore(tmp_path)
    asyncio.run(store.save("https://example.com", _state_with_cookie()))
    asyncio.run(store.invalidate("https://example.com"))
    assert asyncio.run(store.path_if_valid("https://example.com")) == ""


def test_state_reports_counts(tmp_path) -> None:
    store = SessionStore(tmp_path, ttl_seconds=300)
    asyncio.run(store.save("https://a.com", _state_with_cookie()))
    asyncio.run(store.save("https://b.com", _state_with_cookie()))
    snapshot = store.state()
    assert snapshot["stored_sessions"] == 2
    assert snapshot["ttl_seconds"] == 300
