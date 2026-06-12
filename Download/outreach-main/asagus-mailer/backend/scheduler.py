"""
APScheduler setup with all background jobs.
Timezone: Asia/Karachi.
"""

import logging
from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from database import AsyncSessionLocal
from models import SenderAccount

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Asia/Karachi")


async def reset_daily_counts():
    """Reset sent_today counter for all sender accounts at midnight."""
    from sqlalchemy import update
    async with AsyncSessionLocal() as db:
        try:
            today = date.today()
            await db.execute(
                update(SenderAccount).values(sent_today=0, last_reset_date=today)
            )
            await db.commit()
            logger.info("Daily counts reset for all sender accounts")
        except Exception as e:
            logger.error(f"Daily reset failed: {e}")


def setup_scheduler():
    """Register all scheduler jobs and return the scheduler."""
    from services.imap_service import poll_all_accounts
    from services.gmail_service import poll_gmail_accounts
    from services.followup_service import send_due_followups
    from services.warmup_service import run_all_warmup_sessions

    # IMAP reply detection every 5 minutes
    scheduler.add_job(
        poll_all_accounts,
        IntervalTrigger(minutes=5),
        id="imap_poll",
        replace_existing=True,
        max_instances=1,
    )

    # Gmail API reply detection every 5 minutes
    scheduler.add_job(
        poll_gmail_accounts,
        IntervalTrigger(minutes=5),
        id="gmail_poll",
        replace_existing=True,
        max_instances=1,
    )

    # Follow-up sender every 15 minutes
    scheduler.add_job(
        send_due_followups,
        IntervalTrigger(minutes=15),
        id="followup_send",
        replace_existing=True,
        max_instances=1,
    )

    # Daily send count reset at midnight Karachi time
    scheduler.add_job(
        reset_daily_counts,
        CronTrigger(hour=0, minute=0, timezone="Asia/Karachi"),
        id="daily_reset",
        replace_existing=True,
    )

    # Warmup job at 9am Karachi time
    scheduler.add_job(
        run_all_warmup_sessions,
        CronTrigger(hour=9, minute=0, timezone="Asia/Karachi"),
        id="warmup_daily",
        replace_existing=True,
    )

    return scheduler
