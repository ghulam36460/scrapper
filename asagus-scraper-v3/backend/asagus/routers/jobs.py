"""
Jobs Router — CRUD and lifecycle endpoints for scrape jobs.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from asagus.config import Settings, get_settings
from asagus.models import JobStatus, LayerName, ScrapeJob, ScrapeStartRequest
from asagus.services.job_helpers import emit, planned_page_count
from asagus.services.runtime import runtime
from asagus.routers.deps import get_services, require_operator

router = APIRouter(prefix="/api", tags=["jobs"])


@router.get("/jobs", dependencies=[Depends(require_operator)])
async def list_jobs() -> list[ScrapeJob]:
    return await runtime.list_jobs()


@router.post("/jobs", dependencies=[Depends(require_operator)])
async def start_job(
    payload: ScrapeStartRequest,
    tasks: BackgroundTasks,
    settings: Settings = Depends(get_settings),
    services: Any = Depends(get_services),
) -> ScrapeJob:
    # Deferred import to avoid circular dependency with run_job
    from asagus.main import run_job

    job = ScrapeJob(
        request=payload,
        total_targets=planned_page_count(payload, settings),
        progress_message="Queued",
    )
    await runtime.add_job(job)
    await emit(job.id, LayerName.ai_app, "job_queued", "Job queued from dashboard", payload.model_dump())
    tasks.add_task(run_job, job.id, services)
    return job


@router.get("/jobs/{job_id}", dependencies=[Depends(require_operator)])
async def get_job(job_id: str) -> dict[str, Any]:
    job = runtime.jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job": job, "events": await runtime.list_events(job_id)}


@router.post("/jobs/{job_id}/cancel", dependencies=[Depends(require_operator)])
async def cancel_job(job_id: str) -> ScrapeJob:
    job = await runtime.cancel_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status == JobStatus.cancelled:
        await emit(job.id, LayerName.ai_app, "job_cancelled", "Job cancelled by operator")
    return job


@router.delete("/jobs/{job_id}", dependencies=[Depends(require_operator)])
async def delete_job(job_id: str) -> dict[str, Any]:
    job = runtime.jobs.get(job_id)
    if job and job.status in {JobStatus.running, JobStatus.queued}:
        raise HTTPException(status_code=409, detail="Stop the job before deleting it.")
    deleted = await runtime.delete_job(job_id, delete_archives=True)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True, "job_id": job_id, "deleted": ["job", "events", "raw_html_archive_folder"]}


@router.delete("/jobs", dependencies=[Depends(require_operator)])
async def clear_jobs() -> dict[str, Any]:
    running = [job.id for job in runtime.jobs.values() if job.status in {JobStatus.running, JobStatus.queued}]
    if running:
        raise HTTPException(status_code=409, detail=f"Stop running jobs before clearing history: {', '.join(running[:3])}")
    result = await runtime.clear_jobs(delete_archives=True)
    return {"ok": True, **result}
