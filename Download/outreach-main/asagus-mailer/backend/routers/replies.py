"""
Reply inbox + inline reply sending + IMAP poll trigger.
"""

import smtplib
import ssl
import asyncio
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Reply, Lead, EmailLog, SenderAccount, Unsubscribe, FollowupQueue
from crypto import decrypt_password
from services.gmail_service import gmail_send_message
from services.imap_service import poll_all_accounts
from services.gmail_service import poll_gmail_accounts

router = APIRouter(prefix="/api/replies", tags=["replies"])


@router.get("")
async def list_replies(
    unread_only: bool = False,
    is_auto_unsubscribe: bool = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    query = select(Reply).order_by(Reply.is_read.asc(), Reply.received_at.desc())

    if unread_only:
        query = query.where(Reply.is_read == False)
    if is_auto_unsubscribe is not None:
        query = query.where(Reply.is_auto_unsubscribe == is_auto_unsubscribe)

    count_result = await db.execute(select(func.count(Reply.id)))
    total = count_result.scalar()

    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    replies = result.scalars().all()

    enriched = []
    for r in replies:
        lead_result = await db.execute(select(Lead).where(Lead.id == r.lead_id))
        lead = lead_result.scalar_one_or_none()
        enriched.append({
            "id": r.id,
            "lead_id": r.lead_id,
            "lead_name": lead.name if lead else None,
            "lead_email": lead.email if lead else r.from_email,
            "lead_business": lead.business_name if lead else None,
            "lead_status": lead.status if lead else None,
            "email_log_id": r.email_log_id,
            "from_email": r.from_email,
            "from_name": r.from_name,
            "subject": r.subject,
            "body": r.body,
            "received_at": r.received_at,
            "match_method": r.match_method,
            "match_confidence": r.match_confidence,
            "is_read": r.is_read,
            "is_auto_unsubscribe": r.is_auto_unsubscribe,
            "replied_back": r.replied_back,
        })

    return {
        "items": enriched,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total > 0 else 0,
    }


@router.get("/stats")
async def reply_stats(db: AsyncSession = Depends(get_db)):
    unread_result = await db.execute(
        select(func.count(Reply.id)).where(Reply.is_read == False)
    )
    total_result = await db.execute(select(func.count(Reply.id)))
    auto_unsub_result = await db.execute(
        select(func.count(Reply.id)).where(Reply.is_auto_unsubscribe == True)
    )

    return {
        "unread_count": unread_result.scalar() or 0,
        "total": total_result.scalar() or 0,
        "auto_unsubscribed_count": auto_unsub_result.scalar() or 0,
    }


@router.get("/{reply_id}")
async def get_reply_detail(reply_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Reply).where(Reply.id == reply_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Reply not found")

    lead_result = await db.execute(select(Lead).where(Lead.id == r.lead_id))
    lead = lead_result.scalar_one_or_none()

    orig_email = None
    if r.email_log_id:
        orig_result = await db.execute(select(EmailLog).where(EmailLog.id == r.email_log_id))
        orig_log = orig_result.scalar_one_or_none()
        if orig_log:
            sender_result = await db.execute(select(SenderAccount).where(SenderAccount.id == orig_log.sender_account_id))
            orig_sender = sender_result.scalar_one_or_none()
            orig_email = {
                "id": orig_log.id,
                "subject": orig_log.subject,
                "body": orig_log.body,
                "sent_at": orig_log.sent_at,
                "sender_email": orig_sender.email if orig_sender else None,
                "sender_id": orig_log.sender_account_id,
            }

    # Mark as read
    r.is_read = True
    await db.commit()

    return {
        "id": r.id,
        "lead": {
            "id": lead.id, "name": lead.name, "email": lead.email,
            "business_name": lead.business_name, "status": lead.status,
        } if lead else None,
        "original_email": orig_email,
        "from_email": r.from_email,
        "from_name": r.from_name,
        "subject": r.subject,
        "body": r.body,
        "received_at": r.received_at,
        "match_method": r.match_method,
        "match_confidence": r.match_confidence,
        "is_read": r.is_read,
        "is_auto_unsubscribe": r.is_auto_unsubscribe,
        "replied_back": r.replied_back,
        "replied_at": r.replied_at,
        "reply_body": r.reply_body,
    }


@router.post("/{reply_id}/reply")
async def send_reply_back(
    reply_id: int,
    body: str,
    db: AsyncSession = Depends(get_db),
):
    """Send an inline reply back to the lead."""
    result = await db.execute(select(Reply).where(Reply.id == reply_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Reply not found")

    # Get sender from original email
    sender = None
    if r.email_log_id:
        orig_result = await db.execute(select(EmailLog).where(EmailLog.id == r.email_log_id))
        orig = orig_result.scalar_one_or_none()
        if orig:
            s_result = await db.execute(select(SenderAccount).where(SenderAccount.id == orig.sender_account_id))
            sender = s_result.scalar_one_or_none()

    if not sender:
        # Use first active sender
        s_result = await db.execute(
            select(SenderAccount).where(SenderAccount.is_active == True).limit(1)
        )
        sender = s_result.scalar_one_or_none()

    if not sender:
        raise HTTPException(status_code=400, detail="No active sender account available")

    if (sender.auth_type or "smtp") != "gmail_api":
        try:
            password = decrypt_password(sender.smtp_password_enc)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Cannot decrypt sender password: {e}")

    # Build reply
    msg = MIMEMultipart("alternative")
    msg["From"] = formataddr((sender.display_name, sender.email))
    msg["To"] = r.from_email
    msg["Subject"] = f"Re: {r.subject or ''}"
    msg["Message-ID"] = f"<{uuid4()}@asagus-mailer.local>"
    if r.email_log_id:
        orig_result = await db.execute(select(EmailLog).where(EmailLog.id == r.email_log_id))
        orig = orig_result.scalar_one_or_none()
        if orig and orig.message_id:
            msg["In-Reply-To"] = orig.message_id
            msg["References"] = orig.message_id

    msg.attach(MIMEText(body, "plain", "utf-8"))
    html_body = f"<p>{body.replace(chr(10), '<br>')}</p>"
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # Send
    try:
        if (sender.auth_type or "smtp") == "gmail_api":
            await gmail_send_message(db, sender.id, msg.as_string())
        else:
            ctx = ssl.create_default_context()
            if sender.smtp_use_tls:
                with smtplib.SMTP(sender.smtp_host, sender.smtp_port, timeout=30) as smtp:
                    smtp.ehlo()
                    smtp.starttls(context=ctx)
                    smtp.login(sender.email, password)
                    smtp.sendmail(sender.email, r.from_email, msg.as_string())
            else:
                with smtplib.SMTP_SSL(sender.smtp_host, sender.smtp_port, context=ctx, timeout=30) as smtp:
                    smtp.login(sender.email, password)
                    smtp.sendmail(sender.email, r.from_email, msg.as_string())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send reply: {e}")

    r.replied_back = True
    r.replied_at = datetime.utcnow()
    r.reply_body = body
    await db.commit()

    return {"message": "Reply sent successfully"}


@router.post("/{reply_id}/read")
async def mark_reply_read(reply_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Reply).where(Reply.id == reply_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Reply not found")
    r.is_read = True
    await db.commit()
    return {"message": "Marked as read"}


@router.post("/{reply_id}/unsubscribe")
async def mark_unsubscribe_from_reply(reply_id: int, db: AsyncSession = Depends(get_db)):
    """Manually mark a reply sender as unsubscribed."""
    result = await db.execute(select(Reply).where(Reply.id == reply_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Reply not found")

    existing = await db.execute(select(Unsubscribe).where(Unsubscribe.email == r.from_email))
    if not existing.scalar_one_or_none():
        unsub = Unsubscribe(
            email=r.from_email.lower(),
            source="manual",
            lead_id=r.lead_id,
        )
        db.add(unsub)

    # Update lead status
    lead_result = await db.execute(select(Lead).where(Lead.id == r.lead_id))
    lead = lead_result.scalar_one_or_none()
    if lead:
        lead.status = "unsubscribed"

    await db.commit()
    return {"message": "Marked as unsubscribed"}


@router.post("/poll")
async def manual_imap_poll(db: AsyncSession = Depends(get_db)):
    """Manually trigger IMAP poll for all accounts."""
    asyncio.create_task(poll_all_accounts())
    asyncio.create_task(poll_gmail_accounts())
    return {"message": "IMAP and Gmail API poll triggered"}
