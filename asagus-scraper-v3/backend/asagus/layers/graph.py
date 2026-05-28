from __future__ import annotations

from urllib.parse import urlparse

from asagus.models import EnrichedRecord, RelationshipCandidate, RelationshipType


class GraphRelationshipEngine:
    """Layer 6/9 graph candidate logic for Neo4j materialization."""

    def candidates_for(self, record: EnrichedRecord, existing: list[EnrichedRecord]) -> list[RelationshipCandidate]:
        candidates: list[RelationshipCandidate] = []
        for other in existing:
            if other.id == record.id:
                continue
            candidates.extend(self._pair(record, other))
        return candidates

    def _pair(self, left: EnrichedRecord, right: EnrichedRecord) -> list[RelationshipCandidate]:
        out: list[RelationshipCandidate] = []
        if self._same_phone_or_site(left, right):
            out.append(self._candidate(left, right, RelationshipType.duplicate_of, 0.96, ["phone_or_site_exact"]))
        if left.category and left.category == right.category and left.city and left.city == right.city and left.id != right.id:
            out.append(self._candidate(left, right, RelationshipType.competitor, 0.72, ["same_category", "same_city"]))
            out.append(self._candidate(left, right, RelationshipType.same_area, 0.80, ["same_city"]))
        if self._domain(left.website_url) and self._domain(left.website_url) == self._domain(right.website_url):
            out.append(self._candidate(left, right, RelationshipType.same_network, 0.90, ["website_domain_match"]))
        if right.website_url and right.website_url.lower() in str(left.raw_fields).lower():
            out.append(self._candidate(left, right, RelationshipType.links_to, 0.76, ["source_mentions_target_url"]))
        if right.name and right.name.lower() in str(left.raw_fields).lower():
            out.append(self._candidate(left, right, RelationshipType.mentions, 0.68, ["source_mentions_target_name"]))
        return out

    def _candidate(
        self,
        left: EnrichedRecord,
        right: EnrichedRecord,
        relationship: RelationshipType,
        confidence: float,
        evidence: list[str],
    ) -> RelationshipCandidate:
        return RelationshipCandidate(
            source_record_id=left.id,
            target_record_id=right.id,
            relationship=relationship,
            confidence=confidence,
            evidence=evidence,
        )

    def _same_phone_or_site(self, left: EnrichedRecord, right: EnrichedRecord) -> bool:
        return bool(
            (left.phone and right.phone and left.phone == right.phone)
            or (
                left.website_url
                and right.website_url
                and self._domain(left.website_url)
                and self._domain(left.website_url) == self._domain(right.website_url)
            )
        )

    def _domain(self, url: str) -> str:
        if not url:
            return ""
        return urlparse(url if "://" in url else f"https://{url}").netloc.lower().removeprefix("www.")

    def state(self) -> dict[str, object]:
        return {
            "relationships": [relationship.value for relationship in RelationshipType],
            "thresholds": {
                "DUPLICATE_OF": 0.95,
                "SAME_NETWORK": 0.90,
                "SAME_AREA": 0.80,
                "LINKS_TO": 0.76,
                "COMPETITOR": 0.72,
                "MENTIONS": 0.68,
            },
        }
