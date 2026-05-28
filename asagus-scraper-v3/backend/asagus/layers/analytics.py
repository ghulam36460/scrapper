from __future__ import annotations

import math
from collections import Counter, defaultdict

from asagus.models import EnrichedRecord


class PredictiveAnalyticsLayer:
    """Predictive quality scoring, anomaly detection and simple trend features."""

    def lead_score(self, record: EnrichedRecord) -> float:
        contact = 0.25 if record.email or record.phone or record.whatsapp else 0.0
        website = 0.12 if record.website_url else 0.0
        category = 0.10 if record.category else 0.0
        geo = 0.08 if record.city or (record.lat is not None and record.lng is not None) else 0.0
        compliance_penalty = 0.08 if record.gdpr_flag or record.pdpa_flag else 0.0
        duplicate_penalty = record.duplicate_score * 0.25
        value = record.record_completeness * 0.35 + record.confidence * 0.25 + contact + website + category + geo
        return round(max(0.0, min(1.0, value - compliance_penalty - duplicate_penalty)), 3)

    def anomalies(self, records: list[EnrichedRecord]) -> list[dict[str, object]]:
        scores = [self.lead_score(record) for record in records]
        if not scores:
            return []
        mean = sum(scores) / len(scores)
        variance = sum((score - mean) ** 2 for score in scores) / max(len(scores), 1)
        std = math.sqrt(variance) or 1.0
        out = []
        for record, score in zip(records, scores):
            z = (score - mean) / std
            if abs(z) >= 1.8 or record.duplicate_score >= 0.9:
                out.append(
                    {
                        "record_id": record.id,
                        "name": record.name,
                        "lead_score": score,
                        "z_score": round(z, 3),
                        "reason": "duplicate_risk" if record.duplicate_score >= 0.9 else "score_outlier",
                    }
                )
        return out

    def market_summary(self, records: list[EnrichedRecord]) -> dict[str, object]:
        by_city: Counter[str] = Counter(record.city or "unknown" for record in records)
        by_category: Counter[str] = Counter(record.category or "unknown" for record in records)
        quality_by_city: dict[str, list[float]] = defaultdict(list)
        for record in records:
            quality_by_city[record.city or "unknown"].append(self.lead_score(record))
        return {
            "cities": by_city.most_common(10),
            "categories": by_category.most_common(10),
            "avg_quality_by_city": {
                city: round(sum(values) / len(values), 3)
                for city, values in quality_by_city.items()
            },
        }

    def state(self) -> dict[str, object]:
        return {
            "implemented": ["lead_quality_prediction", "z_score_anomaly_detection", "market_summary"],
            "adapter_ready": ["isolation_forest", "forecasting", "causal_uplift"],
        }
