"""
Inbox warm-up service.
Sends emails between user's own accounts to build sender reputation.
"""

import random
import asyncio
import logging
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from models import SenderAccount, WarmupSession, WarmupLog
from services.sender_service import send_email

logger = logging.getLogger(__name__)

WARMUP_SCHEDULE = {
    1: 5, 2: 8, 3: 12, 4: 16, 5: 20,
    6: 24, 7: 28, 8: 32, 9: 36, 10: 40,
}

WARMUP_SUBJECTS = [
    "Checking in", "Quick question", "Following up",
    "Thoughts on this?", "Can we connect?", "Re: Our conversation",
    "Just wanted to share", "Quick note", "Hope you are well",
]

WARMUP_BODIES = [
    "Hope you're doing well. Just wanted to touch base.",
    "Had a quick thought I wanted to share with you.",
    "Following up on our last conversation. Hope all is well.",
    "Do you have a few minutes to connect this week?",
    "Just checking in - how are things going on your end?",
    "Wanted to reach out and see how things are going.",
]


async def run_warmup_for_account(sender_account: SenderAccount, db: AsyncSession):
    """Run warmup sends for a single account."""
    ws_result = await db.execute(
        select(WarmupSession).where(
            WarmupSession.sender_account_id == sender_account.id,
            WarmupSession.status == "active",
        )
    )
    session = ws_result.scalar_one_or_none()

    if not session:
        # Create new session
        session = WarmupSession(
            sender_account_id=sender_account.id,
            day_number=1,
            emails_sent_today=0,
            target_today=5,
            status="active",
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

    target = WARMUP_SCHEDULE.get(session.day_number, 40)
    session.target_today = target
    session.emails_sent_today = 0

    # Get all other active senders as warmup partners
    partners_result = await db.execute(
        select(SenderAccount).where(
            SenderAccount.is_active == True,
            SenderAccount.id != sender_account.id,
        )
    )
    partners = partners_result.scalars().all()

    if not partners:
        logger.warning(f"Warmup: No partner accounts for {sender_account.email}")
        return

    sent_count = 0
    for i in range(target):
        partner = random.choice(partners)
        subject = random.choice(WARMUP_SUBJECTS)
        body = random.choice(WARMUP_BODIES)
        message_id = f"<warmup-{uuid4()}@asagus-mailer.local>"

        result = await send_email(
            db,
            sender_account,
            partner.email,
            subject,
            body,
            message_id,
            None,
        )

        if result["success"]:
            wl = WarmupLog(
                session_id=session.id,
                sender_account_id=sender_account.id,
                direction="sent",
                to_from_email=partner.email,
                subject=subject,
                sent_at=datetime.utcnow(),
                status="ok",
            )
            db.add(wl)
            sent_count += 1

        # Wait between warmup emails (60-180 seconds)
        delay = random.uniform(60, 180)
        await asyncio.sleep(delay)

    session.emails_sent_today = sent_count
    session.last_run_at = datetime.utcnow()
    session.day_number += 1

    if session.day_number > 10:
        session.status = "completed"
        sender_account.warmup_enabled = False
        logger.info(f"Warmup: {sender_account.email} completed warmup!")
    else:
        sender_account.warmup_day = session.day_number

    await db.commit()


async def run_all_warmup_sessions():
    """Run warmup for all accounts with warmup enabled. Called by APScheduler daily."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(SenderAccount).where(
                SenderAccount.is_active == True,
                SenderAccount.warmup_enabled == True,
            )
        )
        senders = result.scalars().all()

        for sender in senders:
            try:
                await run_warmup_for_account(sender, db)
            except Exception as e:
                logger.error(f"Warmup: Failed for {sender.email}: {e}")
