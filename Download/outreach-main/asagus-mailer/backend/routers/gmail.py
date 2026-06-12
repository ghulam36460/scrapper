"""
Gmail API integration endpoints.
Stores OAuth client config, generates auth URL, and handles callback.
"""

import secrets
import urllib.parse
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from fastapi.responses import HTMLResponse
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import IntegrationConfig, OAuthState, SenderAccount
from services.gmail_service import (
    get_integration_config,
    set_integration_config,
    exchange_code_for_tokens,
    save_gmail_token,
)

router = APIRouter(prefix="/api/integrations/gmail", tags=["gmail"])

DEFAULT_REDIRECT_URI = "http://localhost:8000/api/integrations/gmail/callback"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/userinfo.email",
]


@router.get("")
async def get_gmail_config(db: AsyncSession = Depends(get_db)):
    client_id = await get_integration_config(db, "gmail_client_id")
    client_secret = await get_integration_config(db, "gmail_client_secret")
    redirect_uri = await get_integration_config(db, "gmail_redirect_uri")

    return {
        "client_id": client_id,
        "client_secret_set": bool(client_secret),
        "redirect_uri": redirect_uri or DEFAULT_REDIRECT_URI,
    }


@router.post("")
async def set_gmail_config(
    client_id: str = Body(...),
    client_secret: str = Body(None),
    redirect_uri: str = Body(None),
    db: AsyncSession = Depends(get_db),
):
    if not client_id:
        raise HTTPException(status_code=400, detail="client_id is required")

    existing_secret = await get_integration_config(db, "gmail_client_secret")
    if not client_secret and not existing_secret:
        raise HTTPException(status_code=400, detail="client_secret is required")

    await set_integration_config(db, "gmail_client_id", client_id.strip())
    if client_secret:
        await set_integration_config(db, "gmail_client_secret", client_secret.strip())
    if redirect_uri:
        await set_integration_config(db, "gmail_redirect_uri", redirect_uri.strip())

    return {
        "client_id": client_id.strip(),
        "client_secret_set": True,
        "redirect_uri": redirect_uri.strip() if redirect_uri else DEFAULT_REDIRECT_URI,
    }


@router.get("/authorize")
async def get_gmail_auth_url(sender_id: int = Query(...), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SenderAccount).where(SenderAccount.id == sender_id))
    sender = result.scalar_one_or_none()
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")

    client_id = await get_integration_config(db, "gmail_client_id")
    if not client_id:
        raise HTTPException(status_code=400, detail="Gmail client_id not configured")

    redirect_uri = await get_integration_config(db, "gmail_redirect_uri")
    redirect_uri = redirect_uri or DEFAULT_REDIRECT_URI

    state = secrets.token_urlsafe(24)
    db.add(OAuthState(state=state, sender_account_id=sender_id, created_at=datetime.utcnow()))
    await db.commit()

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return {"auth_url": auth_url, "redirect_uri": redirect_uri}


@router.get("/callback", response_class=HTMLResponse)
async def gmail_oauth_callback(
    code: str = Query(None),
    state: str = Query(None),
    error: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    if error:
        return HTMLResponse(
            content=f"<h2>Gmail OAuth Error</h2><p>{error}</p>",
            status_code=400,
        )

    if not code or not state:
        return HTMLResponse(
            content="<h2>Invalid callback</h2><p>Missing code/state.</p>",
            status_code=400,
        )

    result = await db.execute(select(OAuthState).where(OAuthState.state == state))
    st = result.scalar_one_or_none()
    if not st:
        return HTMLResponse(
            content="<h2>Invalid state</h2><p>State not found or expired.</p>",
            status_code=400,
        )

    redirect_uri = await get_integration_config(db, "gmail_redirect_uri")
    redirect_uri = redirect_uri or DEFAULT_REDIRECT_URI

    try:
        token_data = await exchange_code_for_tokens(db, code, redirect_uri)
    except Exception as e:
        await db.execute(delete(OAuthState).where(OAuthState.state == state))
        await db.commit()
        return HTMLResponse(
            content=f"<h2>Token exchange failed</h2><pre>{str(e)}</pre>",
            status_code=400,
        )

    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        await db.execute(delete(OAuthState).where(OAuthState.state == state))
        await db.commit()
        return HTMLResponse(
            content=(
                "<h2>Missing refresh token</h2>"
                "<p>Please re-connect with consent. Ensure access_type=offline and prompt=consent.</p>"
            ),
            status_code=400,
        )

    await save_gmail_token(
        db,
        st.sender_account_id,
        refresh_token=refresh_token,
        access_token=token_data.get("access_token"),
        expires_in=token_data.get("expires_in"),
        scope=token_data.get("scope"),
        token_type=token_data.get("token_type"),
    )

    sender_result = await db.execute(select(SenderAccount).where(SenderAccount.id == st.sender_account_id))
    sender = sender_result.scalar_one_or_none()
    if sender:
        sender.auth_type = "gmail_api"
        if sender.provider != "gmail":
            sender.provider = "gmail"
        await db.commit()

    await db.execute(delete(OAuthState).where(OAuthState.state == state))
    await db.commit()

    return HTMLResponse(
        content=(
            "<h2>Gmail connected successfully</h2>"
            "<p>You can close this window and return to the app.</p>"
        ),
        status_code=200,
    )
