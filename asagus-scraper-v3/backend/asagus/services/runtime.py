from __future__ import annotations

import asyncio
import json
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from asagus.models import (
    DomainPolicyState,
    EnrichedRecord,
    JobEvent,
    JobStatus,
    LLMProvider,
    LLMSettings,
    ObservabilityMetric,
    RelationshipCandidate,
    SelectorFingerprint,
    ScrapeJob,
    utc_now,
)


class RuntimeState:
    """Small local-dev state store.

    Production deployments should back this with Postgres + Redis Streams.
    Keeping a memory store here makes the UI and API usable before infra is up.
    """

    def __init__(self) -> None:
        self.data_dir = Path(__file__).resolve().parents[3] / "data"
        self.records_path = self.data_dir / "runtime_records.json"
        self._lock = asyncio.Lock()
        self.jobs: dict[str, ScrapeJob] = {}
        self.events: dict[str, deque[JobEvent]] = defaultdict(lambda: deque(maxlen=500))
        self.records: dict[str, EnrichedRecord] = {}
        self.domain_policy: dict[str, DomainPolicyState] = {}
        self.selector_fingerprints: dict[str, SelectorFingerprint] = {}
        self.graph_candidates: dict[str, RelationshipCandidate] = {}
        self.metrics: dict[str, ObservabilityMetric] = {}
        self.llm_cache: dict[str, dict[str, Any]] = {}
        self.seen_urls: set[str] = set()
        self.llm_settings = LLMSettings(provider=LLMProvider.disabled)
        self.policy_stats: dict[str, Any] = {
            "rule_layer_hits": 0,
            "bayesian_hits": 0,
            "llm_fallback_rate": 0.0,
            "browser_render_avoidance_rate": 0.0,
            "domains_paused": 0,
            "mdp_decisions": 0,
            "frontier_tier_counts": {},
        }
        self._load_records()

    async def add_job(self, job: ScrapeJob) -> ScrapeJob:
        async with self._lock:
            self.jobs[job.id] = job
        return job

    async def update_job(self, job_id: str, **changes: Any) -> ScrapeJob | None:
        async with self._lock:
            job = self.jobs.get(job_id)
            if not job:
                return None
            data = job.model_dump()
            data.update(changes)
            updated = ScrapeJob.model_validate(data)
            self.jobs[job_id] = updated
            return updated

    async def add_event(self, event: JobEvent) -> None:
        async with self._lock:
            self.events[event.job_id].appendleft(event)

    async def add_record(self, record: EnrichedRecord) -> tuple[EnrichedRecord, bool, list[str]]:
        async with self._lock:
            duplicate, reasons = self._find_duplicate_locked(record)
            if duplicate:
                merged = self._merge_records(duplicate, record, reasons)
                self.records[duplicate.id] = merged
                self.seen_urls.add(self.url_key(record.source_url))
                self._persist_records_locked()
                return merged, False, reasons
            self.records[record.id] = record
            self.seen_urls.add(self.url_key(record.source_url))
            self._persist_records_locked()
            return record, True, []

    async def has_seen_url(self, url: str) -> bool:
        async with self._lock:
            return self.url_key(url) in self.seen_urls

    async def mark_url_seen(self, url: str) -> None:
        async with self._lock:
            self.seen_urls.add(self.url_key(url))

    async def add_graph_candidates(self, candidates: list[RelationshipCandidate]) -> None:
        async with self._lock:
            for candidate in candidates:
                key = "|".join(
                    [
                        candidate.source_record_id,
                        candidate.target_record_id,
                        candidate.relationship.value,
                    ]
                )
                self.graph_candidates[key] = candidate

    async def set_metric(self, metric: ObservabilityMetric) -> None:
        async with self._lock:
            self.metrics[metric.name] = metric

    async def list_jobs(self) -> list[ScrapeJob]:
        async with self._lock:
            return sorted(self.jobs.values(), key=lambda item: item.created_at, reverse=True)

    async def list_events(self, job_id: str) -> list[JobEvent]:
        async with self._lock:
            return list(self.events.get(job_id, []))

    async def list_records(self) -> list[EnrichedRecord]:
        async with self._lock:
            return sorted(self.records.values(), key=lambda item: item.record_completeness, reverse=True)

    async def list_graph_candidates(self) -> list[RelationshipCandidate]:
        async with self._lock:
            return sorted(self.graph_candidates.values(), key=lambda item: item.confidence, reverse=True)

    async def list_metrics(self) -> list[ObservabilityMetric]:
        async with self._lock:
            return sorted(self.metrics.values(), key=lambda item: item.name)

    async def cancel_job(self, job_id: str) -> ScrapeJob | None:
        async with self._lock:
            job = self.jobs.get(job_id)
            if not job:
                return None
            if job.status in {JobStatus.completed, JobStatus.failed, JobStatus.cancelled}:
                return job
            data = job.model_dump()
            data.update(
                {
                    "status": JobStatus.cancelled,
                    "finished_at": utc_now(),
                    "current_url": "",
                    "progress_message": "Cancelled; stored records were kept",
                }
            )
            updated = ScrapeJob.model_validate(data)
            self.jobs[job_id] = updated
            return updated

    def url_key(self, url: str) -> str:
        parsed = urlparse(url.strip())
        host = parsed.netloc.lower().removeprefix("www.")
        path = re.sub(r"/+$", "", parsed.path or "/")
        query = parsed.query
        return f"{host}{path}?{query}".lower()

    def _find_duplicate_locked(self, record: EnrichedRecord) -> tuple[EnrichedRecord | None, list[str]]:
        for existing in self.records.values():
            reasons = self._duplicate_reasons(existing, record)
            if reasons:
                return existing, reasons
        return None, []

    def _duplicate_reasons(self, left: EnrichedRecord, right: EnrichedRecord) -> list[str]:
        reasons: list[str] = []
        if left.source_url and right.source_url and self.url_key(left.source_url) == self.url_key(right.source_url):
            reasons.append("source_url")
        if left.email and right.email and left.email.lower() == right.email.lower():
            reasons.append("email")
        if left.phone and right.phone and self._digits(left.phone) == self._digits(right.phone):
            reasons.append("phone")
        if left.whatsapp and right.whatsapp and self._digits(left.whatsapp) == self._digits(right.whatsapp):
            reasons.append("whatsapp")
        left_domain = self._business_domain(left.website_url)
        right_domain = self._business_domain(right.website_url)
        if left_domain and left_domain == right_domain:
            reasons.append("website_domain")
        for field in ["facebook_url", "instagram_url", "twitter_url", "linkedin_url"]:
            left_value = getattr(left, field, "")
            right_value = getattr(right, field, "")
            if left_value and right_value and self.url_key(left_value) == self.url_key(right_value):
                reasons.append(field)
        return reasons

    def _merge_records(self, existing: EnrichedRecord, incoming: EnrichedRecord, reasons: list[str]) -> EnrichedRecord:
        data = existing.model_dump()
        incoming_data = incoming.model_dump()
        for field, value in incoming_data.items():
            if field in {"id", "created_at"}:
                continue
            current = data.get(field)
            if value and not current:
                data[field] = value
        data["confidence"] = max(existing.confidence, incoming.confidence)
        data["record_completeness"] = max(existing.record_completeness, incoming.record_completeness)
        data["duplicate_score"] = max(existing.duplicate_score, incoming.duplicate_score, 1.0 if reasons else 0.0)
        data["dedupe_reasons"] = sorted(set([*existing.dedupe_reasons, *incoming.dedupe_reasons, *reasons]))
        data["raw_fields"] = {
            **existing.raw_fields,
            **incoming.raw_fields,
            "merged_source_urls": sorted(
                set(
                    [
                        *existing.raw_fields.get("merged_source_urls", []),
                        existing.source_url,
                        incoming.source_url,
                    ]
                )
            ),
        }
        data["extraction_trace"] = [*existing.extraction_trace, *incoming.extraction_trace]
        return EnrichedRecord.model_validate(data)

    def _digits(self, value: str) -> str:
        return re.sub(r"\D+", "", value or "")

    def _business_domain(self, url: str) -> str:
        if not url:
            return ""
        host = urlparse(url if "://" in url else f"https://{url}").netloc.lower().removeprefix("www.")
        public_platforms = (
            "google.com",
            "facebook.com",
            "instagram.com",
            "x.com",
            "twitter.com",
            "linkedin.com",
            "example.com",
        )
        return "" if any(host.endswith(platform) for platform in public_platforms) else host

    def _load_records(self) -> None:
        try:
            if not self.records_path.exists():
                return
            payload = json.loads(self.records_path.read_text(encoding="utf-8"))
            rows = payload.get("records", []) if isinstance(payload, dict) else []
            for row in rows:
                record = EnrichedRecord.model_validate(row)
                self.records[record.id] = record
                if record.source_url:
                    self.seen_urls.add(self.url_key(record.source_url))
                for source_url in record.raw_fields.get("merged_source_urls", []):
                    if isinstance(source_url, str):
                        self.seen_urls.add(self.url_key(source_url))
        except Exception:
            self.records = {}
            self.seen_urls = set()

    def _persist_records_locked(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "records": [record.model_dump(mode="json") for record in self.records.values()],
            "saved_at": utc_now().isoformat(),
        }
        tmp_path = self.records_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(self.records_path)


runtime = RuntimeState()
