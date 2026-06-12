"""
Sent email log endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import EmailLog, Lead, SenderAccount, EmailTemplate, Campaign

router = APIRouter(prefix="/api/emails", tags=["emails"])


@router.get("")
async def list_emails(
    campaign_id: int = None,
    sender_id: int = None,
    is_followup: bool = None,
    status: str = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    query = select(EmailLog).order_by(EmailLog.sent_at.desc())

    if campaign_id is not None:
        query = query.where(EmailLog.campaign_id == campaign_id)
    if sender_id is not None:
        query = query.where(EmailLog.sender_account_id == sender_id)
    if is_followup is not None:
        query = query.where(EmailLog.is_followup == is_followup)
    if status is not None:
        query = query.where(EmailLog.status == status)

    count_q = select(func.count(EmailLog.id))
    if campaign_id:
        count_q = count_q.where(EmailLog.campaign_id == campaign_id)
    count_result = await db.execute(count_q)
    total = count_result.scalar()

    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    logs = result.scalars().all()

    items = []
    for log in logs:
        lead_result = await db.execute(select(Lead).where(Lead.id == log.lead_id))
        lead = lead_result.scalar_one_or_none()
        sender_result = await db.execute(select(SenderAccount).where(SenderAccount.id == log.sender_account_id))
        sender = sender_result.scalar_one_or_none()

        items.append({
            "id": log.id,
            "lead_id": log.lead_id,
            "lead_name": lead.name if lead else None,
            "lead_email": lead.email if lead else None,
            "campaign_id": log.campaign_id,
            "sender_email": sender.email if sender else None,
            "sender_name": sender.display_name if sender else None,
            "template_id": log.template_id,
            "subject": log.subject,
            "subject_variant_index": log.subject_variant_index,
            "sent_at": log.sent_at,
            "status": log.status,
            "is_followup": log.is_followup,
            "followup_day": log.followup_day,
            "error_message": log.error_message,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total > 0 else 0,
    }


@router.get("/{email_id}")
async def get_email_detail(email_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EmailLog).where(EmailLog.id == email_id))
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Email log not found")

    lead_result = await db.execute(select(Lead).where(Lead.id == log.lead_id))
    lead = lead_result.scalar_one_or_none()
    sender_result = await db.execute(select(SenderAccount).where(SenderAccount.id == log.sender_account_id))
    sender = sender_result.scalar_one_or_none()

    template_name = None
    if log.template_id:
        t_result = await db.execute(select(EmailTemplate).where(EmailTemplate.id == log.template_id))
        t = t_result.scalar_one_or_none()
        template_name = t.name if t else None

    return {
        "id": log.id,
        "lead": {"id": lead.id, "name": lead.name, "email": lead.email, "business_name": lead.business_name} if lead else None,
        "sender": {"id": sender.id, "email": sender.email, "display_name": sender.display_name} if sender else None,
        "campaign_id": log.campaign_id,
        "template_id": log.template_id,
        "template_name": template_name,
        "subject": log.subject,
        "subject_variant_index": log.subject_variant_index,
        "body": log.body,
        "sent_at": log.sent_at,
        "status": log.status,
        "is_followup": log.is_followup,
        "followup_day": log.followup_day,
        "message_id": log.message_id,
        "error_message": log.error_message,
    }
