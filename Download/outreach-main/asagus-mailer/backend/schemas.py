"""
All Pydantic schemas for request/response models.
Passwords are NEVER returned in API responses - only has_password: bool.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime


# ── Sender Accounts ──────────────────────────────────────────────────────────

class SenderAccountCreate(BaseModel):
    display_name: str
    email: str
    smtp_host: str
    smtp_port: int = 587
    smtp_password: Optional[str] = None
    smtp_use_tls: bool = True
    imap_host: str = ""
    imap_port: int = 993
    imap_password: Optional[str] = ""
    daily_limit: int = 40
    is_active: bool = True
    provider: str = "other"
    auth_type: str = "smtp"


class SenderAccountUpdate(BaseModel):
    display_name: Optional[str] = None
    email: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_password: Optional[str] = None
    smtp_use_tls: Optional[bool] = None
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None
    imap_password: Optional[str] = None
    daily_limit: Optional[int] = None
    is_active: Optional[bool] = None
    provider: Optional[str] = None
    auth_type: Optional[str] = None


class TestConnectionRequest(BaseModel):
    smtp_password: Optional[str] = None
    imap_password: Optional[str] = None


class SenderAccountResponse(BaseModel):
    id: int
    display_name: str
    email: str
    smtp_host: str
    smtp_port: int
    smtp_use_tls: bool
    imap_host: str
    imap_port: int
    daily_limit: int
    sent_today: int
    last_sent_at: Optional[datetime] = None
    is_active: bool
    provider: str
    warmup_enabled: bool
    warmup_day: int
    created_at: datetime
    has_password: bool = True
    auth_type: str = "smtp"
    gmail_connected: bool = False

    class Config:
        from_attributes = True


class SenderStatsResponse(BaseModel):
    id: int
    email: str
    sent_today: int
    daily_limit: int
    remaining: int
    warmup_status: str
    warmup_day: int


# ── Lead Files ────────────────────────────────────────────────────────────────

class LeadFileResponse(BaseModel):
    id: int
    filename: str
    original_name: str
    total_leads: int
    valid_leads: int
    duplicate_count: int
    uploaded_at: datetime

    class Config:
        from_attributes = True


class LeadResponse(BaseModel):
    id: int
    file_id: int
    name: Optional[str] = None
    business_name: Optional[str] = None
    email: str
    phone: Optional[str] = None
    extra_data: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class ColumnMappingRequest(BaseModel):
    file_id: int
    email_col: str
    name_col: Optional[str] = None
    business_col: Optional[str] = None
    phone_col: Optional[str] = None


# ── Templates ─────────────────────────────────────────────────────────────────

class TemplateCreate(BaseModel):
    name: str
    template_type: str = "initial"
    subject_variants: List[str]
    body: str
    ab_test_enabled: bool = False


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    template_type: Optional[str] = None
    subject_variants: Optional[List[str]] = None
    body: Optional[str] = None
    ab_test_enabled: Optional[bool] = None


class TemplateResponse(BaseModel):
    id: int
    name: str
    template_type: str
    subject_variants: List[str]
    body: str
    ab_test_enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Campaigns ─────────────────────────────────────────────────────────────────

class CampaignCreate(BaseModel):
    name: str
    lead_file_id: int
    initial_template_ids: List[int]
    followup_day3_template_ids: Optional[List[int]] = None
    followup_day6_template_ids: Optional[List[int]] = None
    sender_account_ids: List[int]
    lead_limit: Optional[int] = None
    ab_test_enabled: bool = False
    sender_limits: Optional[Dict[str, int]] = None


class CampaignResponse(BaseModel):
    id: int
    name: str
    lead_file_id: int
    initial_template_ids: List[int]
    followup_day3_template_ids: Optional[List[int]] = None
    followup_day6_template_ids: Optional[List[int]] = None
    sender_account_ids: List[int]
    status: str
    lead_limit: Optional[int] = None
    total_targets: int
    sent_count: int
    current_lead_index: int
    ab_test_enabled: bool
    sender_limits: Optional[Dict[str, int]] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    pause_reason: Optional[str] = None

    class Config:
        from_attributes = True


class CampaignProgressResponse(BaseModel):
    id: int
    status: str
    sent_count: int
    total_targets: int
    current_lead_index: int
    pause_reason: Optional[str] = None
    started_at: Optional[datetime] = None


# ── Email Log ─────────────────────────────────────────────────────────────────

class EmailLogResponse(BaseModel):
    id: int
    lead_id: int
    campaign_id: Optional[int] = None
    sender_account_id: int
    template_id: Optional[int] = None
    subject: str
    subject_variant_index: int
    body: str
    sent_at: datetime
    status: str
    is_followup: bool
    followup_day: int
    message_id: Optional[str] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


# ── Follow-ups ────────────────────────────────────────────────────────────────

class FollowupQueueResponse(BaseModel):
    id: int
    lead_id: int
    campaign_id: Optional[int] = None
    original_email_id: int
    followup_day: int
    scheduled_at: datetime
    status: str
    sent_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Replies ───────────────────────────────────────────────────────────────────

class ReplyResponse(BaseModel):
    id: int
    email_log_id: Optional[int] = None
    lead_id: int
    from_email: str
    from_name: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    received_at: datetime
    match_method: Optional[str] = None
    match_confidence: float
    is_read: bool
    is_auto_unsubscribe: bool
    replied_back: bool
    replied_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReplyBackRequest(BaseModel):
    body: str


# ── Warmup ────────────────────────────────────────────────────────────────────

class WarmupSessionResponse(BaseModel):
    id: int
    sender_account_id: int
    day_number: int
    emails_sent_today: int
    target_today: int
    status: str
    started_at: datetime
    last_run_at: Optional[datetime] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


# ── Unsubscribes ──────────────────────────────────────────────────────────────

class UnsubscribeCreate(BaseModel):
    email: str
    source: str = "manual"


class UnsubscribeResponse(BaseModel):
    id: int
    email: str
    unsubscribed_at: datetime
    source: str
    lead_id: Optional[int] = None

    class Config:
        from_attributes = True


# ── Spam Check ────────────────────────────────────────────────────────────────

class SpamCheckResponse(BaseModel):
    score: float
    is_safe: bool
    flags: List[Dict[str, Any]]
    recommendation: str


# ── Analytics ─────────────────────────────────────────────────────────────────

class AnalyticsOverviewResponse(BaseModel):
    total_sent: int
    total_replies: int
    reply_rate: float
    bounce_rate: float
    total_unsubscribes: int
    avg_spam_score: float


# ── Generic ───────────────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    pages: int
