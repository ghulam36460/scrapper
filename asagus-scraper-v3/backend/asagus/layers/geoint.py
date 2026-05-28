from __future__ import annotations

import math
from collections import defaultdict

from asagus.models import EnrichedRecord


class GeospatialIntelligenceLayer:
    """GEOINT utilities for business records."""

    def distance_km(self, left: EnrichedRecord, right: EnrichedRecord) -> float | None:
        if left.lat is None or left.lng is None or right.lat is None or right.lng is None:
            return None
        return round(self.haversine(left.lat, left.lng, right.lat, right.lng), 3)

    def clusters(self, records: list[EnrichedRecord]) -> list[dict[str, object]]:
        grouped: dict[str, list[EnrichedRecord]] = defaultdict(list)
        for record in records:
            key = record.normalized_area or record.city or "unknown"
            grouped[key].append(record)
        return [
            {
                "area": area,
                "count": len(rows),
                "categories": sorted({row.category for row in rows if row.category}),
                "avg_completeness": round(sum(row.record_completeness for row in rows) / len(rows), 3),
            }
            for area, rows in sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True)
        ]

    def proximity_duplicates(self, records: list[EnrichedRecord], radius_km: float = 0.15) -> list[dict[str, object]]:
        out = []
        for index, left in enumerate(records):
            for right in records[index + 1 :]:
                distance = self.distance_km(left, right)
                if distance is not None and distance <= radius_km and left.name and left.name.lower() == right.name.lower():
                    out.append({"left_id": left.id, "right_id": right.id, "distance_km": distance, "reason": "same_name_nearby"})
        return out

    def haversine(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        radius = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
        return 2 * radius * math.asin(math.sqrt(a))

    def state(self) -> dict[str, object]:
        return {
            "implemented": ["haversine_distance", "area_clusters", "proximity_duplicate_detection"],
            "adapter_ready": ["geocoding", "isochrones", "heatmaps"],
        }
