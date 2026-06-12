"""
Analytics endpoints - overview, campaigns, templates, A/B test, senders, timeline, spam scores.
"""

import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import (
    EmailLog, Reply, Lead, Campaign, EmailTemplate, SenderAccount,
    Unsubscribe, ABTestResult, SpamCheckLog
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/overview")
async def analytics_overview(db: AsyncSession = Depends(get_db)):
    total_sent_result = await db.execute(
        select(func.count(EmailLog.id)).where(EmailLog.status == "sent")
    )
    total_sent = total_sent_result.scalar() or 0

    total_replies_result = await db.execute(select(func.count(Reply.id)))
    total_replies = total_replies_result.scalar() or 0

    total_bounced_result = await db.execute(
        select(func.count(EmailLog.id)).where(EmailLog.status == "bounced")
    )
    total_bounced = total_bounced_result.scalar() or 0

    total_unsub_result = await db.execute(select(func.count(Unsubscribe.id)))
    total_unsub = total_unsub_result.scalar() or 0

    avg_spam_result = await db.execute(select(func.avg(SpamCheckLog.spam_score)))
    avg_spam = round(avg_spam_result.scalar() or 0, 2)

    reply_rate = round((total_replies / total_sent * 100), 2) if total_sent > 0 else 0.0
    bounce_rate = round((total_bounced / total_sent * 100), 2) if total_sent > 0 else 0.0

    return {
        "total_sent": total_sent,
        "total_replies": total_replies,
        "reply_rate": reply_rate,
        "bounce_rate": bounce_rate,
        "total_unsubscribes": total_unsub,
        "avg_spam_score": avg_spam,
    }


@router.get("/campaigns")
async def analytics_campaigns(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Campaign).order_by(Campaign.created_at.desc()))
    campaigns = result.scalars().all()

    stats = []
    for c in campaigns:
        sent_result = await db.execute(
            select(func.count(EmailLog.id)).where(
                EmailLog.campaign_id == c.id, EmailLog.status == "sent"
            )
        )
        sent = sent_result.scalar() or 0

        replies_result = await db.execute(
            select(func.count(Reply.id)).join(Lead, Reply.lead_id == Lead.id).where(
                Lead.file_id == c.lead_file_id
            )
        )
        replies = replies_result.scalar() or 0

        bounced_result = await db.execute(
            select(func.count(EmailLog.id)).where(
                EmailLog.campaign_id == c.id, EmailLog.status == "bounced"
            )
        )
        bounced = bounced_result.scalar() or 0

        unsub_result = await db.execute(
            select(func.count(Lead.id)).where(
                Lead.file_id == c.lead_file_id, Lead.status == "unsubscribed"
            )
        )
        unsub = unsub_result.scalar() or 0

        reply_rate = round((replies / sent * 100), 2) if sent > 0 else 0.0

        stats.append({
            "campaign_id": c.id,
            "campaign_name": c.name,
            "status": c.status,
            "sent": sent,
            "replied": replies,
            "bounced": bounced,
            "unsubscribed": unsub,
            "reply_rate": reply_rate,
        })

    return stats


@router.get("/templates")
async def analytics_templates(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EmailTemplate).order_by(EmailTemplate.created_at.desc()))
    templates = result.scalars().all()

    stats = []
    for t in templates:
        used_result = await db.execute(
            select(func.count(EmailLog.id)).where(EmailLog.template_id == t.id)
        )
        used = used_result.scalar() or 0

        replies_result = await db.execute(
            select(func.count(Reply.id)).where(Reply.template_id == t.id)
        )
        replies = replies_result.scalar() or 0

        reply_rate = round((replies / used * 100), 2) if used > 0 else 0.0

        stats.append({
            "template_id": t.id,
            "template_name": t.name,
            "template_type": t.template_type,
            "times_used": used,
            "replies": replies,
            "reply_rate": reply_rate,
        })

    return stats


@router.get("/ab-test")
async def analytics_ab_test(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ABTestResult).order_by(ABTestResult.campaign_id, ABTestResult.template_id, ABTestResult.subject_variant_index)
    )
    ab_results = result.scalars().all()

    enriched = []
    for ab in ab_results:
        reply_rate = round((ab.replies_received / ab.emails_sent * 100), 2) if ab.emails_sent > 0 else 0.0
        enriched.append({
            "id": ab.id,
            "campaign_id": ab.campaign_id,
            "template_id": ab.template_id,
            "subject_variant_index": ab.subject_variant_index,
            "subject_text": ab.subject_text,
            "emails_sent": ab.emails_sent,
            "replies_received": ab.replies_received,
            "reply_rate": reply_rate,
        })

    return enriched


@router.get("/senders")
async def analytics_senders(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SenderAccount).order_by(SenderAccount.created_at))
    senders = result.scalars().all()

    stats = []
    for s in senders:
        total_result = await db.execute(
            select(func.count(EmailLog.id)).where(EmailLog.sender_account_id == s.id)
        )
        total = total_result.scalar() or 0

        bounced_result = await db.execute(
            select(func.count(EmailLog.id)).where(
                EmailLog.sender_account_id == s.id, EmailLog.status == "bounced"
            )
        )
        bounced = bounced_result.scalar() or 0

        bounce_rate = round((bounced / total * 100), 2) if total > 0 else 0.0

        warmup_status = "disabled"
        if s.warmup_enabled:
            warmup_status = f"active (day {s.warmup_day})"

        stats.append({
            "sender_id": s.id,
            "email": s.email,
            "display_name": s.display_name,
            "provider": s.provider,
            "total_sent": total,
            "bounced": bounced,
            "bounce_rate": bounce_rate,
            "warmup_status": warmup_status,
        })

    return stats


@router.get("/timeline")
async def analytics_timeline(days: int = 30, db: AsyncSession = Depends(get_db)):
    since = datetime.utcnow() - timedelta(days=days)

    sent_result = await db.execute(
        select(
            func.date(EmailLog.sent_at).label("date"),
            func.count(EmailLog.id).label("count"),
        )
        .where(EmailLog.sent_at >= since, EmailLog.status == "sent")
        .group_by(func.date(EmailLog.sent_at))
        .order_by(func.date(EmailLog.sent_at))
    )
    sent_by_day = {str(row.date): row.count for row in sent_result.fetchall()}

    replies_result = await db.execute(
        select(
            func.date(Reply.received_at).label("date"),
            func.count(Reply.id).label("count"),
        )
        .where(Reply.received_at >= since)
        .group_by(func.date(Reply.received_at))
        .order_by(func.date(Reply.received_at))
    )
    replies_by_day = {str(row.date): row.count for row in replies_result.fetchall()}

    # Build complete date range
    timeline = []
    for i in range(days):
        day = (since + timedelta(days=i + 1)).date()
        day_str = str(day)
        timeline.append({
            "date": day_str,
            "sent": sent_by_day.get(day_str, 0),
            "replied": replies_by_day.get(day_str, 0),
        })

    return timeline


@router.get("/spam-scores")
async def analytics_spam_scores(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SpamCheckLog).order_by(SpamCheckLog.checked_at.desc()).limit(limit)
    )
    logs = result.scalars().all()

    return [
        {
            "id": l.id,
            "template_id": l.template_id,
            "subject": l.subject,
            "spam_score": l.spam_score,
            "is_safe": l.is_safe,
            "flags": json.loads(l.flags) if l.flags else [],
            "checked_at": l.checked_at,
        }
        for l in logs
    ]
