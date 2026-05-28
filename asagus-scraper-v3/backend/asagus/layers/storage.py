from __future__ import annotations

from asagus.models import EnrichedRecord
from asagus.services.runtime import RuntimeState


class StorageLayer:
    """Primary persistence facade.

    The local implementation writes to RuntimeState; production adapters should
    write raw HTML to MinIO, structured records to Postgres, and graph edges to
    Neo4j per the blueprint.
    """

    def __init__(self, runtime: RuntimeState) -> None:
        self.runtime = runtime

    async def store_record(self, record: EnrichedRecord) -> tuple[EnrichedRecord, bool, list[str]]:
        return await self.runtime.add_record(record)
