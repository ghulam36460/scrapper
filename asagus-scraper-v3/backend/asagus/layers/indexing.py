from __future__ import annotations

import hashlib
import math

import httpx

from asagus.config import Settings
from asagus.models import EnrichedRecord


class IndexingLayer:
    """BM25 + dense + graph indexing facade."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings

    async def index(self, record: EnrichedRecord) -> dict[str, str]:
        result = {
            "record_id": record.id,
            "bm25": "local_only",
            "dense": "local_only",
            "graph": "local_candidate",
        }
        if not self.settings or not self.settings.enable_infra_persistence:
            return result
        result["bm25"] = await self._index_opensearch(record)
        result["dense"] = await self._index_qdrant(record)
        result["graph"] = await self._index_neo4j(record)
        return result

    async def _index_opensearch(self, record: EnrichedRecord) -> str:
        if not self.settings:
            return "not_configured"
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                await client.put(
                    f"{self.settings.opensearch_host.rstrip('/')}/asagus-records",
                    json={
                        "settings": {"index": {"number_of_shards": 1, "number_of_replicas": 0}},
                        "mappings": {"properties": {"payload": {"type": "object", "enabled": True}}},
                    },
                )
                response = await client.put(
                    f"{self.settings.opensearch_host.rstrip('/')}/asagus-records/_doc/{record.id}",
                    json=self._document(record),
                )
            return "indexed" if response.status_code < 400 else f"degraded:{response.status_code}"
        except Exception:
            return "unreachable"

    async def _index_qdrant(self, record: EnrichedRecord) -> str:
        if not self.settings:
            return "not_configured"
        collection = "asagus_records"
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                await client.put(
                    f"{self.settings.qdrant_host.rstrip('/')}/collections/{collection}",
                    json={"vectors": {"size": 64, "distance": "Cosine"}},
                )
                response = await client.put(
                    f"{self.settings.qdrant_host.rstrip('/')}/collections/{collection}/points?wait=true",
                    json={
                        "points": [
                            {
                                "id": record.id,
                                "vector": self._vector(record),
                                "payload": self._document(record),
                            }
                        ]
                    },
                )
            return "indexed" if response.status_code < 400 else f"degraded:{response.status_code}"
        except Exception:
            return "unreachable"

    async def _index_neo4j(self, record: EnrichedRecord) -> str:
        if not self.settings:
            return "not_configured"
        try:
            from neo4j import AsyncGraphDatabase

            driver = AsyncGraphDatabase.driver(
                self.settings.neo4j_uri,
                auth=(self.settings.neo4j_user, self.settings.neo4j_password),
            )
            try:
                async with driver.session() as session:
                    await session.run(
                        """
                        MERGE (r:Record {id: $id})
                        SET r.name = $name,
                            r.city = $city,
                            r.category = $category,
                            r.source_url = $source_url,
                            r.updated_at = datetime()
                        """,
                        id=record.id,
                        name=record.name,
                        city=record.city,
                        category=record.category,
                        source_url=record.source_url,
                    )
            finally:
                await driver.close()
            return "indexed"
        except Exception:
            return "unreachable"

    def _document(self, record: EnrichedRecord) -> dict[str, object]:
        return {
            "id": record.id,
            "name": record.name,
            "category": record.category,
            "city": record.city,
            "address": record.address,
            "email": record.email,
            "phone": record.phone,
            "website_url": record.website_url,
            "source_url": record.source_url,
            "entity_tags": record.entity_tags,
            "payload": record.model_dump(mode="json"),
        }

    def _vector(self, record: EnrichedRecord, dimensions: int = 64) -> list[float]:
        vector = [0.0] * dimensions
        text = " ".join([record.name, record.category, record.city, record.address, " ".join(record.entity_tags)])
        for token in text.lower().split():
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]
