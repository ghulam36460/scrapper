from __future__ import annotations

from asagus.models import ObservabilityMetric, ScrapeJob


class ObservabilityLayer:
    """Layer-wide metrics named in the architecture document."""

    metric_catalog = [
        ("crawl_throughput_per_min", "targets/min", "Processed crawl targets per minute"),
        ("policy_rule_hit_rate", "%", "Share of decisions handled by deterministic rules"),
        ("llm_call_percent", "%", "Share of pages routed to LLM extraction"),
        ("redis_stream_lag", "messages", "Pending Redis Stream messages"),
        ("proxy_ban_rate", "%", "Proxy requests ending in block or ban"),
        ("extraction_confidence_avg", "%", "Average extraction confidence"),
        ("db_pool_usage", "%", "Postgres pool utilization"),
        ("qdrant_pending_vectors", "vectors", "Vectors queued for Qdrant"),
        ("worker_memory_mb", "MB", "Worker memory footprint"),
        ("end_to_end_latency_ms", "ms", "Job end-to-end latency"),
    ]

    def from_runtime(self, jobs: list[ScrapeJob], policy_stats: dict[str, object]) -> list[ObservabilityMetric]:
        processed = sum(job.processed_targets for job in jobs)
        llm_calls = sum(job.llm_calls for job in jobs)
        renders = sum(job.browser_renders for job in jobs)
        rule_hits = float(policy_stats.get("rule_layer_hits", 0) or 0)
        bayes_hits = float(policy_stats.get("bayesian_hits", 0) or 0)
        decisions = max(rule_hits + bayes_hits, 1.0)
        return [
            ObservabilityMetric(name="crawl_throughput_per_min", value=float(processed), unit="targets", description="Local processed target count"),
            ObservabilityMetric(name="policy_rule_hit_rate", value=round(rule_hits / decisions * 100, 2), unit="%", description="Rule-layer hit rate"),
            ObservabilityMetric(name="llm_call_percent", value=round(llm_calls / max(processed, 1) * 100, 2), unit="%", description="LLM fallback usage"),
            ObservabilityMetric(name="redis_stream_lag", value=0, unit="messages", description="Memory runtime has no Redis lag"),
            ObservabilityMetric(name="proxy_ban_rate", value=0, unit="%", description="Proxy manager ban signal"),
            ObservabilityMetric(name="extraction_confidence_avg", value=0, unit="%", description="Updated after repository persistence"),
            ObservabilityMetric(name="db_pool_usage", value=0, unit="%", description="Local runtime mode"),
            ObservabilityMetric(name="qdrant_pending_vectors", value=0, unit="vectors", description="Indexer adapter queue"),
            ObservabilityMetric(name="worker_memory_mb", value=0, unit="MB", description="Worker telemetry hook"),
            ObservabilityMetric(name="end_to_end_latency_ms", value=float(renders), unit="renders", description="Browser render count in local mode"),
        ]

    def catalog(self) -> list[dict[str, str]]:
        return [{"name": name, "unit": unit, "description": description} for name, unit, description in self.metric_catalog]
