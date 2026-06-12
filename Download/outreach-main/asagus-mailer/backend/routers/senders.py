"""
Sender accounts CRUD + test connection + SMTP preset auto-fill + warmup toggle.
"""

import smtplib
import imaplib
import ssl
import json
import asyncio
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import SenderAccount, EmailLog, Reply, FollowupQueue, WarmupLog, WarmupSession, GmailToken
from schemas import (
    SenderAccountCreate,
    SenderAccountUpdate,
    SenderAccountResponse,
    SenderStatsResponse,
    TestConnectionRequest,
)
from crypto import encrypt_password, decrypt_password
from services.imap_service import fetch_gmail_sent_box
from services.gmail_service import test_gmail_api_connection, gmail_fetch_sent_box

router = APIRouter(prefix="/api/senders", tags=["senders"])

SMTP_PRESETS = {
    "gmail": {
        "smtp_host": "smtp.gmail.com", "smtp_port": 587, "smtp_use_tls": True,
        "imap_host": "imap.gmail.com", "imap_port": 993, "daily_limit": 40,
    },
    "zoho": {
        "smtp_host": "smtp.zoho.com", "smtp_port": 587, "smtp_use_tls": True,
        "imap_host": "imap.zoho.com", "imap_port": 993, "daily_limit": 40,
    },
    "brevo": {
        "smtp_host": "smtp-relay.brevo.com", "smtp_port": 587, "smtp_use_tls": True,
        "imap_host": "", "imap_port": 993, "daily_limit": 300,
    },
    "other": {
        "smtp_host": "", "smtp_port": 587, "smtp_use_tls": True,
        "imap_host": "", "imap_port": 993, "daily_limit": 40,
    },
}


def normalize_password(raw: str, provider: str) -> str:
    if raw is None:
        return ""
    cleaned = raw.strip()
    if provider == "gmail":
        return cleaned.replace(" ", "")
    return cleaned


def sender_to_response(sender: SenderAccount, gmail_connected: bool = False) -> dict:
    return {
        "id": sender.id,
        "display_name": sender.display_name,
        "email": sender.email,
        "smtp_host": sender.smtp_host,
        "smtp_port": sender.smtp_port,
        "smtp_use_tls": sender.smtp_use_tls,
        "imap_host": sender.imap_host,
        "imap_port": sender.imap_port,
        "daily_limit": sender.daily_limit,
        "sent_today": sender.sent_today,
        "last_sent_at": sender.last_sent_at,
        "is_active": sender.is_active,
        "provider": sender.provider,
        "warmup_enabled": sender.warmup_enabled,
        "warmup_day": sender.warmup_day,
        "created_at": sender.created_at,
        "has_password": bool(sender.smtp_password_enc),
        "auth_type": sender.auth_type or "smtp",
        "gmail_connected": gmail_connected,
    }


@router.get("")
async def list_senders(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SenderAccount).order_by(SenderAccount.created_at.desc()))
    senders = result.scalars().all()
    token_result = await db.execute(select(GmailToken.sender_account_id))
    token_ids = {row[0] for row in token_result.fetchall()}
    return [sender_to_response(s, gmail_connected=(s.id in token_ids)) for s in senders]


@router.post("")
async def create_sender(
    data: SenderAccountCreate,
    db: AsyncSession = Depends(get_db)
):
    display_name = data.display_name
    email = data.email
    smtp_host = data.smtp_host
    smtp_password = data.smtp_password
    smtp_port = data.smtp_port
    smtp_use_tls = data.smtp_use_tls
    imap_host = data.imap_host
    imap_port = data.imap_port
    imap_password = data.imap_password
    daily_limit = data.daily_limit
    is_active = data.is_active
    provider = data.provider
    auth_type = data.auth_type or "smtp"
    # Check for duplicate email
    existing = await db.execute(select(SenderAccount).where(SenderAccount.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Sender with email {email} already exists")

    if auth_type == "smtp" and (not smtp_password or not smtp_password.strip()):
        raise HTTPException(status_code=400, detail="SMTP password is required for SMTP accounts")

    if auth_type == "gmail_api":
        provider = "gmail"

    smtp_pass = normalize_password(smtp_password, provider)
    imap_pass = normalize_password(imap_password or smtp_password, provider)
    sender = SenderAccount(
        display_name=display_name,
        email=email,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_password_enc=encrypt_password(smtp_pass),
        smtp_use_tls=smtp_use_tls,
        imap_host=imap_host,
        imap_port=imap_port,
        imap_password_enc=encrypt_password(imap_pass),
        daily_limit=daily_limit,
        is_active=is_active,
        provider=provider,
        warmup_enabled=False,
        warmup_day=0,
        sent_today=0,
        last_reset_date=date.today(),
        auth_type=auth_type,
    )
    db.add(sender)
    await db.commit()
    await db.refresh(sender)
    gmail_connected = False
    if auth_type == "gmail_api":
        token_result = await db.execute(select(GmailToken.sender_account_id).where(GmailToken.sender_account_id == sender.id))
        gmail_connected = token_result.scalar_one_or_none() is not None
    return sender_to_response(sender, gmail_connected=gmail_connected)


@router.put("/{sender_id}")
async def update_sender(
    sender_id: int,
    data: SenderAccountUpdate,
    db: AsyncSession = Depends(get_db)
):
    display_name = data.display_name
    email = data.email
    smtp_host = data.smtp_host
    smtp_port = data.smtp_port
    smtp_password = data.smtp_password
    smtp_use_tls = data.smtp_use_tls
    imap_host = data.imap_host
    imap_port = data.imap_port
    imap_password = data.imap_password
    daily_limit = data.daily_limit
    is_active = data.is_active
    provider = data.provider
    result = await db.execute(select(SenderAccount).where(SenderAccount.id == sender_id))
    sender = result.scalar_one_or_none()
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")

    if display_name is not None:
        sender.display_name = display_name
    if email is not None:
        sender.email = email
    if smtp_host is not None:
        sender.smtp_host = smtp_host
    if smtp_port is not None:
        sender.smtp_port = smtp_port
    provider = data.provider if data.provider is not None else sender.provider
    if smtp_password is not None and smtp_password.strip():
        sender.smtp_password_enc = encrypt_password(
            normalize_password(smtp_password, provider)
        )
    if smtp_use_tls is not None:
        sender.smtp_use_tls = smtp_use_tls
    if imap_host is not None:
        sender.imap_host = imap_host
    if imap_port is not None:
        sender.imap_port = imap_port
    if imap_password is not None and imap_password.strip():
        sender.imap_password_enc = encrypt_password(
            normalize_password(imap_password, provider)
        )
    if daily_limit is not None:
        sender.daily_limit = daily_limit
    if is_active is not None:
        sender.is_active = is_active
    if provider is not None:
        sender.provider = provider
    if data.auth_type is not None:
        sender.auth_type = data.auth_type
        if data.auth_type == "gmail_api":
            sender.provider = "gmail"

    await db.commit()
    await db.refresh(sender)
    token_result = await db.execute(select(GmailToken.sender_account_id).where(GmailToken.sender_account_id == sender.id))
    gmail_connected = token_result.scalar_one_or_none() is not None
    return sender_to_response(sender, gmail_connected=gmail_connected)


@router.delete("/{sender_id}")
async def delete_sender(sender_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SenderAccount).where(SenderAccount.id == sender_id))
    sender = result.scalar_one_or_none()
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")

    # Clean up dependent records to avoid FK violations
    log_ids_result = await db.execute(
        select(EmailLog.id).where(EmailLog.sender_account_id == sender_id)
    )
    log_ids = [row[0] for row in log_ids_result.fetchall()]

    if log_ids:
        await db.execute(
            update(Reply)
            .where(Reply.email_log_id.in_(log_ids))
            .values(email_log_id=None)
        )
        await db.execute(
            delete(FollowupQueue)
            .where(FollowupQueue.original_email_id.in_(log_ids))
        )
        await db.execute(
            delete(EmailLog)
            .where(EmailLog.id.in_(log_ids))
        )

    await db.execute(delete(WarmupLog).where(WarmupLog.sender_account_id == sender_id))
    await db.execute(delete(WarmupSession).where(WarmupSession.sender_account_id == sender_id))

    await db.delete(sender)
    await db.commit()
    return {"message": "Sender deleted", "deleted_email_logs": len(log_ids)}


@router.post("/{sender_id}/test")
async def test_sender_connection(
    sender_id: int,
    payload: TestConnectionRequest = Body(default=None),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SenderAccount).where(SenderAccount.id == sender_id))
    sender = result.scalar_one_or_none()
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")

    if (sender.auth_type or "smtp") == "gmail_api":
        return await test_gmail_api_connection(sender, db)

    provider = sender.provider or "other"
    try:
        password = decrypt_password(sender.smtp_password_enc)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot decrypt password: {e}")
    if payload and payload.smtp_password:
        password = normalize_password(payload.smtp_password, provider)

    smtp_ok = False
    smtp_error = None
    smtp_help = None
    imap_ok = False
    imap_error = None

    # Test SMTP
    try:
        ctx = ssl.create_default_context()
        if sender.smtp_use_tls:
            with smtplib.SMTP(sender.smtp_host, sender.smtp_port, timeout=10) as s:
                s.ehlo()
                s.starttls(context=ctx)
                s.ehlo()
                s.login(sender.email, password)
                smtp_ok = True
        else:
            with smtplib.SMTP_SSL(sender.smtp_host, sender.smtp_port, context=ctx, timeout=10) as s:
                s.ehlo()
                s.login(sender.email, password)
                smtp_ok = True
    except Exception as e:
        smtp_error = str(e)
        smtp_error_lower = smtp_error.lower()
        if "5.7.8" in smtp_error_lower or "badcredentials" in smtp_error_lower:
            smtp_help = (
                "Gmail rejected login. Use a NEW App Password (16 chars, no spaces), "
                "enable 2FA, and try DisplayUnlockCaptcha. Also verify full email is used."
            )
        elif "application-specific password" in smtp_error_lower:
            smtp_help = (
                "Gmail requires an App Password. Generate one from Google Account > Security > App passwords."
            )
        elif "timeout" in smtp_error_lower or "timed out" in smtp_error_lower:
            smtp_help = (
                "Connection timeout. Check firewall/antivirus, or try smtp.gmail.com:587 with STARTTLS."
            )

    # Test IMAP
    if sender.imap_host and sender.imap_host.strip():
        try:
            imap_pwd = decrypt_password(sender.imap_password_enc)
            if payload and payload.imap_password:
                imap_pwd = normalize_password(payload.imap_password, provider)
            mail = imaplib.IMAP4_SSL(sender.imap_host, sender.imap_port, timeout=10)
            mail.login(sender.email, imap_pwd)
            mail.logout()
            imap_ok = True
        except Exception as e:
            imap_error = str(e)
    else:
        imap_error = "No IMAP host configured"

    return {
        "smtp_ok": smtp_ok,
        "smtp_error": smtp_error,
        "smtp_help": smtp_help,
        "imap_ok": imap_ok,
        "imap_error": imap_error,
    }


@router.get("/{sender_id}/stats")
async def get_sender_stats(sender_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SenderAccount).where(SenderAccount.id == sender_id))
    sender = result.scalar_one_or_none()
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")

    today = date.today()
    if sender.last_reset_date != today:
        sender.sent_today = 0
        sender.last_reset_date = today
        await db.commit()

    warmup_status = "disabled"
    if sender.warmup_enabled:
        warmup_status = f"active (day {sender.warmup_day})"

    return {
        "id": sender.id,
        "email": sender.email,
        "sent_today": sender.sent_today,
        "daily_limit": sender.daily_limit,
        "remaining": max(0, sender.daily_limit - sender.sent_today),
        "warmup_status": warmup_status,
        "warmup_day": sender.warmup_day,
    }


@router.post("/{sender_id}/warmup/start")
async def start_warmup(sender_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SenderAccount).where(SenderAccount.id == sender_id))
    sender = result.scalar_one_or_none()
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")
    sender.warmup_enabled = True
    sender.warmup_day = max(1, sender.warmup_day)
    await db.commit()
    return {"message": "Warmup started", "warmup_day": sender.warmup_day}


@router.post("/{sender_id}/warmup/stop")
async def stop_warmup(sender_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SenderAccount).where(SenderAccount.id == sender_id))
    sender = result.scalar_one_or_none()
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")
    sender.warmup_enabled = False
    await db.commit()
    return {"message": "Warmup stopped"}


@router.get("/{sender_id}/sent-box")
async def get_sent_box(sender_id: int, limit: int = 50, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SenderAccount).where(SenderAccount.id == sender_id))
    sender = result.scalar_one_or_none()
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")

    if (sender.auth_type or "smtp") == "gmail_api":
        emails = await gmail_fetch_sent_box(db, sender.id, limit)
    else:
        emails = await asyncio.get_event_loop().run_in_executor(
            None, lambda: asyncio.run(fetch_gmail_sent_box(sender, limit))
        )
    return {"emails": emails, "count": len(emails)}


@router.get("/presets/{provider}")
async def get_preset(provider: str):
    preset = SMTP_PRESETS.get(provider.lower())
    if not preset:
        raise HTTPException(status_code=404, detail=f"No preset for provider: {provider}")
    return preset
