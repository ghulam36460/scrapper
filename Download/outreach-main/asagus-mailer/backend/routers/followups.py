"""
Follow-up queue management endpoints.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import FollowupQueue, Lead, EmailLog

router = APIRouter(prefix="/api/followups", tags=["followups"])


@router.get("")
async def list_followups(
    followup_day: int = None,
    status: str = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    query = select(FollowupQueue).order_by(FollowupQueue.scheduled_at.asc())
    if followup_day is not None:
        query = query.where(FollowupQueue.followup_day == followup_day)
    if status is not None:
        query = query.where(FollowupQueue.status == status)

    count_result = await db.execute(select(func.count(FollowupQueue.id)))
    total = count_result.scalar()

    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    items = result.scalars().all()

    now = datetime.utcnow()
    enriched = []
    for fq in items:
        lead_result = await db.execute(select(Lead).where(Lead.id == fq.lead_id))
        lead = lead_result.scalar_one_or_none()
        orig_result = await db.execute(select(EmailLog).where(EmailLog.id == fq.original_email_id))
        orig = orig_result.scalar_one_or_none()

        enriched.append({
            "id": fq.id,
            "lead_id": fq.lead_id,
            "lead_email": lead.email if lead else None,
            "lead_name": lead.name if lead else None,
            "campaign_id": fq.campaign_id,
            "original_email_id": fq.original_email_id,
            "original_subject": orig.subject if orig else None,
            "original_sender_id": orig.sender_account_id if orig else None,
            "followup_day": fq.followup_day,
            "scheduled_at": fq.scheduled_at,
            "status": fq.status,
            "sent_at": fq.sent_at,
            "is_overdue": fq.status == "pending" and fq.scheduled_at < now,
        })

    return {
        "items": enriched,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total > 0 else 0,
    }


@router.post("/{followup_id}/trigger")
async def trigger_followup_now(followup_id: int, db: AsyncSession = Depends(get_db)):
    """Manually trigger a pending follow-up immediately."""
    result = await db.execute(select(FollowupQueue).where(FollowupQueue.id == followup_id))
    fq = result.scalar_one_or_none()
    if not fq:
        raise HTTPException(status_code=404, detail="Follow-up not found")
    if fq.status != "pending":
        raise HTTPException(status_code=400, detail=f"Follow-up is already {fq.status}")

    # Set scheduled_at to now to trigger on next scheduler run
    fq.scheduled_at = datetime.utcnow()
    await db.commit()
    return {"message": "Follow-up scheduled for immediate send"}


@router.post("/{followup_id}/cancel")
async def cancel_followup(followup_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FollowupQueue).where(FollowupQueue.id == followup_id))
    fq = result.scalar_one_or_none()
    if not fq:
        raise HTTPException(status_code=404, detail="Follow-up not found")
    if fq.status != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot cancel follow-up with status: {fq.status}")

    fq.status = "cancelled"
    await db.commit()
    return {"message": "Follow-up cancelled"}


@router.get("/stats")
async def followup_stats(db: AsyncSession = Depends(get_db)):
    now = datetime.utcnow()
    week_start = now - timedelta(days=7)

    due_today_result = await db.execute(
        select(func.count(FollowupQueue.id)).where(
            FollowupQueue.status == "pending",
            FollowupQueue.scheduled_at <= now,
        )
    )
    due_today = due_today_result.scalar() or 0

    overdue_result = await db.execute(
        select(func.count(FollowupQueue.id)).where(
            FollowupQueue.status == "pending",
            FollowupQueue.scheduled_at < now,
        )
    )
    overdue = overdue_result.scalar() or 0

    pending_result = await db.execute(
        select(func.count(FollowupQueue.id)).where(FollowupQueue.status == "pending")
    )
    pending_total = pending_result.scalar() or 0

    sent_week_result = await db.execute(
        select(func.count(FollowupQueue.id)).where(
            FollowupQueue.status == "sent",
            FollowupQueue.sent_at >= week_start,
        )
    )
    sent_week = sent_week_result.scalar() or 0

    return {
        "due_today": due_today,
        "overdue": overdue,
        "pending_total": pending_total,
        "sent_this_week": sent_week,
    }
