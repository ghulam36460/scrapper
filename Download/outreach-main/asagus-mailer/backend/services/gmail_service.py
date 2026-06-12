"""
Gmail API integration helpers.
Handles OAuth token exchange, refresh, send, and reply polling.
"""

import base64
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from models import GmailToken, IntegrationConfig, SenderAccount, Reply, Lead, Unsubscribe, FollowupQueue
from services.imap_service import (
    match_reply_to_sent_email,
    check_for_bounce,
    check_for_unsubscribe_intent,
)

GOOGLE_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
GMAIL_PROFILE_URL = "https://gmail.googleapis.com/gmail/v1/users/me/profile"
GMAIL_MESSAGES_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
GMAIL_MESSAGE_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}"


def _utcnow() -> datetime:
    return datetime.utcnow()


def _decode_body(data: str) -> str:
    try:
        decoded = base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")
        return decoded.strip()
    except Exception:
        return ""


def _extract_body(payload: Dict[str, Any]) -> str:
    if not payload:
        return ""

    mime_type = payload.get("mimeType", "")
    body = payload.get("body", {})
    data = body.get("data")
    if mime_type == "text/plain" and data:
        return _decode_body(data)

    if mime_type == "text/html" and data:
        html = _decode_body(data)
        text = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s+", " ", text).strip()

    for part in payload.get("parts", []) or []:
        text = _extract_body(part)
        if text:
            return text

    return ""


def _get_header(headers: List[Dict[str, str]], name: str) -> str:
    for h in headers or []:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


async def get_integration_config(db: AsyncSession, key: str) -> Optional[str]:
    result = await db.execute(select(IntegrationConfig).where(IntegrationConfig.key == key))
    row = result.scalar_one_or_none()
    return row.value if row else None


async def set_integration_config(db: AsyncSession, key: str, value: str) -> None:
    result = await db.execute(select(IntegrationConfig).where(IntegrationConfig.key == key))
    row = result.scalar_one_or_none()
    if row:
        row.value = value
        row.updated_at = _utcnow()
    else:
        row = IntegrationConfig(key=key, value=value, updated_at=_utcnow())
        db.add(row)
    await db.commit()


async def get_gmail_token(db: AsyncSession, sender_id: int) -> Optional[GmailToken]:
    result = await db.execute(select(GmailToken).where(GmailToken.sender_account_id == sender_id))
    return result.scalar_one_or_none()


async def save_gmail_token(
    db: AsyncSession,
    sender_id: int,
    refresh_token: str,
    access_token: Optional[str],
    expires_in: Optional[int],
    scope: Optional[str],
    token_type: Optional[str],
) -> GmailToken:
    token = await get_gmail_token(db, sender_id)
    expires_at = _utcnow() + timedelta(seconds=expires_in or 0) if expires_in else None
    if token:
        token.refresh_token = refresh_token
        token.access_token = access_token
        token.expires_at = expires_at
        token.scope = scope
        token.token_type = token_type
        token.updated_at = _utcnow()
    else:
        token = GmailToken(
            sender_account_id=sender_id,
            refresh_token=refresh_token,
            access_token=access_token,
            expires_at=expires_at,
            scope=scope,
            token_type=token_type,
            created_at=_utcnow(),
            updated_at=_utcnow(),
        )
        db.add(token)
    await db.commit()
    return token


async def exchange_code_for_tokens(
    db: AsyncSession,
    code: str,
    redirect_uri: str,
) -> Dict[str, Any]:
    client_id = await get_integration_config(db, "gmail_client_id")
    client_secret = await get_integration_config(db, "gmail_client_secret")

    if not client_id or not client_secret:
        raise RuntimeError("Gmail OAuth client is not configured")

    payload = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(GOOGLE_OAUTH_TOKEN_URL, data=payload)
        if resp.status_code >= 400:
            raise RuntimeError(f"Token exchange failed: {resp.text}")
        return resp.json()


async def refresh_access_token(db: AsyncSession, token: GmailToken) -> GmailToken:
    client_id = await get_integration_config(db, "gmail_client_id")
    client_secret = await get_integration_config(db, "gmail_client_secret")

    if not client_id or not client_secret:
        raise RuntimeError("Gmail OAuth client is not configured")

    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": token.refresh_token,
        "grant_type": "refresh_token",
    }

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(GOOGLE_OAUTH_TOKEN_URL, data=payload)
        if resp.status_code >= 400:
            raise RuntimeError(f"Token refresh failed: {resp.text}")
        data = resp.json()
    access_token = data.get("access_token")
    expires_in = data.get("expires_in")
    scope = data.get("scope") or token.scope
    token_type = data.get("token_type") or token.token_type

    return await save_gmail_token(
        db,
        token.sender_account_id,
        token.refresh_token,
        access_token,
        expires_in,
        scope,
        token_type,
    )


async def ensure_access_token(db: AsyncSession, sender_id: int) -> str:
    token = await get_gmail_token(db, sender_id)
    if not token:
        raise RuntimeError("Gmail not connected for this sender")

    if token.access_token and token.expires_at and token.expires_at > _utcnow() + timedelta(seconds=30):
        return token.access_token

    token = await refresh_access_token(db, token)
    if not token.access_token:
        raise RuntimeError("Unable to refresh Gmail access token")
    return token.access_token


async def gmail_send_message(db: AsyncSession, sender_id: int, raw_message: str) -> Dict[str, Any]:
    access_token = await ensure_access_token(db, sender_id)
    headers = {"Authorization": f"Bearer {access_token}"}
    raw_b64 = base64.urlsafe_b64encode(raw_message.encode("utf-8")).decode("utf-8")
    payload = {"raw": raw_b64}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(GMAIL_SEND_URL, headers=headers, json=payload)
        if resp.status_code >= 400:
            raise RuntimeError(f"Gmail send failed: {resp.text}")
        data = resp.json()
    return {
        "success": True,
        "message_id": data.get("id"),
        "error": None,
        "error_type": None,
    }


async def gmail_get_profile(db: AsyncSession, sender_id: int) -> Dict[str, Any]:
    access_token = await ensure_access_token(db, sender_id)
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(GMAIL_PROFILE_URL, headers=headers)
        if resp.status_code >= 400:
            raise RuntimeError(f"Gmail profile fetch failed: {resp.text}")
        return resp.json()


async def gmail_list_messages(
    db: AsyncSession,
    sender_id: int,
    query: str,
    max_results: int = 20,
    label_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    access_token = await ensure_access_token(db, sender_id)
    headers = {"Authorization": f"Bearer {access_token}"}
    params: Dict[str, Any] = {"q": query, "maxResults": max_results}
    if label_ids:
        params["labelIds"] = label_ids
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(GMAIL_MESSAGES_URL, headers=headers, params=params)
        if resp.status_code >= 400:
            raise RuntimeError(f"Gmail messages list failed: {resp.text}")
        data = resp.json()
    return data.get("messages", [])


async def gmail_get_message(db: AsyncSession, sender_id: int, message_id: str, fmt: str = "full") -> Dict[str, Any]:
    access_token = await ensure_access_token(db, sender_id)
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"format": fmt}
    url = GMAIL_MESSAGE_URL.format(message_id=message_id)
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url, headers=headers, params=params)
        if resp.status_code >= 400:
            raise RuntimeError(f"Gmail message fetch failed: {resp.text}")
        return resp.json()


async def test_gmail_api_connection(sender: SenderAccount, db: AsyncSession) -> Dict[str, Any]:
    try:
        profile = await gmail_get_profile(db, sender.id)
        return {
            "smtp_ok": True,
            "smtp_error": None,
            "smtp_help": None,
            "imap_ok": True,
            "imap_error": None,
            "gmail_profile": profile,
        }
    except Exception as e:
        return {
            "smtp_ok": False,
            "smtp_error": str(e),
            "smtp_help": "Gmail API auth failed. Reconnect this sender via Gmail OAuth.",
            "imap_ok": False,
            "imap_error": "Gmail API auth failed",
            "gmail_profile": None,
        }


async def poll_gmail_accounts():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(SenderAccount).where(SenderAccount.is_active == True, SenderAccount.auth_type == "gmail_api")
        )
        senders = result.scalars().all()
        for sender in senders:
            try:
                await poll_single_gmail_account(sender, db)
            except Exception:
                continue


async def poll_single_gmail_account(sender: SenderAccount, db: AsyncSession):
    # Build existing UID set to avoid duplicates
    existing_result = await db.execute(
        select(Reply.imap_uid).where(Reply.imap_uid.like(f"gmail:{sender.id}:%"))
    )
    existing_uids = {row[0] for row in existing_result.fetchall() if row[0]}

    # Pull recent inbox messages not from us
    query = "in:inbox -from:me newer_than:30d"
    messages = await gmail_list_messages(db, sender.id, query=query, max_results=50)

    for msg in messages:
        msg_id = msg.get("id")
        if not msg_id:
            continue
        uid_key = f"gmail:{sender.id}:{msg_id}"
        if uid_key in existing_uids:
            continue

        detail = await gmail_get_message(db, sender.id, msg_id, fmt="full")
        payload = detail.get("payload", {})
        headers = payload.get("headers", [])

        from_raw = _get_header(headers, "From")
        subject = _get_header(headers, "Subject")
        in_reply_to = _get_header(headers, "In-Reply-To")
        references = _get_header(headers, "References")
        date_header = _get_header(headers, "Date")

        body = _extract_body(payload)
        from_email = ""
        if "<" in from_raw and ">" in from_raw:
            from_email = from_raw.split("<")[-1].split(">")[0].strip().lower()
        else:
            from_email = from_raw.strip().lower()

        # Basic date parsing
        received_at = _utcnow()
        if date_header:
            try:
                from email.utils import parsedate_to_datetime
                received_at = parsedate_to_datetime(date_header).replace(tzinfo=None)
            except Exception:
                pass

        if check_for_bounce(subject or "", from_email or ""):
            lead_result = await db.execute(select(Lead).where(Lead.email == from_email))
            lead = lead_result.scalar_one_or_none()
            if lead:
                lead.status = "bounced"
                await db.execute(
                    update(FollowupQueue).where(
                        FollowupQueue.lead_id == lead.id,
                        FollowupQueue.status == "pending",
                    ).values(status="cancelled")
                )
                await db.commit()
            continue

        matched_log, method, confidence = await match_reply_to_sent_email(
            from_email=from_email,
            subject=subject,
            in_reply_to=in_reply_to,
            references=references,
            db=db,
        )

        is_auto_unsub = check_for_unsubscribe_intent(body)

        lead_id = matched_log.lead_id if matched_log else None
        if lead_id is None:
            lead_result = await db.execute(select(Lead).where(Lead.email == from_email))
            lead = lead_result.scalar_one_or_none()
            if lead:
                lead_id = lead.id

        if lead_id is None:
            continue

        if is_auto_unsub:
            existing_unsub = await db.execute(select(Unsubscribe).where(Unsubscribe.email == from_email))
            if not existing_unsub.scalar_one_or_none():
                db.add(Unsubscribe(email=from_email, source="reply_keyword", lead_id=lead_id))
            lead_result = await db.execute(select(Lead).where(Lead.id == lead_id))
            lead = lead_result.scalar_one_or_none()
            if lead:
                lead.status = "unsubscribed"
            await db.execute(
                update(FollowupQueue).where(
                    FollowupQueue.lead_id == lead_id,
                    FollowupQueue.status == "pending",
                ).values(status="cancelled")
            )
        else:
            lead_result = await db.execute(select(Lead).where(Lead.id == lead_id))
            lead = lead_result.scalar_one_or_none()
            if lead and lead.status not in ("unsubscribed", "bounced"):
                lead.status = "replied"
            await db.execute(
                update(FollowupQueue).where(
                    FollowupQueue.lead_id == lead_id,
                    FollowupQueue.status == "pending",
                ).values(status="cancelled")
            )

        reply = Reply(
            email_log_id=matched_log.id if matched_log else None,
            lead_id=lead_id,
            template_id=matched_log.template_id if matched_log else None,
            from_email=from_email,
            from_name=from_raw.split("<")[0].strip() if "<" in from_raw else from_raw,
            subject=subject,
            body=(body or "")[:10000],
            received_at=received_at,
            imap_uid=uid_key,
            match_method=method,
            match_confidence=confidence,
            is_read=False,
            is_auto_unsubscribe=is_auto_unsub,
            replied_back=False,
        )
        db.add(reply)
        await db.commit()


async def gmail_fetch_sent_box(db: AsyncSession, sender_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    messages = await gmail_list_messages(db, sender_id, query="in:sent newer_than:30d", max_results=limit)
    results: List[Dict[str, Any]] = []
    for msg in messages[:limit]:
        msg_id = msg.get("id")
        if not msg_id:
            continue
        detail = await gmail_get_message(db, sender_id, msg_id, fmt="metadata")
        payload = detail.get("payload", {})
        headers = payload.get("headers", [])
        subject = _get_header(headers, "Subject")
        to = _get_header(headers, "To")
        date_str = _get_header(headers, "Date")
        snippet = detail.get("snippet", "")
        results.append({
            "subject": subject or "(no subject)",
            "to": to,
            "date": date_str,
            "snippet": snippet,
        })
    return results
