from __future__ import annotations

from asagus.models import EnrichedRecord


class IndexingLayer:
    """BM25 + dense + graph indexing facade."""

    async def index(self, record: EnrichedRecord) -> dict[str, str]:
        # Production: OpenSearch, Qdrant and Neo4j writes happen here.
        return {
            "record_id": record.id,
            "bm25": "queued",
            "dense": "queued",
            "graph": "candidate",
        }
