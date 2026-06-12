"""
Records Router — CRUD and CSV export for business records and secondary DB.
"""
from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from asagus.models import JobStatus
from asagus.services.runtime import runtime
from asagus.routers.deps import require_operator

router = APIRouter(prefix="/api", tags=["records"])


@router.get("/records", dependencies=[Depends(require_operator)])
async def list_records() -> dict[str, Any]:
    rows = await runtime.list_records()
    return {"count": len(rows), "records": rows}


@router.delete("/records/{record_id}", dependencies=[Depends(require_operator)])
async def delete_record(record_id: str) -> dict[str, Any]:
    deleted = await runtime.delete_record(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"ok": True, "record_id": record_id}


@router.delete("/records", dependencies=[Depends(require_operator)])
async def clear_records() -> dict[str, Any]:
    result = await runtime.clear_records()
    return {"ok": True, **result}


@router.delete("/runtime/local-data", dependencies=[Depends(require_operator)])
async def clear_local_data() -> dict[str, Any]:
    running = [job.id for job in runtime.jobs.values() if job.status in {JobStatus.running, JobStatus.queued}]
    if running:
        raise HTTPException(status_code=409, detail=f"Stop running jobs before clearing all data: {', '.join(running[:3])}")
    result = await runtime.clear_all_local_data()
    return {"ok": True, **result}


@router.get("/graph/candidates", dependencies=[Depends(require_operator)])
async def graph_candidates() -> dict[str, Any]:
    rows = await runtime.list_graph_candidates()
    return {"count": len(rows), "candidates": rows}


# ─── CSV Export ─────────────────────────────────────────────────────────

@router.get("/records/export/csv", dependencies=[Depends(require_operator)])
async def export_records_csv() -> StreamingResponse:
    """Export primary DB records as CSV download using streaming with ALL contact fields."""
    records = await runtime.list_records()

    # FIXED: Include ALL critical contact and social fields that were missing
    fieldnames = [
        # Identity
        "id", "name", "category", 
        # Contact (CRITICAL - was partially missing)
        "phone", "whatsapp", "email", "address",
        # Location
        "city", "country_code", "lat", "lng", "normalized_area",
        # Online Presence (CRITICAL - was missing)
        "website_url", "facebook_url", "instagram_url",
        "twitter_url", "linkedin_url",
        # Ratings
        "rating", "review_count",
        # Verification Status (NEW)
        "email_verified", "email_mx_checked", "phone_valid", "whatsapp_valid", "website_alive",
        # Metrics
        "record_completeness", "confidence", "duplicate_score",
        # Source
        "source", "source_url", "method",
        # Compliance
        "gdpr_flag", "pdpa_flag",
        # Enrichment (NEW)
        "entity_tags", "ner_entities", "dedupe_reasons",
    ]

    def iter_csv() -> Any:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        for record in records:
            row = record.model_dump(mode="json")
            # Convert complex fields to strings for CSV
            if "entity_tags" in row and isinstance(row["entity_tags"], list):
                row["entity_tags"] = ", ".join(row["entity_tags"])
            if "ner_entities" in row and isinstance(row["ner_entities"], dict):
                row["ner_entities"] = "; ".join(f"{k}: {','.join(v)}" for k, v in row["ner_entities"].items())
            if "dedupe_reasons" in row and isinstance(row["dedupe_reasons"], list):
                row["dedupe_reasons"] = ", ".join(row["dedupe_reasons"])
            
            writer.writerow({k: row.get(k, "") for k in fieldnames})
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    return StreamingResponse(
        iter_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=asagus_primary_records.csv"},
    )


# ─── Secondary DB ──────────────────────────────────────────────────────

@router.get("/records/secondary", dependencies=[Depends(require_operator)])
async def list_secondary_records() -> dict[str, Any]:
    """List secondary DB records (all scraped URLs including skipped)."""
    rows = await runtime.list_secondary_records()
    return {"count": len(rows), "records": rows[:2000]}


@router.get("/records/secondary/export/csv", dependencies=[Depends(require_operator)])
async def export_secondary_records_csv() -> StreamingResponse:
    """Export secondary DB (all real-time events) as CSV download using streaming."""
    records = await runtime.list_secondary_records()

    # Collect all field names across ALL records to avoid dropping columns
    all_keys: set[str] = set()
    for r in records:
        all_keys.update(r.keys())
    fieldnames = sorted(all_keys)

    def iter_csv() -> Any:
        output = io.StringIO()
        if not fieldnames:
            yield ""
            return
            
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        for record in records:
            writer.writerow({k: record.get(k, "") for k in fieldnames})
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    return StreamingResponse(
        iter_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=asagus_secondary_records.csv"},
    )


# ─── ✅ FIX #5: Download Tools CSV Merger ──────────────────────────────

@router.get("/records/export/merged-csv/{job_id}", dependencies=[Depends(require_operator)])
async def export_merged_tools_csv(job_id: str) -> dict[str, Any]:
    """✅ FIX #5: Merge CSV outputs from all Download tools for a job."""
    from asagus.services.csv_merger import merge_download_tools_csv
    
    result = merge_download_tools_csv(job_id)
    return result


@router.get("/records/export/merged-csv/{job_id}/summary", dependencies=[Depends(require_operator)])
async def get_merge_summary(job_id: str) -> dict[str, Any]:
    """✅ FIX #5: Get summary of available Download tools outputs for a job."""
    from asagus.services.csv_merger import DownloadToolsCSVMerger
    
    merger = DownloadToolsCSVMerger(job_id)
    return merger.get_merge_summary()
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    return StreamingResponse(
        iter_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=asagus_secondary_records.csv"},
    )
