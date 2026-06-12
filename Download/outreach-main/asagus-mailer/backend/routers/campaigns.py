"""
Campaign CRUD + run/pause/progress endpoints.
"""

import json
import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Campaign, Lead, GlobalSentEmail, Unsubscribe, EmailLog, SenderAccount
from services.sender_service import run_campaign_sending, RUNNING_CAMPAIGNS

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


def campaign_to_response(c: Campaign) -> dict:
    try:
        init_ids = json.loads(c.initial_template_ids)
    except Exception:
        init_ids = []
    try:
        d3_ids = json.loads(c.followup_day3_template_ids) if c.followup_day3_template_ids else None
    except Exception:
        d3_ids = None
    try:
        d6_ids = json.loads(c.followup_day6_template_ids) if c.followup_day6_template_ids else None
    except Exception:
        d6_ids = None
    try:
        sender_ids = json.loads(c.sender_account_ids)
    except Exception:
        sender_ids = []
    try:
        s_limits = json.loads(c.sender_limits) if c.sender_limits else None
    except Exception:
        s_limits = None

    return {
        "id": c.id, "name": c.name, "lead_file_id": c.lead_file_id,
        "initial_template_ids": init_ids,
        "followup_day3_template_ids": d3_ids,
        "followup_day6_template_ids": d6_ids,
        "sender_account_ids": sender_ids,
        "status": c.status,
        "lead_limit": c.lead_limit,
        "total_targets": c.total_targets,
        "sent_count": c.sent_count,
        "current_lead_index": c.current_lead_index,
        "ab_test_enabled": c.ab_test_enabled,
        "sender_limits": s_limits,
        "created_at": c.created_at,
        "started_at": c.started_at,
        "completed_at": c.completed_at,
        "pause_reason": c.pause_reason,
    }


@router.get("")
async def list_campaigns(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Campaign).order_by(Campaign.created_at.desc()))
    campaigns = result.scalars().all()
    return [campaign_to_response(c) for c in campaigns]


@router.post("")
async def create_campaign(
    name: str,
    lead_file_id: int,
    initial_template_ids: str,
    sender_account_ids: str,
    followup_day3_template_ids: str = None,
    followup_day6_template_ids: str = None,
    lead_limit: int = None,
    ab_test_enabled: bool = False,
    sender_limits: str = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a campaign. Template and sender IDs should be JSON arrays as strings.
    sender_limits: JSON object {"sender_id": max_count}
    """
    try:
        init_ids = json.loads(initial_template_ids)
    except Exception:
        raise HTTPException(status_code=400, detail="initial_template_ids must be valid JSON array")
    try:
        s_ids = json.loads(sender_account_ids)
    except Exception:
        raise HTTPException(status_code=400, detail="sender_account_ids must be valid JSON array")

    d3_ids = None
    if followup_day3_template_ids:
        try:
            d3_ids = json.dumps(json.loads(followup_day3_template_ids))
        except Exception:
            d3_ids = None

    d6_ids = None
    if followup_day6_template_ids:
        try:
            d6_ids = json.dumps(json.loads(followup_day6_template_ids))
        except Exception:
            d6_ids = None

    s_limits_json = None
    if sender_limits:
        try:
            s_limits_json = json.dumps(json.loads(sender_limits))
        except Exception:
            s_limits_json = None

    campaign = Campaign(
        name=name,
        lead_file_id=lead_file_id,
        initial_template_ids=json.dumps(init_ids),
        followup_day3_template_ids=d3_ids,
        followup_day6_template_ids=d6_ids,
        sender_account_ids=json.dumps(s_ids),
        status="draft",
        lead_limit=lead_limit,
        ab_test_enabled=ab_test_enabled,
        sender_limits=s_limits_json,
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return campaign_to_response(campaign)


@router.get("/{campaign_id}")
async def get_campaign(campaign_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign_to_response(c)


@router.get("/{campaign_id}/preview")
async def preview_campaign(campaign_id: int, db: AsyncSession = Depends(get_db)):
    """Show lead availability stats before running the campaign."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")

    total_result = await db.execute(
        select(func.count(Lead.id)).where(Lead.file_id == c.lead_file_id)
    )
    total = total_result.scalar() or 0

    gs_result = await db.execute(select(GlobalSentEmail.email))
    gs_set = {row[0] for row in gs_result.fetchall()}

    unsub_result = await db.execute(select(Unsubscribe.email))
    unsub_set = {row[0] for row in unsub_result.fetchall()}

    pending_result = await db.execute(
        select(Lead).where(Lead.file_id == c.lead_file_id, Lead.status == "pending")
    )
    pending_leads = pending_result.scalars().all()

    available = [
        l for l in pending_leads
        if l.email.lower() not in gs_set and l.email.lower() not in unsub_set
    ]

    will_send = len(available)
    if c.lead_limit and c.lead_limit > 0:
        will_send = min(c.lead_limit, will_send)

    return {
        "total_leads": total,
        "available_leads": len(available),
        "already_contacted_globally": len([l for l in pending_leads if l.email.lower() in gs_set]),
        "unsubscribed": len([l for l in pending_leads if l.email.lower() in unsub_set]),
        "will_send": will_send,
        "lead_limit": c.lead_limit,
    }


@router.post("/{campaign_id}/run")
async def run_campaign(
    campaign_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if c.status == "running":
        raise HTTPException(status_code=400, detail="Campaign is already running")

    if c.status == "completed":
        raise HTTPException(status_code=400, detail="Campaign already completed")

    if campaign_id in RUNNING_CAMPAIGNS:
        raise HTTPException(status_code=400, detail="Campaign is already in background queue")

    c.status = "running"
    c.started_at = c.started_at or datetime.utcnow()
    c.pause_reason = None
    await db.commit()

    background_tasks.add_task(run_campaign_sending, campaign_id)
    return {"message": "Campaign started", "campaign_id": campaign_id, "status": "running"}


@router.post("/{campaign_id}/pause")
async def pause_campaign(campaign_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if c.status == "paused":
        return {"message": "Campaign is already paused", "status": "paused"}

    if c.status not in ("running",):
        raise HTTPException(status_code=400, detail=f"Cannot pause campaign with status: {c.status}")

    c.status = "paused"
    c.pause_reason = "Manually paused by user"
    await db.commit()
    return {"message": "Campaign paused", "status": "paused"}


@router.delete("/{campaign_id}")
async def delete_campaign(campaign_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if c.status == "running":
        raise HTTPException(status_code=400, detail="Cannot delete a running campaign. Pause it first.")

    await db.delete(c)
    await db.commit()
    return {"message": "Campaign deleted"}


@router.get("/{campaign_id}/progress")
async def campaign_progress(campaign_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Get recent sent emails
    recent_result = await db.execute(
        select(EmailLog, Lead)
        .join(Lead, EmailLog.lead_id == Lead.id)
        .where(EmailLog.campaign_id == campaign_id)
        .order_by(EmailLog.sent_at.desc())
        .limit(10)
    )
    recent = recent_result.all()

    recent_sends = [
        {
            "lead_name": lead.name or lead.email,
            "subject": log.subject,
            "sent_at": log.sent_at,
            "status": log.status,
        }
        for log, lead in recent
    ]

    progress_pct = 0
    if c.total_targets and c.total_targets > 0:
        progress_pct = round((c.sent_count / c.total_targets) * 100, 1)

    return {
        "id": c.id,
        "status": c.status,
        "sent_count": c.sent_count,
        "total_targets": c.total_targets,
        "current_lead_index": c.current_lead_index,
        "pause_reason": c.pause_reason,
        "started_at": c.started_at,
        "completed_at": c.completed_at,
        "progress_pct": progress_pct,
        "recent_sends": recent_sends,
    }


@router.get("/{campaign_id}/sender-stats")
async def campaign_sender_stats(campaign_id: int, db: AsyncSession = Depends(get_db)):
    """Per-sender email counts for this campaign."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")

    sender_ids = json.loads(c.sender_account_ids)
    sender_limits = json.loads(c.sender_limits) if c.sender_limits else {}
    stats = []

    for sid in sender_ids:
        s_result = await db.execute(select(SenderAccount).where(SenderAccount.id == sid))
        sender = s_result.scalar_one_or_none()
        if not sender:
            continue

        count_result = await db.execute(
            select(func.count(EmailLog.id)).where(
                EmailLog.campaign_id == campaign_id,
                EmailLog.sender_account_id == sid,
            )
        )
        campaign_sent = count_result.scalar() or 0
        campaign_limit = sender_limits.get(str(sid), sender.daily_limit)

        stats.append({
            "sender_id": sid,
            "email": sender.email,
            "display_name": sender.display_name,
            "sent_this_campaign": campaign_sent,
            "campaign_limit": campaign_limit,
            "daily_limit": sender.daily_limit,
            "sent_today": sender.sent_today,
            "remaining_today": max(0, sender.daily_limit - sender.sent_today),
        })

    return stats
