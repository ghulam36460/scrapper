"""
All SQLAlchemy ORM models for the ASAGUS Mailer system.
Tables auto-create on startup via database.init_db().
"""

from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Date, Float,
    ForeignKey, Index
)
from sqlalchemy.orm import relationship
from database import Base


class SenderAccount(Base):
    __tablename__ = "sender_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    display_name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    smtp_host = Column(String, nullable=False)
    smtp_port = Column(Integer, nullable=False, default=587)
    smtp_password_enc = Column(String, nullable=False)
    smtp_use_tls = Column(Boolean, nullable=False, default=True)
    imap_host = Column(String, nullable=False, default="")
    imap_port = Column(Integer, nullable=False, default=993)
    imap_password_enc = Column(String, nullable=False)
    daily_limit = Column(Integer, nullable=False, default=40)
    sent_today = Column(Integer, nullable=False, default=0)
    last_sent_at = Column(DateTime, nullable=True)
    last_reset_date = Column(Date, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    provider = Column(String, default="other")
    warmup_enabled = Column(Boolean, default=False)
    warmup_day = Column(Integer, default=0)
    auth_type = Column(String, default="smtp")
    created_at = Column(DateTime, default=datetime.utcnow)

    email_logs = relationship("EmailLog", back_populates="sender_account")
    warmup_sessions = relationship("WarmupSession", back_populates="sender_account")
    warmup_logs = relationship("WarmupLog", back_populates="sender_account")
    gmail_token = relationship("GmailToken", back_populates="sender_account", uselist=False)


class LeadFile(Base):
    __tablename__ = "lead_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String, nullable=False)
    original_name = Column(String, nullable=False)
    total_leads = Column(Integer, default=0)
    valid_leads = Column(Integer, default=0)
    duplicate_count = Column(Integer, default=0)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    leads = relationship("Lead", back_populates="file", cascade="all, delete-orphan")
    campaigns = relationship("Campaign", back_populates="lead_file")


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey("lead_files.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=True)
    business_name = Column(String, nullable=True)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    extra_data = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="pending")
    global_email_hash = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    file = relationship("LeadFile", back_populates="leads")
    email_logs = relationship("EmailLog", back_populates="lead")
    followup_queues = relationship("FollowupQueue", back_populates="lead")
    replies = relationship("Reply", back_populates="lead")

    __table_args__ = (
        Index("idx_leads_email", "email"),
        Index("idx_leads_file_id", "file_id"),
        Index("idx_leads_status", "status"),
        Index("idx_leads_hash", "global_email_hash"),
    )


class GlobalSentEmail(Base):
    __tablename__ = "global_sent_emails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, nullable=False, unique=True)
    first_sent_at = Column(DateTime, default=datetime.utcnow)
    campaign_id = Column(Integer, nullable=True)
    lead_id = Column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_global_sent", "email"),
    )


class Unsubscribe(Base):
    __tablename__ = "unsubscribes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, nullable=False, unique=True)
    unsubscribed_at = Column(DateTime, default=datetime.utcnow)
    source = Column(String, default="manual")
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True)

    __table_args__ = (
        Index("idx_unsub_email", "email"),
    )


class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    template_type = Column(String, nullable=False, default="initial")
    subject_variants = Column(Text, nullable=False)
    body = Column(Text, nullable=False)
    ab_test_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    email_logs = relationship("EmailLog", back_populates="template")
    spam_checks = relationship("SpamCheckLog", back_populates="template")
    ab_test_results = relationship("ABTestResult", back_populates="template")


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    lead_file_id = Column(Integer, ForeignKey("lead_files.id"), nullable=False)
    initial_template_ids = Column(Text, nullable=False)
    followup_day3_template_ids = Column(Text, nullable=True)
    followup_day6_template_ids = Column(Text, nullable=True)
    sender_account_ids = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="draft")
    lead_limit = Column(Integer, nullable=True)
    total_targets = Column(Integer, default=0)
    sent_count = Column(Integer, default=0)
    current_lead_index = Column(Integer, default=0)
    ab_test_enabled = Column(Boolean, default=False)
    sender_limits = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    pause_reason = Column(String, nullable=True)

    lead_file = relationship("LeadFile", back_populates="campaigns")
    email_logs = relationship("EmailLog", back_populates="campaign")
    followup_queues = relationship("FollowupQueue", back_populates="campaign")
    ab_test_results = relationship("ABTestResult", back_populates="campaign")


class EmailLog(Base):
    __tablename__ = "email_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)
    sender_account_id = Column(Integer, ForeignKey("sender_accounts.id"), nullable=False)
    template_id = Column(Integer, ForeignKey("email_templates.id"), nullable=True)
    subject = Column(String, nullable=False)
    subject_variant_index = Column(Integer, default=0)
    body = Column(Text, nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="sent")
    is_followup = Column(Boolean, default=False)
    followup_day = Column(Integer, default=0)
    message_id = Column(String, nullable=True)
    thread_id = Column(String, nullable=True)
    normalized_subject = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)

    lead = relationship("Lead", back_populates="email_logs")
    campaign = relationship("Campaign", back_populates="email_logs")
    sender_account = relationship("SenderAccount", back_populates="email_logs")
    template = relationship("EmailTemplate", back_populates="email_logs")
    followup_queues = relationship("FollowupQueue", back_populates="original_email")
    replies = relationship("Reply", back_populates="email_log")

    __table_args__ = (
        Index("idx_email_log_lead_id", "lead_id"),
        Index("idx_email_log_sent_at", "sent_at"),
        Index("idx_email_log_campaign_id", "campaign_id"),
        Index("idx_email_log_message_id", "message_id"),
        Index("idx_email_log_norm_subject", "normalized_subject"),
    )


class FollowupQueue(Base):
    __tablename__ = "followup_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)
    original_email_id = Column(Integer, ForeignKey("email_log.id"), nullable=False)
    followup_day = Column(Integer, nullable=False)
    scheduled_at = Column(DateTime, nullable=False)
    status = Column(String, default="pending")
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    lead = relationship("Lead", back_populates="followup_queues")
    campaign = relationship("Campaign", back_populates="followup_queues")
    original_email = relationship("EmailLog", back_populates="followup_queues")

    __table_args__ = (
        Index("idx_followup_scheduled", "scheduled_at", "status"),
    )


class Reply(Base):
    __tablename__ = "replies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email_log_id = Column(Integer, ForeignKey("email_log.id"), nullable=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    template_id = Column(Integer, ForeignKey("email_templates.id"), nullable=True)
    from_email = Column(String, nullable=False)
    from_name = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    body = Column(Text, nullable=True)
    received_at = Column(DateTime, default=datetime.utcnow)
    imap_uid = Column(String, nullable=True)
    match_method = Column(String, nullable=True)
    match_confidence = Column(Float, default=1.0)
    is_read = Column(Boolean, default=False)
    is_auto_unsubscribe = Column(Boolean, default=False)
    replied_back = Column(Boolean, default=False)
    replied_at = Column(DateTime, nullable=True)
    reply_body = Column(Text, nullable=True)

    lead = relationship("Lead", back_populates="replies")
    email_log = relationship("EmailLog", back_populates="replies")

    __table_args__ = (
        Index("idx_replies_lead_id", "lead_id"),
        Index("idx_replies_read", "is_read"),
    )


class ABTestResult(Base):
    __tablename__ = "ab_test_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)
    template_id = Column(Integer, ForeignKey("email_templates.id"), nullable=True)
    subject_variant_index = Column(Integer, nullable=False)
    subject_text = Column(String, nullable=False)
    emails_sent = Column(Integer, default=0)
    replies_received = Column(Integer, default=0)
    recorded_at = Column(DateTime, default=datetime.utcnow)

    campaign = relationship("Campaign", back_populates="ab_test_results")
    template = relationship("EmailTemplate", back_populates="ab_test_results")


class WarmupSession(Base):
    __tablename__ = "warmup_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sender_account_id = Column(Integer, ForeignKey("sender_accounts.id"), nullable=False)
    day_number = Column(Integer, nullable=False, default=1)
    emails_sent_today = Column(Integer, default=0)
    target_today = Column(Integer, default=5)
    status = Column(String, default="active")
    started_at = Column(DateTime, default=datetime.utcnow)
    last_run_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    sender_account = relationship("SenderAccount", back_populates="warmup_sessions")
    logs = relationship("WarmupLog", back_populates="session")


class WarmupLog(Base):
    __tablename__ = "warmup_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("warmup_sessions.id"), nullable=False)
    sender_account_id = Column(Integer, ForeignKey("sender_accounts.id"), nullable=False)
    direction = Column(String, nullable=False)
    to_from_email = Column(String, nullable=False)
    subject = Column(String, nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="ok")

    session = relationship("WarmupSession", back_populates="logs")
    sender_account = relationship("SenderAccount", back_populates="warmup_logs")


class SpamCheckLog(Base):
    __tablename__ = "spam_check_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    template_id = Column(Integer, ForeignKey("email_templates.id"), nullable=True)
    subject = Column(String, nullable=False)
    body_preview = Column(Text, nullable=True)
    spam_score = Column(Float, nullable=False)
    flags = Column(Text, nullable=True)
    checked_at = Column(DateTime, default=datetime.utcnow)
    is_safe = Column(Boolean, nullable=True)

    template = relationship("EmailTemplate", back_populates="spam_checks")


class GmailToken(Base):
    __tablename__ = "gmail_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sender_account_id = Column(Integer, ForeignKey("sender_accounts.id", ondelete="CASCADE"), nullable=False, unique=True)
    refresh_token = Column(Text, nullable=False)
    access_token = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    scope = Column(Text, nullable=True)
    token_type = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    sender_account = relationship("SenderAccount", back_populates="gmail_token")


class IntegrationConfig(Base):
    __tablename__ = "integration_config"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow)


class OAuthState(Base):
    __tablename__ = "oauth_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    state = Column(String, nullable=False, unique=True)
    sender_account_id = Column(Integer, ForeignKey("sender_accounts.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
