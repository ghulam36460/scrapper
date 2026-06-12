"""
ASAGUS Mailer - FastAPI application entry point.
Auto-generates SECRET_KEY if not present, initializes database, starts scheduler.
"""

import os
import sys
import hashlib
from contextlib import asynccontextmanager
from datetime import datetime

from pathlib import Path
from dotenv import load_dotenv, find_dotenv

env_path = find_dotenv(usecwd=True)
if env_path:
    load_dotenv(env_path)
else:
    load_dotenv()

# Auto-generate SECRET_KEY if missing
if not os.environ.get("SECRET_KEY"):
    from cryptography.fernet import Fernet
    new_key = Fernet.generate_key().decode()
    target_env = env_path or str((Path(__file__).resolve().parent.parent / ".env").resolve())
    with open(target_env, "w") as f:
        f.write(f"SECRET_KEY={new_key}\n")
    os.environ["SECRET_KEY"] = new_key
    print("[OK] Generated new SECRET_KEY and saved to .env")

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, init_db
from scheduler import setup_scheduler
from routers import senders, leads, templates, campaigns, emails, followups, replies, warmup, analytics, gmail
from models import Lead, Unsubscribe, FollowupQueue
from services.template_service import generate_unsubscribe_token


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("[ASAGUS] Starting up...")
    await init_db()
    print("[ASAGUS] Database initialized")

    scheduler = setup_scheduler()
    scheduler.start()
    print("[ASAGUS] Scheduler started")

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    print("[ASAGUS] Scheduler stopped")


app = FastAPI(
    title="ASAGUS Mailer API",
    description="Production-grade cold email automation system",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"^https?://.*$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers
app.include_router(senders.router)
app.include_router(leads.router)
app.include_router(templates.router)
app.include_router(campaigns.router)
app.include_router(emails.router)
app.include_router(followups.router)
app.include_router(replies.router)
app.include_router(warmup.router)
app.include_router(analytics.router)
app.include_router(gmail.router)


@app.get("/")
async def root():
    return {
        "app": "ASAGUS Mailer",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/unsubscribe/{token}", response_class=HTMLResponse)
async def handle_unsubscribe(token: str, db: AsyncSession = Depends(get_db)):
    """Public unsubscribe endpoint - handles link click from email."""
    # Find lead by verifying token
    result = await db.execute(select(Lead))
    all_leads = result.scalars().all()

    matched_lead = None
    for lead in all_leads:
        expected_token = generate_unsubscribe_token(lead.id, lead.email)
        if expected_token == token:
            matched_lead = lead
            break

    if not matched_lead:
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head><title>Unsubscribe - Invalid Link</title>
            <style>body{font-family:Arial,sans-serif;max-width:600px;margin:80px auto;text-align:center;color:#333;}</style>
            </head>
            <body>
            <h1>Invalid Unsubscribe Link</h1>
            <p>This unsubscribe link is invalid or has already been used.</p>
            </body></html>
            """,
            status_code=400,
        )

    # Insert into unsubscribes
    existing = await db.execute(
        select(Unsubscribe).where(Unsubscribe.email == matched_lead.email.lower())
    )
    if not existing.scalar_one_or_none():
        unsub = Unsubscribe(
            email=matched_lead.email.lower(),
            source="link_click",
            lead_id=matched_lead.id,
        )
        db.add(unsub)

    # Update lead status
    matched_lead.status = "unsubscribed"

    # Cancel all pending followups for this lead
    from sqlalchemy import update
    await db.execute(
        update(FollowupQueue).where(
            FollowupQueue.lead_id == matched_lead.id,
            FollowupQueue.status == "pending",
        ).values(status="cancelled")
    )

    await db.commit()

    return HTMLResponse(
        content="""
        <!DOCTYPE html>
        <html>
        <head>
        <title>Unsubscribed Successfully</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                max-width: 600px;
                margin: 80px auto;
                text-align: center;
                color: #333;
                background: #f9f9f9;
            }
            .card {
                background: white;
                padding: 40px;
                border-radius: 12px;
                box-shadow: 0 2px 20px rgba(0,0,0,0.08);
            }
            h1 { color: #2d6a4f; }
            p { color: #555; line-height: 1.6; }
        </style>
        </head>
        <body>
        <div class="card">
        <h1>You've been unsubscribed.</h1>
        <p>You will no longer receive emails from us.</p>
        <p style="color:#888;font-size:14px;margin-top:30px;">
            If this was a mistake, please contact the sender directly.
        </p>
        </div>
        </body>
        </html>
        """,
        status_code=200,
    )


# Unsubscribes management API
@app.get("/api/unsubscribes")
async def list_unsubscribes(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func
    count_result = await db.execute(select(func.count(Unsubscribe.id)))
    total = count_result.scalar()

    result = await db.execute(
        select(Unsubscribe)
        .order_by(Unsubscribe.unsubscribed_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()

    return {
        "items": [
            {
                "id": i.id, "email": i.email,
                "unsubscribed_at": i.unsubscribed_at,
                "source": i.source, "lead_id": i.lead_id,
            }
            for i in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total > 0 else 0,
    }


@app.post("/api/unsubscribes")
async def add_unsubscribe(email: str, source: str = "manual", db: AsyncSession = Depends(get_db)):
    norm_email = email.strip().lower()
    existing = await db.execute(select(Unsubscribe).where(Unsubscribe.email == norm_email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already unsubscribed")

    unsub = Unsubscribe(email=norm_email, source=source)
    db.add(unsub)
    await db.commit()
    await db.refresh(unsub)
    return {"id": unsub.id, "email": unsub.email, "source": unsub.source}


@app.delete("/api/unsubscribes/{unsub_id}")
async def remove_unsubscribe(unsub_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Unsubscribe).where(Unsubscribe.id == unsub_id))
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="Unsubscribe entry not found")
    await db.delete(u)
    await db.commit()
    return {"message": "Removed from unsubscribe list"}
