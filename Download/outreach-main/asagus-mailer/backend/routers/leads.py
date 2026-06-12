"""
Lead file upload, CSV parsing, column mapping, and lead management.
"""

import os
import uuid
import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy import select, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import (
    Lead,
    LeadFile,
    GlobalSentEmail,
    Unsubscribe,
    Campaign,
    EmailLog,
    FollowupQueue,
    Reply,
)
from services.csv_service import parse_csv_preview, parse_csv_with_mapping

router = APIRouter(prefix="/api/leads", tags=["leads"])

UPLOADS_DIR = "uploads"
os.makedirs(UPLOADS_DIR, exist_ok=True)


@router.get("/files")
async def list_lead_files(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(LeadFile).order_by(LeadFile.uploaded_at.desc()))
    files = result.scalars().all()
    return [
        {
            "id": f.id, "filename": f.filename, "original_name": f.original_name,
            "total_leads": f.total_leads, "valid_leads": f.valid_leads,
            "duplicate_count": f.duplicate_count, "uploaded_at": f.uploaded_at,
        }
        for f in files
    ]


@router.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    """Upload CSV and return column preview + auto-detected mapping."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    content = await file.read()

    try:
        preview = parse_csv_preview(content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Save file temporarily
    filename = f"{uuid.uuid4()}.csv"
    filepath = os.path.join(UPLOADS_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(content)

    return {
        "temp_filename": filename,
        "original_name": file.filename,
        "columns": preview["columns"],
        "preview": preview["preview"],
        "auto_mapping": preview["auto_mapping"],
        "total_rows": preview["total_rows"],
    }


@router.post("/confirm-upload")
async def confirm_upload(
    temp_filename: str,
    original_name: str,
    email_col: str,
    name_col: str = None,
    business_col: str = None,
    phone_col: str = None,
    db: AsyncSession = Depends(get_db),
):
    """Confirm column mapping and insert leads into DB."""
    filepath = os.path.join(UPLOADS_DIR, temp_filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Temp file not found. Please re-upload.")

    with open(filepath, "rb") as f:
        content = f.read()

    # Get existing global sent emails for dedup info
    gs_result = await db.execute(select(GlobalSentEmail.email))
    existing_emails = {row[0] for row in gs_result.fetchall()}

    try:
        parsed = parse_csv_with_mapping(
            content=content,
            email_col=email_col,
            name_col=name_col,
            business_col=business_col,
            phone_col=phone_col,
            existing_emails=existing_emails,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Create lead file record
    lead_file = LeadFile(
        filename=temp_filename,
        original_name=original_name,
        total_leads=parsed["total"],
        valid_leads=parsed["valid"],
        duplicate_count=parsed["duplicates_in_file"],
    )
    db.add(lead_file)
    await db.flush()

    # Insert leads
    for lead_data in parsed["leads"]:
        lead = Lead(
            file_id=lead_file.id,
            email=lead_data["email"],
            name=lead_data["name"] or None,
            business_name=lead_data["business_name"] or None,
            phone=lead_data["phone"] or None,
            extra_data=lead_data["extra_data"],
            global_email_hash=lead_data["global_email_hash"],
            status="skipped" if lead_data.get("globally_sent") else "pending",
        )
        db.add(lead)

    await db.commit()
    await db.refresh(lead_file)

    # Clean up temp file
    try:
        os.remove(filepath)
    except Exception:
        pass

    return {
        "file_id": lead_file.id,
        "original_name": original_name,
        "total": parsed["total"],
        "valid": parsed["valid"],
        "invalid": parsed["invalid"],
        "duplicates_in_file": parsed["duplicates_in_file"],
        "already_sent_globally": parsed["already_sent_globally"],
    }


@router.get("/files/{file_id}")
async def get_leads_in_file(
    file_id: int,
    page: int = 1,
    page_size: int = 20,
    status: str = None,
    db: AsyncSession = Depends(get_db),
):
    lf_result = await db.execute(select(LeadFile).where(LeadFile.id == file_id))
    lf = lf_result.scalar_one_or_none()
    if not lf:
        raise HTTPException(status_code=404, detail="Lead file not found")

    query = select(Lead).where(Lead.file_id == file_id)
    if status:
        query = query.where(Lead.status == status)

    count_result = await db.execute(
        select(func.count(Lead.id)).where(Lead.file_id == file_id)
        if not status else
        select(func.count(Lead.id)).where(Lead.file_id == file_id, Lead.status == status)
    )
    total = count_result.scalar()

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    leads = result.scalars().all()

    return {
        "items": [
            {
                "id": l.id, "email": l.email, "name": l.name,
                "business_name": l.business_name, "phone": l.phone,
                "status": l.status, "created_at": l.created_at,
            }
            for l in leads
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total > 0 else 0,
    }


@router.get("/files/{file_id}/stats")
async def get_file_stats(file_id: int, db: AsyncSession = Depends(get_db)):
    lf_result = await db.execute(select(LeadFile).where(LeadFile.id == file_id))
    lf = lf_result.scalar_one_or_none()
    if not lf:
        raise HTTPException(status_code=404, detail="Lead file not found")

    statuses = {}
    for status in ["pending", "sent", "replied", "bounced", "unsubscribed", "skipped"]:
        count_result = await db.execute(
            select(func.count(Lead.id)).where(
                Lead.file_id == file_id, Lead.status == status
            )
        )
        statuses[status] = count_result.scalar() or 0

    # Count globally sent that are in this file
    gs_count_result = await db.execute(
        select(func.count(Lead.id)).where(
            Lead.file_id == file_id,
            Lead.status.notin_(["pending"]),
        )
    )

    total = sum(statuses.values())

    pending_result = await db.execute(
        select(Lead.email).where(Lead.file_id == file_id, Lead.status == "pending")
    )
    pending_emails = [row[0].lower() for row in pending_result.fetchall()]
    if pending_emails:
        gs_result = await db.execute(
            select(GlobalSentEmail.email).where(GlobalSentEmail.email.in_(pending_emails))
        )
        unsub_result = await db.execute(
            select(Unsubscribe.email).where(Unsubscribe.email.in_(pending_emails))
        )
        blocked = {row[0] for row in gs_result.fetchall()} | {row[0] for row in unsub_result.fetchall()}
        available = max(0, len(pending_emails) - len(blocked))
    else:
        available = 0

    return {
        "file_id": file_id,
        "original_name": lf.original_name,
        "total": total,
        "available": available,
        "sent": statuses["sent"],
        "replied": statuses["replied"],
        "bounced": statuses["bounced"],
        "unsubscribed": statuses["unsubscribed"],
        "skipped": statuses["skipped"],
    }


@router.delete("/files/{file_id}")
async def delete_lead_file(file_id: int, db: AsyncSession = Depends(get_db)):
    lf_result = await db.execute(select(LeadFile).where(LeadFile.id == file_id))
    lf = lf_result.scalar_one_or_none()
    if not lf:
        raise HTTPException(status_code=404, detail="Lead file not found")

    running_result = await db.execute(
        select(func.count(Campaign.id)).where(
            Campaign.lead_file_id == file_id,
            Campaign.status == "running",
        )
    )
    if (running_result.scalar() or 0) > 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete lead file while a campaign is running. Pause it first.",
        )

    lead_ids_subq = select(Lead.id).where(Lead.file_id == file_id)

    await db.execute(delete(Reply).where(Reply.lead_id.in_(lead_ids_subq)))
    await db.execute(delete(FollowupQueue).where(FollowupQueue.lead_id.in_(lead_ids_subq)))
    await db.execute(delete(EmailLog).where(EmailLog.lead_id.in_(lead_ids_subq)))
    await db.execute(
        update(Unsubscribe)
        .where(Unsubscribe.lead_id.in_(lead_ids_subq))
        .values(lead_id=None)
    )
    await db.execute(delete(Campaign).where(Campaign.lead_file_id == file_id))

    await db.delete(lf)
    await db.commit()
    return {"message": "Lead file deleted"}


@router.get("/{lead_id}")
async def get_lead_detail(lead_id: int, db: AsyncSession = Depends(get_db)):
    from models import EmailLog
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    logs_result = await db.execute(
        select(EmailLog).where(EmailLog.lead_id == lead_id).order_by(EmailLog.sent_at.desc())
    )
    logs = logs_result.scalars().all()

    return {
        "id": lead.id, "email": lead.email, "name": lead.name,
        "business_name": lead.business_name, "phone": lead.phone,
        "extra_data": json.loads(lead.extra_data) if lead.extra_data else {},
        "status": lead.status, "file_id": lead.file_id, "created_at": lead.created_at,
        "email_history": [
            {
                "id": l.id, "subject": l.subject, "sent_at": l.sent_at,
                "status": l.status, "is_followup": l.is_followup,
                "followup_day": l.followup_day,
            }
            for l in logs
        ],
    }


@router.get("/global-sent")
async def list_global_sent(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    count_result = await db.execute(select(func.count(GlobalSentEmail.id)))
    total = count_result.scalar()

    result = await db.execute(
        select(GlobalSentEmail)
        .order_by(GlobalSentEmail.first_sent_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()

    return {
        "items": [
            {
                "id": i.id, "email": i.email, "first_sent_at": i.first_sent_at,
                "campaign_id": i.campaign_id,
            }
            for i in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total > 0 else 0,
    }
