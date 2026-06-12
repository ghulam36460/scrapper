from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from asagus.config import Settings
from asagus.models import EnrichedRecord, FetchResult, utc_now
from asagus.services.runtime import RuntimeState


class StorageLayer:
    """Primary persistence facade.

    The local implementation writes to RuntimeState; production adapters should
    write raw HTML to MinIO, structured records to Postgres, and graph edges to
    Neo4j per the blueprint.
    """

    def __init__(self, runtime: RuntimeState, settings: Settings | None = None) -> None:
        self.runtime = runtime
        self.settings = settings

    async def store_record(self, record: EnrichedRecord) -> tuple[EnrichedRecord, bool, list[str]]:
        stored, is_new, duplicate_reasons = await self.runtime.add_record(record)
        await self._mirror_record_to_postgres(stored)
        return stored, is_new, duplicate_reasons

    async def archive_raw_html(self, job_id: str, fetch: FetchResult) -> dict[str, str]:
        if not fetch.html:
            return {}
        archive_dir = self.runtime.data_dir / "raw_html" / self._safe_segment(job_id)
        archive_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(fetch.url.encode("utf-8", errors="ignore")).hexdigest()[:20]
        html_path = archive_dir / f"{digest}.html"
        meta_path = archive_dir / f"{digest}.json"
        html_path.write_text(fetch.html, encoding="utf-8")
        metadata = {
            "url": fetch.url,
            "final_url": fetch.final_url,
            "status_code": fetch.status_code,
            "content_type": fetch.content_type,
            "fetch_mode": fetch.fetch_mode.value,
            "proxy_used": fetch.proxy_used,
            "archived_at": utc_now().isoformat(),
        }
        meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        result = {
            "html_path": str(html_path),
            "metadata_path": str(meta_path),
            "sha256_prefix": digest,
        }
        minio_result = await self._archive_raw_html_to_minio(job_id, digest, fetch, metadata)
        if minio_result:
            result.update(minio_result)
        return result

    def _safe_segment(self, value: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_.-]+", "-", value).strip("-") or "unknown"

    def _infra_enabled(self) -> bool:
        return bool(self.settings and self.settings.enable_infra_persistence)

    async def _mirror_record_to_postgres(self, record: EnrichedRecord) -> None:
        if not self._infra_enabled() or not self.settings:
            return
        try:
            import asyncpg

            conn = await asyncpg.connect(self.settings.postgres_url, timeout=2)
            try:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS records (
                        id TEXT PRIMARY KEY,
                        source_url TEXT,
                        payload JSONB NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                payload = json.dumps(record.model_dump(mode="json"), ensure_ascii=False)
                await conn.execute(
                    """
                    INSERT INTO records (id, source_url, payload, updated_at)
                    VALUES ($1, $2, $3::jsonb, NOW())
                    ON CONFLICT (id) DO UPDATE
                    SET source_url = EXCLUDED.source_url,
                        payload = EXCLUDED.payload,
                        updated_at = NOW()
                    """,
                    record.id,
                    record.source_url,
                    payload,
                )
            finally:
                await conn.close()
        except Exception:
            return

    async def _archive_raw_html_to_minio(
        self,
        job_id: str,
        digest: str,
        fetch: FetchResult,
        metadata: dict[str, Any],
    ) -> dict[str, str]:
        if not self._infra_enabled() or not self.settings:
            return {}
        try:
            import boto3
            from botocore.config import Config

            endpoint_url = self.settings.minio_endpoint
            if not endpoint_url.startswith(("http://", "https://")):
                endpoint_url = f"http://{endpoint_url}"
            client = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=self.settings.minio_access_key,
                aws_secret_access_key=self.settings.minio_secret_key,
                config=Config(signature_version="s3v4", connect_timeout=2, read_timeout=5),
            )
            bucket = self.settings.minio_bucket
            try:
                client.head_bucket(Bucket=bucket)
            except Exception:
                client.create_bucket(Bucket=bucket)
            key_prefix = f"raw-html/{self._safe_segment(job_id)}/{digest}"
            client.put_object(
                Bucket=bucket,
                Key=f"{key_prefix}.html",
                Body=fetch.html.encode("utf-8", errors="ignore"),
                ContentType=fetch.content_type or "text/html",
            )
            client.put_object(
                Bucket=bucket,
                Key=f"{key_prefix}.json",
                Body=json.dumps(metadata, ensure_ascii=False).encode("utf-8"),
                ContentType="application/json",
            )
            return {"minio_bucket": bucket, "minio_key": f"{key_prefix}.html"}
        except Exception:
            return {}
