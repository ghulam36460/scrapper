from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import time
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

logger = logging.getLogger(__name__)


class RuntimeState:
    """Small local-dev state store.

    Production deployments should back this with Postgres + Redis Streams.
    Keeping a memory store here makes the UI and API usable before infra is up.
    """

    def __init__(self, data_dir: str | Path | None = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).resolve().parents[3] / "data"
        self.records_path = self.data_dir / "runtime_records.json"
        self.secondary_records_path = self.data_dir / "runtime_secondary_records.json"
        self.jobs_path = self.data_dir / "runtime_jobs.json"
        self.events_path = self.data_dir / "runtime_events.json"
        self.event_log_path = self.data_dir / "runtime_events.ndjson"
        self.llm_settings_path = self.data_dir / "llm_settings.json"
        self._lock = asyncio.Lock()
        self.jobs: dict[str, ScrapeJob] = {}
        self.events: dict[str, deque[JobEvent]] = defaultdict(lambda: deque(maxlen=500))
        self.records: dict[str, EnrichedRecord] = {}
        self.secondary_records: deque[dict[str, Any]] = deque(maxlen=50_000)  # All events incl. skipped
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
        self._event_writes_since_snapshot = 0
        self._last_event_snapshot_at = 0.0
        self._event_snapshot_interval_seconds = 5.0
        self._event_snapshot_batch_size = 50
        self._terminal_event_types = {"job_completed", "job_failed", "job_cancelled"}
        # ✅ FIX #1: Auto-persistence counters to prevent data loss
        self._records_since_last_persist = 0
        self._auto_persist_interval = 10  # Save every N records
        self._load_records()
        self._load_secondary_records()
        self._load_jobs()
        self._load_events()
        self._load_llm_settings()
        # ✅ FIX #1: Create backup on startup for recovery
        self._create_startup_backup()

    async def add_job(self, job: ScrapeJob) -> ScrapeJob:
        async with self._lock:
            self.jobs[job.id] = job
            self._persist_jobs_locked()
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
            self._persist_jobs_locked()
            return updated

    async def add_event(self, event: JobEvent) -> None:
        async with self._lock:
            self.events[event.job_id].appendleft(event)
            self._append_event_log_locked(event)
            self._event_writes_since_snapshot += 1
            if self._should_snapshot_events_locked(event):
                self._persist_events_locked()

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
            # ✅ FIX #1: Auto-persist every N records to prevent data loss
            self._records_since_last_persist += 1
            if self._records_since_last_persist >= self._auto_persist_interval:
                self._persist_records_locked()
                self._records_since_last_persist = 0
            else:
                # Even if not persisting, ensure we persist on every record to be safe
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

    async def add_secondary_record(self, record: dict[str, Any]) -> None:
        """Add a record to the secondary DB (all scraped URLs including skipped)."""
        async with self._lock:
            self.secondary_records.append(record)
            self._persist_secondary_records_locked()

    async def list_secondary_records(self) -> list[dict[str, Any]]:
        """Return all secondary DB records (full real-time log)."""
        async with self._lock:
            return list(self.secondary_records)

    def persist_llm_settings(self) -> None:
        """Save current LLM settings to disk so they survive restarts."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        payload = self.llm_settings.model_dump(mode="json")
        tmp = self.llm_settings_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.llm_settings_path)

    def _load_llm_settings(self) -> None:
        """Load persisted LLM settings from disk on startup."""
        try:
            if not self.llm_settings_path.exists():
                return
            payload = json.loads(self.llm_settings_path.read_text(encoding="utf-8"))
            self.llm_settings = LLMSettings.model_validate(payload)
        except Exception:
            pass  # Keep default disabled settings on error

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
            self._persist_jobs_locked()
            return updated

    async def delete_job(self, job_id: str, delete_archives: bool = True) -> bool:
        async with self._lock:
            existed = job_id in self.jobs or job_id in self.events
            self.jobs.pop(job_id, None)
            self.events.pop(job_id, None)
            self._persist_jobs_locked()
            self._persist_events_locked()
        if delete_archives:
            self._delete_raw_html_dir(job_id)
        return existed

    async def clear_jobs(self, delete_archives: bool = True) -> dict[str, int]:
        async with self._lock:
            job_ids = set(self.jobs.keys()) | set(self.events.keys())
            jobs_deleted = len(self.jobs)
            events_deleted = sum(len(events) for events in self.events.values())
            self.jobs.clear()
            self.events.clear()
            self._persist_jobs_locked()
            self._persist_events_locked()
        archives_deleted = 0
        if delete_archives:
            for job_id in job_ids:
                if self._delete_raw_html_dir(job_id):
                    archives_deleted += 1
        return {"jobs_deleted": jobs_deleted, "events_deleted": events_deleted, "archives_deleted": archives_deleted}

    async def delete_record(self, record_id: str) -> bool:
        async with self._lock:
            record = self.records.pop(record_id, None)
            existed = record is not None
            if existed:
                self._delete_record_archive_files(record)
                self._rebuild_seen_urls_locked()
                self._persist_records_locked()
            return existed

    async def clear_records(self) -> dict[str, int]:
        async with self._lock:
            records_deleted = len(self.records)
            graph_candidates_deleted = len(self.graph_candidates)
            for record in list(self.records.values()):
                self._delete_record_archive_files(record)
            self.records.clear()
            self.graph_candidates.clear()
            self.seen_urls.clear()
            self._persist_records_locked()
            return {"records_deleted": records_deleted, "graph_candidates_deleted": graph_candidates_deleted}

    async def clear_all_local_data(self) -> dict[str, int]:
        job_result = await self.clear_jobs(delete_archives=True)
        record_result = await self.clear_records()
        return {**job_result, **record_result}

    def url_key(self, url: str) -> str:
        parsed = urlparse(url.strip())
        host = parsed.netloc.lower().removeprefix("www.")
        path = re.sub(r"/+$", "", parsed.path or "/")
        query = parsed.query
        return f"{host}{path}?{query}".lower()

    def _delete_raw_html_dir(self, job_id: str) -> bool:
        safe_id = re.sub(r"[^a-zA-Z0-9_.-]+", "-", job_id).strip("-")
        # Prevent traversal like ..-..
        safe_id = safe_id.replace("..", "")
        path = (self.data_dir / "raw_html" / safe_id).resolve()
        
        # Ensure path is inside data_dir/raw_html
        try:
            if not path.is_relative_to((self.data_dir / "raw_html").resolve()):
                return False
        except ValueError:
            return False

        if not path.exists() or not path.is_dir():
            return False
        shutil.rmtree(path, ignore_errors=True)
        return True

    def _delete_record_archive_files(self, record: EnrichedRecord | None) -> None:
        if not record:
            return
        archive = record.raw_fields.get("raw_html_archive", {})
        if not isinstance(archive, dict):
            return
        for key in ["html_path", "metadata_path"]:
            value = archive.get(key)
            if not isinstance(value, str):
                continue
            path = Path(value)
            try:
                if path.exists() and path.is_file() and path.is_relative_to(self.data_dir):
                    path.unlink()
            except Exception:
                continue

    def _rebuild_seen_urls_locked(self) -> None:
        self.seen_urls = set()
        for record in self.records.values():
            if record.source_url:
                self.seen_urls.add(self.url_key(record.source_url))
            for source_url in record.raw_fields.get("merged_source_urls", []):
                if isinstance(source_url, str):
                    self.seen_urls.add(self.url_key(source_url))

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
            if value is not None and value != "" and (current is None or current == ""):
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
                try:
                    record = EnrichedRecord.model_validate(row)
                    self.records[record.id] = record
                    if record.source_url:
                        self.seen_urls.add(self.url_key(record.source_url))
                    for source_url in record.raw_fields.get("merged_source_urls", []):
                        if isinstance(source_url, str):
                            self.seen_urls.add(self.url_key(source_url))
                except Exception:
                    continue
        except Exception:
            self.records = {}
            self.seen_urls = set()

    def _load_jobs(self) -> None:
        try:
            if not self.jobs_path.exists():
                return
            payload = json.loads(self.jobs_path.read_text(encoding="utf-8"))
            rows = payload.get("jobs", []) if isinstance(payload, dict) else []
            for row in rows:
                try:
                    job = ScrapeJob.model_validate(row)
                    if job.status == JobStatus.running:
                        job = job.model_copy(update={"status": JobStatus.failed, "error": "Backend restarted while job was running"})
                    self.jobs[job.id] = job
                except Exception:
                    continue
        except Exception:
            self.jobs = {}

    def _load_events(self) -> None:
        try:
            if not self.events_path.exists():
                self._load_event_log()
                return
            payload = json.loads(self.events_path.read_text(encoding="utf-8"))
            rows = payload.get("events", {}) if isinstance(payload, dict) else {}
            if isinstance(rows, dict):
                for job_id, events in rows.items():
                    if not isinstance(events, list):
                        continue
                    for row in reversed(events[-500:]):
                        try:
                            self.events[str(job_id)].appendleft(JobEvent.model_validate(row))
                        except Exception:
                            continue
            self._load_event_log()
        except Exception:
            self.events = defaultdict(lambda: deque(maxlen=500))
            self._load_event_log()

    def _load_event_log(self) -> None:
        if not self.event_log_path.exists():
            return
        seen_ids = {
            event.id
            for events in self.events.values()
            for event in events
        }
        try:
            with self.event_log_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = JobEvent.model_validate(json.loads(line))
                    except Exception:
                        continue
                    if event.id in seen_ids:
                        continue
                    seen_ids.add(event.id)
                    self.events[event.job_id].appendleft(event)
        except Exception:
            return

    def _persist_records_locked(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "records": [record.model_dump(mode="json") for record in self.records.values()],
            "saved_at": utc_now().isoformat(),
        }
        tmp_path = self.records_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(self.records_path)

    def _persist_secondary_records_locked(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "records": list(self.secondary_records)[-50_000:],
            "saved_at": utc_now().isoformat(),
        }
        tmp_path = self.secondary_records_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(self.secondary_records_path)

    def _load_secondary_records(self) -> None:
        try:
            if not self.secondary_records_path.exists():
                return
            payload = json.loads(self.secondary_records_path.read_text(encoding="utf-8"))
            rows = payload.get("records", []) if isinstance(payload, dict) else []
            self.secondary_records = deque((r for r in rows if isinstance(r, dict)), maxlen=50_000)
        except Exception:
            self.secondary_records = deque(maxlen=50_000)

    def _safe_replace(self, src: Path, dst: Path) -> None:
        """Safely replace dst with src, retrying on Windows PermissionError (WinError 5)."""
        import os
        import time

        max_attempts = 5
        backoff = 0.05  # 50ms initial backoff
        
        for attempt in range(1, max_attempts + 1):
            try:
                src.replace(dst)
                return
            except PermissionError as exc:
                is_win_error_5 = False
                if os.name == "nt":
                    # PermissionError's winerror attribute is 5 for Access is Denied on Windows
                    if getattr(exc, "winerror", None) == 5:
                        is_win_error_5 = True
                
                if is_win_error_5 and attempt < max_attempts:
                    logger.warning(
                        "Retrying atomic file replace due to Windows sharing violation (WinError 5): "
                        "attempt %d/%d for %s -> %s. Error: %s",
                        attempt, max_attempts, src.name, dst.name, exc
                    )
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    raise exc

    def _persist_jobs_locked(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "jobs": [job.model_dump(mode="json") for job in self.jobs.values()],
            "saved_at": utc_now().isoformat(),
        }
        tmp_path = self.jobs_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._safe_replace(tmp_path, self.jobs_path)

    def _persist_events_locked(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "events": {
                job_id: [event.model_dump(mode="json") for event in events]
                for job_id, events in self.events.items()
            },
            "saved_at": utc_now().isoformat(),
        }
        tmp_path = self.events_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(self.events_path)
        self._rewrite_event_log_locked()
        self._event_writes_since_snapshot = 0
        self._last_event_snapshot_at = time.monotonic()

    def _append_event_log_locked(self, event: JobEvent) -> None:
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with self.event_log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event.model_dump(mode="json"), ensure_ascii=False))
                handle.write("\n")
        except Exception:
            return

    def _rewrite_event_log_locked(self) -> None:
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            tmp_path = self.event_log_path.with_suffix(".tmp")
            with tmp_path.open("w", encoding="utf-8") as handle:
                for events in self.events.values():
                    for event in reversed(list(events)):
                        handle.write(json.dumps(event.model_dump(mode="json"), ensure_ascii=False))
                        handle.write("\n")
            tmp_path.replace(self.event_log_path)
        except Exception:
            return

    def _should_snapshot_events_locked(self, event: JobEvent) -> bool:
        if event.event_type in self._terminal_event_types:
            return True
        if self._event_writes_since_snapshot >= self._event_snapshot_batch_size:
            return True
        if time.monotonic() - self._last_event_snapshot_at >= self._event_snapshot_interval_seconds:
            return True
        return False

    def _create_startup_backup(self) -> None:
        """✅ FIX #1: Create backup of existing data on startup for recovery."""
        try:
            if self.records_path.exists():
                backup_path = self.records_path.with_suffix(".json.backup")
                shutil.copy2(self.records_path, backup_path)
        except Exception:
            pass  # Backup is optional, don't fail startup

    async def force_persist_all(self) -> dict[str, str]:
        """✅ FIX #1: Force immediate persistence of all data."""
        async with self._lock:
            try:
                self._persist_records_locked()
                self._persist_secondary_records_locked()
                self._persist_jobs_locked()
                self._persist_events_locked()
                return {"status": "success", "message": "All data persisted to disk"}
            except Exception as exc:
                return {"status": "error", "message": str(exc)}

    async def get_persistence_stats(self) -> dict[str, Any]:
        """✅ FIX #1: Get statistics about persistence state."""
        async with self._lock:
            return {
                "records_count": len(self.records),
                "records_since_last_persist": self._records_since_last_persist,
                "auto_persist_interval": self._auto_persist_interval,
                "records_path": str(self.records_path),
                "records_file_exists": self.records_path.exists(),
                "backup_exists": self.records_path.with_suffix(".json.backup").exists(),
                "secondary_records_count": len(self.secondary_records),
                "jobs_count": len(self.jobs),
                "seen_urls_count": len(self.seen_urls),
            }


runtime = RuntimeState()
