"""
Warmup session and log viewing endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import WarmupSession, WarmupLog, SenderAccount

router = APIRouter(prefix="/api/warmup", tags=["warmup"])


@router.get("/sessions")
async def list_warmup_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(WarmupSession).order_by(WarmupSession.started_at.desc())
    )
    sessions = result.scalars().all()

    enriched = []
    for s in sessions:
        sender_result = await db.execute(
            select(SenderAccount).where(SenderAccount.id == s.sender_account_id)
        )
        sender = sender_result.scalar_one_or_none()
        enriched.append({
            "id": s.id,
            "sender_id": s.sender_account_id,
            "sender_email": sender.email if sender else None,
            "sender_name": sender.display_name if sender else None,
            "sender_provider": sender.provider if sender else None,
            "day_number": s.day_number,
            "emails_sent_today": s.emails_sent_today,
            "target_today": s.target_today,
            "status": s.status,
            "started_at": s.started_at,
            "last_run_at": s.last_run_at,
        })

    return enriched


@router.get("/sessions/{session_id}")
async def get_warmup_session(session_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WarmupSession).where(WarmupSession.id == session_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Warmup session not found")

    sender_result = await db.execute(select(SenderAccount).where(SenderAccount.id == s.sender_account_id))
    sender = sender_result.scalar_one_or_none()

    logs_result = await db.execute(
        select(WarmupLog)
        .where(WarmupLog.session_id == session_id)
        .order_by(WarmupLog.sent_at.desc())
        .limit(50)
    )
    logs = logs_result.scalars().all()

    return {
        "id": s.id,
        "sender_email": sender.email if sender else None,
        "sender_name": sender.display_name if sender else None,
        "day_number": s.day_number,
        "emails_sent_today": s.emails_sent_today,
        "target_today": s.target_today,
        "status": s.status,
        "started_at": s.started_at,
        "last_run_at": s.last_run_at,
        "notes": s.notes,
        "logs": [
            {
                "id": l.id,
                "direction": l.direction,
                "to_from_email": l.to_from_email,
                "subject": l.subject,
                "sent_at": l.sent_at,
                "status": l.status,
            }
            for l in logs
        ],
    }


@router.get("/log")
async def get_warmup_log(
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
):
    count_result = await db.execute(select(func.count(WarmupLog.id)))
    total = count_result.scalar()

    result = await db.execute(
        select(WarmupLog)
        .order_by(WarmupLog.sent_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    logs = result.scalars().all()

    return {
        "items": [
            {
                "id": l.id,
                "session_id": l.session_id,
                "sender_id": l.sender_account_id,
                "direction": l.direction,
                "to_from_email": l.to_from_email,
                "subject": l.subject,
                "sent_at": l.sent_at,
                "status": l.status,
            }
            for l in logs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total > 0 else 0,
    }
