"""
SMTP sending engine with sender rotation, delays, dedup, and campaign execution.
"""

import smtplib
import ssl
import asyncio
import random
import json
import re
import logging
import time
from uuid import uuid4
from datetime import datetime, date, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr, make_msgid
from typing import Optional, List

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from models import (
    SenderAccount, Lead, Campaign, EmailLog, GlobalSentEmail,
    Unsubscribe, EmailTemplate, FollowupQueue, ABTestResult
)
from crypto import decrypt_password
from services.template_service import render_template, generate_unsubscribe_token, normalize_subject
from services.gmail_service import gmail_send_message
from services.spam_service import check_spam_score

logger = logging.getLogger(__name__)

# Global dict tracking running campaigns (campaign_id -> True)
RUNNING_CAMPAIGNS = {}


def normalize_email(email: str) -> str:
    """Lowercase + strip whitespace."""
    return str(email).strip().lower()


async def is_globally_sent(email: str, db: AsyncSession) -> bool:
    """Check global_sent_emails table."""
    norm = normalize_email(email)
    result = await db.execute(
        select(GlobalSentEmail).where(GlobalSentEmail.email == norm)
    )
    return result.scalar_one_or_none() is not None


async def is_unsubscribed(email: str, db: AsyncSession) -> bool:
    """Check unsubscribes table."""
    norm = normalize_email(email)
    result = await db.execute(
        select(Unsubscribe).where(Unsubscribe.email == norm)
    )
    return result.scalar_one_or_none() is not None


async def get_campaign_sent_by_sender(campaign_id: int, sender_id: int, db: AsyncSession) -> int:
    """Get count of emails sent by a specific sender in a campaign."""
    result = await db.execute(
        select(func.count(EmailLog.id)).where(
            EmailLog.campaign_id == campaign_id,
            EmailLog.sender_account_id == sender_id,
            EmailLog.is_followup == False,
        )
    )
    return result.scalar() or 0


async def get_available_sender(
    db: AsyncSession,
    sender_ids: List[int],
    campaign_id: int,
    sender_limits: dict,
) -> Optional[SenderAccount]:
    """
    Return the best available sender from the list.
    Checks: is_active, sent_today < daily_limit, campaign limit not exceeded.
    Returns sender with oldest last_sent_at for fair rotation.
    Returns None if all senders are at limit.
    """
    today = date.today()
    candidates = []

    for sid in sender_ids:
        result = await db.execute(
            select(SenderAccount).where(SenderAccount.id == sid, SenderAccount.is_active == True)
        )
        sender = result.scalar_one_or_none()
        if not sender:
            continue

        # Reset daily count if needed
        if sender.last_reset_date != today:
            sender.sent_today = 0
            sender.last_reset_date = today
            await db.commit()

        # Check daily limit
        if sender.sent_today >= sender.daily_limit:
            continue

        # Check campaign-level limit
        campaign_limit = sender_limits.get(str(sid), sender_limits.get(sid, 9999))
        campaign_sent = await get_campaign_sent_by_sender(campaign_id, sid, db)
        if campaign_sent >= campaign_limit:
            continue

        candidates.append(sender)

    if not candidates:
        return None

    # Return sender with oldest last_sent_at (fair rotation)
    candidates.sort(key=lambda s: s.last_sent_at or datetime.min)
    return candidates[0]


def build_email_message(
    sender: SenderAccount,
    to_email: str,
    subject: str,
    body: str,
    message_id: str,
    thread_id: Optional[str] = None,
) -> MIMEMultipart:
    """Build a MIMEMultipart email message with all proper headers."""
    msg = MIMEMultipart("alternative")
    msg["From"] = formataddr((sender.display_name, sender.email))
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["Message-ID"] = message_id
    msg["X-Mailer"] = "ASAGUS Mailer"

    if thread_id:
        msg["In-Reply-To"] = thread_id
        msg["References"] = thread_id

    # Plain text part
    plain_body = re.sub(r'<[^>]+>', '', body)
    msg.attach(MIMEText(plain_body, "plain", "utf-8"))

    # HTML part
    html_body = body if "<" in body else f"<p>{body.replace(chr(10), '<br>')}</p>"
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    return msg


def send_email_sync(
    sender: SenderAccount,
    to_email: str,
    subject: str,
    body: str,
    message_id: str,
    thread_id: Optional[str] = None,
) -> dict:
    """
    Synchronous SMTP send. Returns {"success": bool, "message_id": str, "error": str|None}.
    """
    max_attempts = 3
    last_error = None

    for attempt in range(1, max_attempts + 1):
        try:
            password = decrypt_password(sender.smtp_password_enc)
            msg = build_email_message(sender, to_email, subject, body, message_id, thread_id)

            ctx = ssl.create_default_context()

            # Port 465 typically requires implicit SSL even if smtp_use_tls is True.
            use_ssl = (not sender.smtp_use_tls) or sender.smtp_port == 465

            if not use_ssl:
                # STARTTLS
                with smtplib.SMTP(sender.smtp_host, sender.smtp_port, timeout=30) as smtp:
                    smtp.ehlo()
                    smtp.starttls(context=ctx)
                    smtp.ehlo()
                    smtp.login(sender.email, password)
                    smtp.sendmail(sender.email, to_email, msg.as_string())
            else:
                # SSL
                with smtplib.SMTP_SSL(sender.smtp_host, sender.smtp_port, context=ctx, timeout=30) as smtp:
                    smtp.ehlo()
                    smtp.login(sender.email, password)
                    smtp.sendmail(sender.email, to_email, msg.as_string())

            return {"success": True, "message_id": message_id, "error": None, "error_type": None}

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP auth failed for {sender.email} -> {to_email}: {e}")
            return {"success": False, "message_id": message_id, "error": str(e), "error_type": "auth"}
        except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, TimeoutError, OSError) as e:
            last_error = e
            logger.error(f"SMTP transient error for {sender.email} -> {to_email}: {e}")
            if attempt < max_attempts:
                time.sleep(1.5 * attempt)
                continue
            return {"success": False, "message_id": message_id, "error": str(e), "error_type": "connect"}
        except Exception as e:
            last_error = e
            logger.error(f"SMTP send failed to {to_email}: {e}")
            return {"success": False, "message_id": message_id, "error": str(e), "error_type": "other"}

    return {"success": False, "message_id": message_id, "error": str(last_error) if last_error else "Unknown error", "error_type": "other"}


async def send_email(
    db: AsyncSession,
    sender: SenderAccount,
    to_email: str,
    subject: str,
    body: str,
    message_id: str,
    thread_id: Optional[str] = None,
) -> dict:
    """Send email using SMTP or Gmail API based on sender auth_type."""
    if (sender.auth_type or "smtp") == "gmail_api":
        try:
            msg = build_email_message(sender, to_email, subject, body, message_id, thread_id)
            return await gmail_send_message(db, sender.id, msg.as_string())
        except Exception as e:
            logger.error(f"Gmail API send failed for {sender.email} -> {to_email}: {e}")
            return {"success": False, "message_id": message_id, "error": str(e), "error_type": "gmail_api"}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, send_email_sync, sender, to_email, subject, body, message_id, thread_id
    )


async def schedule_followups_for_lead(
    lead_id: int,
    campaign_id: int,
    email_log_id: int,
    sent_at: datetime,
    db: AsyncSession,
):
    """Insert day 3 and day 6 follow-up queue entries for a lead."""
    # Check if followups already exist for this lead in this campaign
    existing = await db.execute(
        select(FollowupQueue).where(
            FollowupQueue.lead_id == lead_id,
            FollowupQueue.campaign_id == campaign_id,
            FollowupQueue.status == "pending",
        )
    )
    if existing.scalars().first():
        return  # Already scheduled

    for day in [3, 6]:
        fq = FollowupQueue(
            lead_id=lead_id,
            campaign_id=campaign_id,
            original_email_id=email_log_id,
            followup_day=day,
            scheduled_at=sent_at + timedelta(days=day),
            status="pending",
        )
        db.add(fq)

    await db.commit()


async def update_ab_test_results(
    campaign_id: int,
    template_id: int,
    variant_index: int,
    subject_text: str,
    db: AsyncSession,
):
    """Update or create AB test result entry for a sent email."""
    result = await db.execute(
        select(ABTestResult).where(
            ABTestResult.campaign_id == campaign_id,
            ABTestResult.template_id == template_id,
            ABTestResult.subject_variant_index == variant_index,
        )
    )
    ab = result.scalar_one_or_none()
    if ab:
        ab.emails_sent += 1
    else:
        ab = ABTestResult(
            campaign_id=campaign_id,
            template_id=template_id,
            subject_variant_index=variant_index,
            subject_text=subject_text,
            emails_sent=1,
        )
        db.add(ab)
    await db.commit()


async def run_campaign_sending(campaign_id: int):
    """
    Full async campaign sending loop. Runs as a background task.
    """
    RUNNING_CAMPAIGNS[campaign_id] = True
    logger.info(f"Campaign {campaign_id}: Starting send loop")

    async with AsyncSessionLocal() as db:
        try:
            # Load campaign
            result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
            campaign = result.scalar_one_or_none()
            if not campaign:
                logger.error(f"Campaign {campaign_id} not found")
                return

            if campaign.status not in ("running",):
                logger.info(f"Campaign {campaign_id} not in running state: {campaign.status}")
                return

            sender_ids = json.loads(campaign.sender_account_ids)
            initial_template_ids = json.loads(campaign.initial_template_ids)
            sender_limits = json.loads(campaign.sender_limits) if campaign.sender_limits else {}

            # Get global sent emails for dedup
            gs_result = await db.execute(select(GlobalSentEmail.email))
            global_sent_set = {row[0] for row in gs_result.fetchall()}

            # Get unsubscribed emails
            unsub_result = await db.execute(select(Unsubscribe.email))
            unsub_set = {row[0] for row in unsub_result.fetchall()}

            # Query pending leads from this file
            leads_result = await db.execute(
                select(Lead).where(
                    Lead.file_id == campaign.lead_file_id,
                    Lead.status == "pending",
                ).order_by(Lead.id)
            )
            all_leads = leads_result.scalars().all()

            # Filter out globally sent and unsubscribed
            blocked_global = []
            blocked_unsub = []
            available_leads = []
            for l in all_leads:
                norm_email = normalize_email(l.email)
                if norm_email in unsub_set:
                    blocked_unsub.append(l)
                elif norm_email in global_sent_set:
                    blocked_global.append(l)
                else:
                    available_leads.append(l)

            # Keep lead statuses consistent with filters
            if blocked_unsub:
                for l in blocked_unsub:
                    l.status = "unsubscribed"
            if blocked_global:
                for l in blocked_global:
                    l.status = "skipped"
            if blocked_unsub or blocked_global:
                await db.commit()

            # Apply lead limit
            if campaign.lead_limit and campaign.lead_limit > 0:
                available_leads = available_leads[:campaign.lead_limit]

            # Update total targets
            campaign.total_targets = len(available_leads)
            await db.commit()

            if campaign.total_targets == 0:
                campaign.status = "paused"
                campaign.pause_reason = "No available leads after filters"
                await db.commit()
                logger.info(f"Campaign {campaign_id}: No available leads. Paused.")
                return

            logger.info(f"Campaign {campaign_id}: Sending to {len(available_leads)} leads")

            failed_count = 0
            skipped_count = 0
            last_error = None

            for idx, lead in enumerate(available_leads):
                # Check if campaign is still running
                result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
                campaign = result.scalar_one_or_none()
                if not campaign or campaign.status != "running":
                    logger.info(f"Campaign {campaign_id}: Paused or stopped")
                    break

                norm_email = normalize_email(lead.email)

                # Double-check dedup
                if norm_email in global_sent_set or norm_email in unsub_set:
                    lead.status = "skipped"
                    await db.commit()
                    continue

                # Get available sender
                sender = await get_available_sender(db, sender_ids, campaign_id, sender_limits)
                if not sender:
                    campaign.status = "paused"
                    campaign.pause_reason = "All sender accounts reached daily limit"
                    await db.commit()
                    logger.warning(f"Campaign {campaign_id}: All senders at daily limit. Paused.")
                    break

                # Pick random template
                template_id = random.choice(initial_template_ids)
                t_result = await db.execute(select(EmailTemplate).where(EmailTemplate.id == template_id))
                template = t_result.scalar_one_or_none()
                if not template:
                    continue

                # Generate unsubscribe token
                unsub_token = generate_unsubscribe_token(lead.id, lead.email)

                # Render template
                rendered = render_template(
                    template=template,
                    lead=lead,
                    sender=sender,
                    unsubscribe_token=unsub_token,
                    lead_index=campaign.sent_count + idx,
                    ab_enabled=campaign.ab_test_enabled,
                )

                # Spam check - skip if score > 7.0
                spam_result = check_spam_score(rendered["subject"], rendered["body"])
                if spam_result["score"] > 7.0:
                    logger.warning(
                        f"Campaign {campaign_id}: Skipping {lead.email} - spam score {spam_result['score']}"
                    )
                    lead.status = "skipped"
                    email_log = EmailLog(
                        lead_id=lead.id,
                        campaign_id=campaign_id,
                        sender_account_id=sender.id,
                        template_id=template.id,
                        subject=rendered["subject"],
                        subject_variant_index=rendered["subject_variant_index"],
                        body=rendered["body"],
                        sent_at=datetime.utcnow(),
                        status="skipped",
                        is_followup=False,
                        followup_day=0,
                        message_id=None,
                        normalized_subject=normalize_subject(rendered["subject"]),
                        error_message=f"Spam score {spam_result['score']}"
                    )
                    db.add(email_log)
                    await db.commit()
                    skipped_count += 1
                    continue

                # Generate message ID
                message_id = f"<{uuid4()}@asagus-mailer.local>"

                # Random delay between sends
                delay = random.uniform(30, 150)
                await asyncio.sleep(delay)

                # Send email
                result_send = await send_email(
                    db,
                    sender,
                    lead.email,
                    rendered["subject"],
                    rendered["body"],
                    message_id,
                    None,
                )

                now = datetime.utcnow()
                norm_subj = normalize_subject(rendered["subject"])

                if result_send["success"]:
                    # Log email
                    email_log = EmailLog(
                        lead_id=lead.id,
                        campaign_id=campaign_id,
                        sender_account_id=sender.id,
                        template_id=template.id,
                        subject=rendered["subject"],
                        subject_variant_index=rendered["subject_variant_index"],
                        body=rendered["body"],
                        sent_at=now,
                        status="sent",
                        is_followup=False,
                        followup_day=0,
                        message_id=message_id,
                        thread_id=message_id,
                        normalized_subject=norm_subj,
                    )
                    db.add(email_log)
                    await db.flush()

                    # Add to global sent
                    gs = GlobalSentEmail(
                        email=norm_email,
                        first_sent_at=now,
                        campaign_id=campaign_id,
                        lead_id=lead.id,
                    )
                    db.add(gs)
                    global_sent_set.add(norm_email)

                    # Update lead status
                    lead.status = "sent"

                    # Update sender stats
                    sender.sent_today += 1
                    sender.last_sent_at = now

                    # Update campaign stats
                    campaign.sent_count += 1
                    campaign.current_lead_index = idx + 1

                    await db.commit()

                    # Schedule follow-ups
                    await schedule_followups_for_lead(
                        lead_id=lead.id,
                        campaign_id=campaign_id,
                        email_log_id=email_log.id,
                        sent_at=now,
                        db=db,
                    )

                    # Update A/B test results
                    if campaign.ab_test_enabled:
                        await update_ab_test_results(
                            campaign_id=campaign_id,
                            template_id=template.id,
                            variant_index=rendered["subject_variant_index"],
                            subject_text=rendered["subject"],
                            db=db,
                        )
                else:
                    # Log failure
                    email_log = EmailLog(
                        lead_id=lead.id,
                        campaign_id=campaign_id,
                        sender_account_id=sender.id,
                        template_id=template.id,
                        subject=rendered["subject"],
                        subject_variant_index=rendered["subject_variant_index"],
                        body=rendered["body"],
                        sent_at=now,
                        status="failed",
                        is_followup=False,
                        followup_day=0,
                        message_id=message_id,
                        normalized_subject=norm_subj,
                        error_message=result_send["error"],
                    )
                    db.add(email_log)
                    await db.commit()
                    failed_count += 1
                    last_error = result_send.get("error")

                    if result_send.get("error_type") == "auth":
                        campaign.status = "paused"
                        campaign.pause_reason = f"SMTP auth failed for {sender.email}. Recheck app password."
                        await db.commit()
                        logger.warning(
                            f"Campaign {campaign_id}: Paused due to SMTP auth failure for {sender.email}"
                        )
                        break

                    if failed_count >= 3 and campaign.sent_count == 0:
                        campaign.status = "paused"
                        campaign.pause_reason = f"Repeated send failures. Last error: {str(last_error)[:120]}"
                        await db.commit()
                        logger.warning(
                            f"Campaign {campaign_id}: Paused after repeated failures"
                        )
                        break

            # Mark campaign completed
            result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
            campaign = result.scalar_one_or_none()
            if campaign and campaign.status == "running":
                if campaign.sent_count > 0:
                    campaign.status = "completed"
                    campaign.completed_at = datetime.utcnow()
                    await db.commit()
                    logger.info(f"Campaign {campaign_id}: Completed. Sent {campaign.sent_count} emails.")
                else:
                    campaign.status = "paused"
                    if failed_count > 0:
                        campaign.pause_reason = f"All sends failed. Last error: {str(last_error)[:120]}"
                    else:
                        campaign.pause_reason = "No deliverable leads after filters"
                    await db.commit()
                    logger.info(f"Campaign {campaign_id}: Paused with zero sends.")

        except Exception as e:
            logger.error(f"Campaign {campaign_id}: Fatal error: {e}", exc_info=True)
            async with AsyncSessionLocal() as err_db:
                result = await err_db.execute(select(Campaign).where(Campaign.id == campaign_id))
                campaign = result.scalar_one_or_none()
                if campaign:
                    campaign.status = "paused"
                    campaign.pause_reason = f"Error: {str(e)[:200]}"
                    await err_db.commit()
        finally:
            RUNNING_CAMPAIGNS.pop(campaign_id, None)
