"""
Records Router — CRUD and CSV export for business records and secondary DB.
"""
from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from asagus.services.formatting import DataFormatter
from asagus.layers.noise_reduction import format_csv_cell
from asagus.models import JobStatus
from asagus.services.runtime import runtime
from asagus.routers.deps import require_operator

router = APIRouter(prefix="/api", tags=["records"])

# ... (keep other routes unchanged)

# ─── CSV Export ─────────────────────────────────────────────────────────

@router.get("/records/export/csv", dependencies=[Depends(require_operator)])
async def export_records_csv() -> StreamingResponse:
    """Export primary DB records as CSV download using professional formatting."""
    records = await runtime.list_records()

    # Define clean, requested header mapping
    column_mapping = {
        "name": "Business Name",
        "category": "Category",
        "phone": "Phone Number",
        "whatsapp": "WhatsApp",
        "email": "Email",
        "address": "Address",
        "city": "City",
        "country_code": "Country",
        "website_url": "Website",
        "facebook_url": "Facebook",
        "instagram_url": "Instagram",
        "twitter_url": "Twitter",
        "linkedin_url": "LinkedIn",
        "rating": "Rating",
        "review_count": "Reviews",
        "email_verified": "Email Verified",
        "phone_valid": "Phone Valid",
        "whatsapp_valid": "WhatsApp Valid",
        "website_alive": "Website Active",
        "record_completeness": "Completeness Score",
        "confidence": "Confidence Score",
        "cleaning_issues": "Issues",
        "manual_review_required": "Needs Review",
        "source": "Source",
        "source_url": "Source URL",
        "id": "ID",
    }
    
    # Exact requested order
    column_order = [
        "Business Name", "Category", "City", "Country", "Phone Number", "WhatsApp",
        "Email", "Email Verified", "Phone Valid", "WhatsApp Valid",
        "Website", "Website Active", "Facebook", "Instagram", "Twitter", "LinkedIn",
        "Rating", "Reviews", "Completeness Score", "Confidence Score",
        "Address", "Area", "Issues", "Needs Review", "Source", "Source URL", "ID"
    ]

    def iter_csv() -> Any:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=column_order, extrasaction="ignore")
        writer.writeheader()
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        for record in records:
            row = record.model_dump(mode="json")
            
            # Apply formatter
            formatted_row = {
                "Business Name": row.get("name", "-"),
                "Category": row.get("category", "-"),
                "City": row.get("city", "-"),
                "Country": DataFormatter.format_country(row.get("country_code", "-")),
                "Phone Number": DataFormatter.format_phone(row.get("phone", "-"), row.get("country_code", "")),
                "WhatsApp": DataFormatter.format_phone(row.get("whatsapp", "-"), row.get("country_code", "")),
                "Email": row.get("email", "-"),
                "Email Verified": DataFormatter.format_boolean(row.get("email_verified", "-")),
                "Phone Valid": DataFormatter.format_boolean(row.get("phone_valid", "-")),
                "WhatsApp Valid": DataFormatter.format_boolean(row.get("whatsapp_valid", "-")),
                "Website": DataFormatter.format_url(row.get("website_url", "-")),
                "Website Active": DataFormatter.format_boolean(row.get("website_alive", "-")),
                "Facebook": DataFormatter.format_url(row.get("facebook_url", "-")),
                "Instagram": DataFormatter.format_url(row.get("instagram_url", "-")),
                "Twitter": DataFormatter.format_url(row.get("twitter_url", "-")),
                "LinkedIn": DataFormatter.format_url(row.get("linkedin_url", "-")),
                "Rating": row.get("rating", "-"),
                "Reviews": row.get("review_count", "-"),
                "Completeness Score": DataFormatter.format_score(row.get("record_completeness", 0)),
                "Confidence Score": DataFormatter.format_score(row.get("confidence", 0)),
                "Address": row.get("address", "-"),
                "Area": row.get("normalized_area", "-"),
                "Issues": ", ".join(row.get("raw_fields", {}).get("cleaning_issues", [])),
                "Needs Review": DataFormatter.format_boolean(row.get("manual_review_required", "no")),
                "Source": row.get("source", "-"),
                "Source URL": row.get("source_url", "-"),
                "ID": row.get("id", "-"),
            }
            
            # Quality Flag logic
            if formatted_row["Needs Review"] == "✅":
                formatted_row["Business Name"] += " ⚠️ REVIEW"
            if formatted_row["Completeness Score"] != "-" and float(formatted_row["Completeness Score"].strip("%")) < 70:
                formatted_row["Business Name"] += " 📋 INCOMPLETE"
            if formatted_row["Email Verified"] == "❌":
                formatted_row["Email"] += " (unverified)"

            writer.writerow({k: format_csv_cell(v) for k, v in formatted_row.items()})
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)


# ─── Secondary DB ──────────────────────────────────────────────────────

@router.get("/records/secondary", dependencies=[Depends(require_operator)])
async def list_secondary_records() -> dict[str, Any]:
    """List secondary DB records (all scraped URLs including skipped)."""
    rows = await runtime.list_secondary_records()
    return {"count": len(rows), "records": rows[:2000]}


@router.get("/records/secondary/export/csv", dependencies=[Depends(require_operator)])
async def export_secondary_records_csv() -> StreamingResponse:
    """Export secondary DB (all real-time events) as CSV download using unified formatting."""
    records = await runtime.list_secondary_records()

    # Define requested header mapping and order
    column_order = [
        "Business Name", "Category", "City", "Country", "Phone Number", "WhatsApp",
        "Email", "Email Verified", "Phone Valid", "WhatsApp Valid",
        "Website", "Website Active", "Facebook", "Instagram", "Twitter", "LinkedIn",
        "Rating", "Reviews", "Completeness Score", "Confidence Score",
        "Address", "Area", "Issues", "Needs Review", "Source", "Source URL", "ID"
    ]

    def iter_csv() -> Any:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=column_order, extrasaction="ignore")
        writer.writeheader()
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        for row in records:
            # Map and Format using DataFormatter
            formatted_row = {
                "Business Name": row.get("name", "-"),
                "Category": row.get("category", "-"),
                "City": row.get("city", "-"),
                "Country": DataFormatter.format_country(row.get("country_code", "-")),
                "Phone Number": DataFormatter.format_phone(row.get("phone", "-"), row.get("country_code", "")),
                "WhatsApp": DataFormatter.format_phone(row.get("whatsapp", "-"), row.get("country_code", "")),
                "Email": row.get("email", "-"),
                "Email Verified": DataFormatter.format_boolean(row.get("email_verified", "-")),
                "Phone Valid": DataFormatter.format_boolean(row.get("phone_valid", "-")),
                "WhatsApp Valid": DataFormatter.format_boolean(row.get("whatsapp_valid", "-")),
                "Website": DataFormatter.format_url(row.get("website_url", "-")),
                "Website Active": DataFormatter.format_boolean(row.get("website_alive", "-")),
                "Facebook": DataFormatter.format_url(row.get("facebook_url", "-")),
                "Instagram": DataFormatter.format_url(row.get("instagram_url", "-")),
                "Twitter": DataFormatter.format_url(row.get("twitter_url", "-")),
                "LinkedIn": DataFormatter.format_url(row.get("linkedin_url", "-")),
                "Rating": row.get("rating", "-"),
                "Reviews": row.get("review_count", "-"),
                "Completeness Score": DataFormatter.format_score(row.get("record_completeness", 0)),
                "Confidence Score": DataFormatter.format_score(row.get("confidence", 0)),
                "Address": row.get("address", "-"),
                "Area": row.get("normalized_area", "-"),
                "Issues": ", ".join(row.get("raw_fields", {}).get("cleaning_issues", [])),
                "Needs Review": DataFormatter.format_boolean(row.get("manual_review_required", "no")),
                "Source": row.get("source", "-"),
                "Source URL": row.get("source_url", "-"),
                "ID": row.get("id", "-"),
            }
            writer.writerow({k: format_csv_cell(v) for k, v in formatted_row.items()})
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
    """Merge CSV outputs from all Download tools for a job."""
    from asagus.services.csv_merger import merge_download_tools_csv
    
    result = merge_download_tools_csv(job_id)
    return result


@router.get("/records/export/combined-csv/{job_id}", dependencies=[Depends(require_operator)])
async def build_combined_job_csv(job_id: str) -> dict[str, Any]:
    """Build one CSV from ASAGUS primary records plus Download tool outputs."""
    from asagus.services.csv_merger import merge_asagus_and_download_csv

    records = [record.model_dump(mode="json") for record in await runtime.list_records()]
    return merge_asagus_and_download_csv(job_id, records)


@router.get("/records/export/combined-csv/{job_id}/download", dependencies=[Depends(require_operator)])
async def download_combined_job_csv(job_id: str) -> FileResponse:
    """Build and download one CSV from ASAGUS primary records plus tool outputs."""
    from asagus.services.csv_merger import merge_asagus_and_download_csv

    records = [record.model_dump(mode="json") for record in await runtime.list_records()]
    result = merge_asagus_and_download_csv(job_id, records)
    output_csv = result.get("output_csv")
    if not output_csv:
        raise HTTPException(status_code=404, detail=result.get("status", "combined CSV unavailable"))
    return FileResponse(
        output_csv,
        media_type="text/csv",
        filename=f"asagus_combined_{job_id}.csv",
    )


@router.get("/records/export/merged-csv/{job_id}/summary", dependencies=[Depends(require_operator)])
async def get_merge_summary(job_id: str) -> dict[str, Any]:
    """✅ FIX #5: Get summary of available Download tools outputs for a job."""
    from asagus.services.csv_merger import DownloadToolsCSVMerger
    
    merger = DownloadToolsCSVMerger(job_id)
    return merger.get_merge_summary()
