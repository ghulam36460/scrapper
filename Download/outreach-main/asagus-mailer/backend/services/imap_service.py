"""
IMAP polling service with multi-layer reply detection.
Handles bounce detection, unsubscribe intent from replies, and warmup email recognition.
"""

import imaplib
import email
import re
import logging
from datetime import datetime, timedelta
from email.utils import parseaddr, parsedate_to_datetime
from email.header import decode_header
from typing import Optional, Tuple

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from models import (
    SenderAccount, EmailLog, Lead, Reply, Unsubscribe, FollowupQueue, WarmupLog, WarmupSession
)
from crypto import decrypt_password
from services.template_service import normalize_subject

logger = logging.getLogger(__name__)


def decode_header_value(value: str) -> str:
    """Decode an email header value that may be encoded."""
    if not value:
        return ""
    try:
        parts = decode_header(value)
        decoded = ""
        for part, charset in parts:
            if isinstance(part, bytes):
                try:
                    decoded += part.decode(charset or "utf-8", errors="replace")
                except Exception:
                    decoded += part.decode("utf-8", errors="replace")
            else:
                decoded += str(part)
        return decoded.strip()
    except Exception:
        return str(value)


def get_email_body(msg) -> str:
    """Extract plain text body from email message, fallback to stripped HTML."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disp = str(part.get("Content-Disposition", ""))
            if "attachment" in content_disp:
                continue
            if content_type == "text/plain":
                try:
                    charset = part.get_content_charset() or "utf-8"
                    body = part.get_payload(decode=True).decode(charset, errors="replace")
                    break
                except Exception:
                    pass
            elif content_type == "text/html" and not body:
                try:
                    charset = part.get_content_charset() or "utf-8"
                    html = part.get_payload(decode=True).decode(charset, errors="replace")
                    body = re.sub(r'<[^>]+>', ' ', html)
                    body = re.sub(r'\s+', ' ', body).strip()
                except Exception:
                    pass
    else:
        try:
            charset = msg.get_content_charset() or "utf-8"
            body = msg.get_payload(decode=True).decode(charset, errors="replace")
        except Exception:
            body = str(msg.get_payload())

    return body.strip()


def similarity_score(s1: str, s2: str) -> float:
    """
    Simple token overlap similarity. Returns 0.0 to 1.0.
    """
    if not s1 or not s2:
        return 0.0
    tokens1 = set(s1.lower().split())
    tokens2 = set(s2.lower().split())
    if not tokens1 or not tokens2:
        return 0.0
    intersection = tokens1 & tokens2
    union = tokens1 | tokens2
    return len(intersection) / len(union) if union else 0.0


def check_for_unsubscribe_intent(body: str) -> bool:
    """Detect if reply body contains unsubscribe intent keywords."""
    keywords = [
        "unsubscribe", "remove me", "stop emailing", "take me off",
        "don't email", "do not email", "opt out", "opt-out",
        "please remove", "no more emails", "stop contacting", "leave me alone",
    ]
    body_lower = body.lower()
    return any(kw in body_lower for kw in keywords)


def check_for_bounce(subject: str, from_email: str) -> bool:
    """Detect if an incoming email is a bounce/delivery failure notification."""
    bounce_froms = ["mailer-daemon", "postmaster", "no-reply@bounce", "bounce", "noreply@"]
    bounce_subjects = [
        "delivery status notification", "mail delivery failed", "undeliverable",
        "delivery failure", "returned mail", "delivery report", "message not delivered",
        "failure notice", "non-delivery report", "could not be delivered",
    ]
    from_lower = from_email.lower()
    subject_lower = subject.lower() if subject else ""

    if any(bf in from_lower for bf in bounce_froms):
        return True
    if any(bs in subject_lower for bs in bounce_subjects):
        return True
    return False


async def match_reply_to_sent_email(
    from_email: str,
    subject: str,
    in_reply_to: Optional[str],
    references: Optional[str],
    db: AsyncSession,
) -> Tuple[Optional[EmailLog], str, float]:
    """
    Try 4 matching layers to link incoming reply to a sent email.
    Returns (EmailLog | None, method_name, confidence).
    """
    # LAYER 1: Message-ID exact match (confidence 1.0)
    message_ids_to_check = []
    if in_reply_to:
        message_ids_to_check.append(in_reply_to.strip())
    if references:
        for mid in references.split():
            message_ids_to_check.append(mid.strip())

    for mid in message_ids_to_check:
        if mid:
            result = await db.execute(
                select(EmailLog).where(EmailLog.message_id == mid)
            )
            matched = result.scalar_one_or_none()
            if matched:
                return (matched, "message_id", 1.0)

    # LAYER 2: Subject similarity match (confidence 0.7-0.9)
    norm_incoming = normalize_subject(subject)
    if norm_incoming:
        result = await db.execute(
            select(EmailLog).where(EmailLog.normalized_subject != None)
        )
        candidates = result.scalars().all()
        best_score = 0.0
        best_match = None
        for candidate in candidates:
            score = similarity_score(norm_incoming, candidate.normalized_subject or "")
            if score > best_score:
                best_score = score
                best_match = candidate

        if best_score > 0.7 and best_match:
            # Verify from_email matches the lead
            lead_result = await db.execute(
                select(Lead).where(Lead.id == best_match.lead_id)
            )
            lead = lead_result.scalar_one_or_none()
            if lead and lead.email.lower() == from_email.lower():
                confidence = min(0.9, 0.6 + best_score * 0.3)
                return (best_match, "subject_similarity", round(confidence, 2))

    # LAYER 3: Sender email match (confidence 0.6)
    lead_result = await db.execute(
        select(Lead).where(Lead.email == from_email.lower())
    )
    lead = lead_result.scalar_one_or_none()
    if lead:
        cutoff = datetime.utcnow() - timedelta(days=30)
        log_result = await db.execute(
            select(EmailLog).where(
                EmailLog.lead_id == lead.id,
                EmailLog.sent_at >= cutoff,
            ).order_by(EmailLog.sent_at.desc())
        )
        recent_log = log_result.scalars().first()
        if recent_log:
            return (recent_log, "sender_match", 0.6)

    # LAYER 4: Thread heuristic (confidence 0.5)
    if references:
        for mid in references.split():
            if "@asagus-mailer.local" in mid:
                # Try to find lead from from_email
                lead_result = await db.execute(
                    select(Lead).where(Lead.email == from_email.lower())
                )
                lead = lead_result.scalar_one_or_none()
                if lead:
                    log_result = await db.execute(
                        select(EmailLog).where(EmailLog.lead_id == lead.id)
                        .order_by(EmailLog.sent_at.desc())
                    )
                    recent_log = log_result.scalars().first()
                    if recent_log:
                        return (recent_log, "thread_heuristic", 0.5)

    return (None, "unmatched", 0.0)


async def poll_single_account(sender: SenderAccount, db: AsyncSession):
    """Poll IMAP for a single sender account and process replies."""
    if not sender.imap_host or sender.imap_host.strip() == "":
        return

    try:
        password = decrypt_password(sender.imap_password_enc)
    except Exception as e:
        logger.warning(f"IMAP: Could not decrypt password for {sender.email}: {e}")
        return

    # Get all our sender emails for warmup detection
    all_senders_result = await db.execute(select(SenderAccount.email))
    our_emails = {row[0].lower() for row in all_senders_result.fetchall()}

    try:
        mail = imaplib.IMAP4_SSL(sender.imap_host, sender.imap_port, timeout=30)
        mail.login(sender.email, password)
        mail.select("INBOX")

        # Build existing UID set for this sender to avoid duplicates
        cutoff = datetime.utcnow() - timedelta(days=60)
        existing_result = await db.execute(
            select(Reply.imap_uid).where(Reply.received_at >= cutoff)
        )
        existing_uids = set()
        prefix = f"{sender.id}:"
        for (val,) in existing_result.fetchall():
            if val and val.startswith(prefix):
                existing_uids.add(val)

        # Search emails (seen + unseen) from last 30 days
        since_date = (datetime.utcnow() - timedelta(days=30)).strftime("%d-%b-%Y")
        _, message_uids = mail.uid("search", None, f'(SINCE {since_date})')

        for uid in message_uids[0].split():
            try:
                uid_str = uid.decode() if isinstance(uid, (bytes, bytearray)) else str(uid)
                uid_key = f"{sender.id}:{uid_str}"
                if uid_key in existing_uids:
                    continue

                _, msg_data = mail.uid("fetch", uid, "(RFC822)")
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                from_raw = decode_header_value(msg.get("From", ""))
                from_name, from_email_addr = parseaddr(from_raw)
                from_email_addr = from_email_addr.lower().strip()

                subject = decode_header_value(msg.get("Subject", ""))
                in_reply_to = msg.get("In-Reply-To", "")
                references = msg.get("References", "")
                body = get_email_body(msg)

                # Parse date
                try:
                    date_header = msg.get("Date", "")
                    received_at = parsedate_to_datetime(date_header)
                    received_at = received_at.replace(tzinfo=None)  # Store as UTC naive
                except Exception:
                    received_at = datetime.utcnow()

                # Check if this is a warmup email from our own accounts
                if from_email_addr in our_emails:
                    # Mark as read without processing as reply
                    mail.uid("store", uid, '+FLAGS', '\\Seen')
                    # Log warmup receipt
                    ws_result = await db.execute(
                        select(WarmupSession).where(
                            WarmupSession.sender_account_id == sender.id,
                            WarmupSession.status == "active",
                        )
                    )
                    session = ws_result.scalar_one_or_none()
                    if session:
                        wl = WarmupLog(
                            session_id=session.id,
                            sender_account_id=sender.id,
                            direction="received",
                            to_from_email=from_email_addr,
                            subject=subject,
                            sent_at=received_at,
                            status="ok",
                        )
                        db.add(wl)
                        await db.commit()
                    continue

                # Check for bounce
                if check_for_bounce(subject, from_email_addr):
                    # Find lead and mark bounced
                    lead_result = await db.execute(
                        select(Lead).where(Lead.email == from_email_addr)
                    )
                    lead = lead_result.scalar_one_or_none()
                    if lead:
                        lead.status = "bounced"
                        # Cancel followups
                        await db.execute(
                            update(FollowupQueue).where(
                                FollowupQueue.lead_id == lead.id,
                                FollowupQueue.status == "pending",
                            ).values(status="cancelled")
                        )
                        await db.commit()
                    mail.uid("store", uid, '+FLAGS', '\\Seen')
                    continue

                # Match reply to sent email
                matched_log, method, confidence = await match_reply_to_sent_email(
                    from_email=from_email_addr,
                    subject=subject,
                    in_reply_to=in_reply_to,
                    references=references,
                    db=db,
                )

                # Check for unsubscribe intent
                is_auto_unsub = check_for_unsubscribe_intent(body)

                # Determine lead_id
                lead_id = None
                if matched_log:
                    lead_id = matched_log.lead_id
                else:
                    # Try to find lead directly by email
                    lead_result = await db.execute(
                        select(Lead).where(Lead.email == from_email_addr)
                    )
                    lead = lead_result.scalar_one_or_none()
                    if lead:
                        lead_id = lead.id

                if lead_id is None:
                    # Create a placeholder lead for tracking
                    mail.uid("store", uid, '+FLAGS', '\\Seen')
                    continue

                # Handle unsubscribe from reply
                if is_auto_unsub:
                    # Add to unsubscribes
                    existing_unsub = await db.execute(
                        select(Unsubscribe).where(Unsubscribe.email == from_email_addr)
                    )
                    if not existing_unsub.scalar_one_or_none():
                        unsub = Unsubscribe(
                            email=from_email_addr,
                            source="reply_keyword",
                            lead_id=lead_id,
                        )
                        db.add(unsub)

                    # Update lead status
                    lead_result = await db.execute(select(Lead).where(Lead.id == lead_id))
                    lead = lead_result.scalar_one_or_none()
                    if lead:
                        lead.status = "unsubscribed"

                    # Cancel followups
                    await db.execute(
                        update(FollowupQueue).where(
                            FollowupQueue.lead_id == lead_id,
                            FollowupQueue.status == "pending",
                        ).values(status="cancelled")
                    )

                # Update lead status to replied (if not unsubscribed)
                if not is_auto_unsub:
                    lead_result = await db.execute(select(Lead).where(Lead.id == lead_id))
                    lead = lead_result.scalar_one_or_none()
                    if lead and lead.status not in ("unsubscribed", "bounced"):
                        lead.status = "replied"

                    # Cancel pending followups for this lead
                    await db.execute(
                        update(FollowupQueue).where(
                            FollowupQueue.lead_id == lead_id,
                            FollowupQueue.status == "pending",
                        ).values(status="cancelled")
                    )

                # Save reply
                reply = Reply(
                    email_log_id=matched_log.id if matched_log else None,
                    lead_id=lead_id,
                    template_id=matched_log.template_id if matched_log else None,
                    from_email=from_email_addr,
                    from_name=from_name,
                    subject=subject,
                    body=body[:10000],  # Limit body size
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

                # Mark email as read in IMAP
                mail.uid("store", uid, '+FLAGS', '\\Seen')

            except Exception as e:
                logger.error(f"IMAP: Error processing email {num} for {sender.email}: {e}")
                continue

        mail.logout()

    except Exception as e:
        logger.error(f"IMAP: Connection failed for {sender.email}: {e}")


async def poll_all_accounts(db: AsyncSession = None):
    """
    Poll all active sender accounts for new replies.
    Called by APScheduler every 5 minutes.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(SenderAccount).where(
                SenderAccount.is_active == True,
                SenderAccount.auth_type != "gmail_api",
            )
        )
        senders = result.scalars().all()

        for sender in senders:
            try:
                await poll_single_account(sender, db)
            except Exception as e:
                logger.error(f"IMAP: Poll failed for {sender.email}: {e}")


async def fetch_gmail_sent_box(sender_account: SenderAccount, limit: int = 50) -> list:
    """
    Fetch last {limit} emails from the sender's IMAP Sent folder.
    Returns list of {subject, to, date, snippet}.
    """
    if not sender_account.imap_host:
        return []

    try:
        password = decrypt_password(sender_account.imap_password_enc)

        sent_folder = "[Gmail]/Sent Mail"
        if sender_account.provider == "zoho":
            sent_folder = "Sent"
        elif sender_account.provider == "other":
            sent_folder = "Sent"

        mail = imaplib.IMAP4_SSL(sender_account.imap_host, sender_account.imap_port, timeout=30)
        mail.login(sender_account.email, password)

        # Try different folder names
        folders_to_try = [sent_folder, "Sent", "[Gmail]/Sent Mail", "INBOX.Sent"]
        selected = False
        for folder in folders_to_try:
            try:
                status, _ = mail.select(folder)
                if status == "OK":
                    selected = True
                    break
            except Exception:
                continue

        if not selected:
            mail.logout()
            return []

        _, message_nums = mail.search(None, "ALL")
        nums = message_nums[0].split()

        # Get last {limit} messages
        nums = nums[-limit:] if len(nums) > limit else nums
        nums = list(reversed(nums))  # Newest first

        results = []
        for num in nums[:limit]:
            try:
                _, msg_data = mail.fetch(num, "(RFC822.HEADER RFC822.SIZE)")
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)

                subject = decode_header_value(msg.get("Subject", "(no subject)"))
                to = decode_header_value(msg.get("To", ""))
                date_str = msg.get("Date", "")
                try:
                    dt = parsedate_to_datetime(date_str)
                    date_formatted = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    date_formatted = date_str

                # Get snippet
                _, full_data = mail.fetch(num, "(RFC822)")
                full_msg = email.message_from_bytes(full_data[0][1])
                body = get_email_body(full_msg)
                snippet = body[:100].replace("\n", " ").strip() + "..." if len(body) > 100 else body

                results.append({
                    "subject": subject,
                    "to": to,
                    "date": date_formatted,
                    "snippet": snippet,
                })
            except Exception as e:
                logger.error(f"Sent box: Error fetching message {num}: {e}")
                continue

        mail.logout()
        return results

    except Exception as e:
        logger.error(f"Sent box: Failed for {sender_account.email}: {e}")
        return []
