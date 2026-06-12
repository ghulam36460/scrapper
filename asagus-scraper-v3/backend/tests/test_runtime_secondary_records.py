from __future__ import annotations

import asyncio
from collections import deque

from asagus.services.runtime import RuntimeState


def test_secondary_records_persist_from_deque(tmp_path) -> None:
    state = RuntimeState(tmp_path)

    asyncio.run(state.add_secondary_record({"url": "https://example.com", "status": "skipped"}))

    assert state.secondary_records_path.exists()
    assert list(state.secondary_records) == [{"url": "https://example.com", "status": "skipped"}]


def test_secondary_records_load_as_deque(tmp_path) -> None:
    path = tmp_path / "runtime_secondary_records.json"
    path.write_text(
        '{"records": [{"url": "https://example.com", "status": "stored"}]}',
        encoding="utf-8",
    )

    state = RuntimeState(tmp_path)

    assert isinstance(state.secondary_records, deque)
    asyncio.run(state.add_secondary_record({"url": "https://example.org", "status": "failed"}))
    assert len(state.secondary_records) == 2
