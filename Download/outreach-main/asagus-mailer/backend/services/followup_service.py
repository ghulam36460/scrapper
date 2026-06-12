"""
Follow-up scheduling and sending service.
Sends day 3 and day 6 follow-up emails.
"""

import json
import random
import asyncio
import logging
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from models import (
    FollowupQueue, Campaign, Lead, EmailLog, EmailTemplate, SenderAccount
)
from services.template_service import render_template, generate_unsubscribe_token, normalize_subject
from services.sender_service import send_email, get_available_sender

logger = logging.getLogger(__name__)


async def send_due_followups(db: AsyncSession = None):
    """Send all due follow-up emails. Called by APScheduler every 15 minutes."""
    async with AsyncSessionLocal() as db:
        try:
            now = datetime.utcnow()
            result = await db.execute(
                select(FollowupQueue).where(
                    FollowupQueue.status == "pending",
                    FollowupQueue.scheduled_at <= now,
                )
            )
            due_items = result.scalars().all()
            logger.info(f"Follow-up: {len(due_items)} due items")

            for fq in due_items:
                try:
                    lead_result = await db.execute(select(Lead).where(Lead.id == fq.lead_id))
                    lead = lead_result.scalar_one_or_none()
                    if not lead or lead.status in ("replied", "unsubscribed", "bounced"):
                        fq.status = "cancelled"
                        await db.commit()
                        continue

                    campaign_result = await db.execute(select(Campaign).where(Campaign.id == fq.campaign_id))
                    campaign = campaign_result.scalar_one_or_none()
                    if not campaign:
                        fq.status = "cancelled"
                        await db.commit()
                        continue

                    if fq.followup_day == 3 and campaign.followup_day3_template_ids:
                        template_ids = json.loads(campaign.followup_day3_template_ids)
                    elif fq.followup_day == 6 and campaign.followup_day6_template_ids:
                        template_ids = json.loads(campaign.followup_day6_template_ids)
                    else:
                        template_ids = json.loads(campaign.initial_template_ids)

                    if not template_ids:
                        fq.status = "cancelled"
                        await db.commit()
                        continue

                    orig_result = await db.execute(select(EmailLog).where(EmailLog.id == fq.original_email_id))
                    original_email = orig_result.scalar_one_or_none()

                    template_id = random.choice(template_ids)
                    t_result = await db.execute(select(EmailTemplate).where(EmailTemplate.id == template_id))
                    template = t_result.scalar_one_or_none()
                    if not template:
                        fq.status = "cancelled"
                        await db.commit()
                        continue

                    sender_ids = json.loads(campaign.sender_account_ids)
                    sender_limits = json.loads(campaign.sender_limits) if campaign.sender_limits else {}

                    preferred_sender = None
                    if original_email:
                        pref_result = await db.execute(
                            select(SenderAccount).where(
                                SenderAccount.id == original_email.sender_account_id,
                                SenderAccount.is_active == True,
                            )
                        )
                        preferred_sender = pref_result.scalar_one_or_none()

                    if preferred_sender and preferred_sender.sent_today < preferred_sender.daily_limit:
                        sender = preferred_sender
                    else:
                        sender = await get_available_sender(db, sender_ids, campaign.id, sender_limits)

                    if not sender:
                        continue

                    unsub_token = generate_unsubscribe_token(lead.id, lead.email)
                    rendered = render_template(
                        template=template, lead=lead, sender=sender,
                        unsubscribe_token=unsub_token, lead_index=fq.id,
                        ab_enabled=campaign.ab_test_enabled,
                    )

                    thread_id = original_email.thread_id if original_email else None
                    message_id = f"<{uuid4()}@asagus-mailer.local>"
                    delay = random.uniform(30, 150)
                    await asyncio.sleep(delay)

                    result_send = await send_email(
                        db,
                        sender,
                        lead.email,
                        rendered["subject"],
                        rendered["body"],
                        message_id,
                        thread_id,
                    )

                    send_time = datetime.utcnow()
                    if result_send["success"]:
                        email_log = EmailLog(
                            lead_id=lead.id, campaign_id=campaign.id,
                            sender_account_id=sender.id, template_id=template.id,
                            subject=rendered["subject"],
                            subject_variant_index=rendered["subject_variant_index"],
                            body=rendered["body"], sent_at=send_time, status="sent",
                            is_followup=True, followup_day=fq.followup_day,
                            message_id=message_id, thread_id=thread_id or message_id,
                            normalized_subject=normalize_subject(rendered["subject"]),
                        )
                        db.add(email_log)
                        fq.status = "sent"
                        fq.sent_at = send_time
                        sender.sent_today += 1
                        sender.last_sent_at = send_time
                        await db.commit()

                except Exception as e:
                    logger.error(f"Follow-up {fq.id}: Error: {e}")

        except Exception as e:
            logger.error(f"Follow-up scheduler fatal: {e}", exc_info=True)
