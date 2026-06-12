"""
Email template CRUD + preview + spam check.
"""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import EmailTemplate, SpamCheckLog
from services.spam_service import check_spam_score
from services.template_service import render_template, generate_unsubscribe_token

router = APIRouter(prefix="/api/templates", tags=["templates"])


def template_to_response(t: EmailTemplate) -> dict:
    try:
        variants = json.loads(t.subject_variants)
    except Exception:
        variants = [t.subject_variants]
    return {
        "id": t.id,
        "name": t.name,
        "template_type": t.template_type,
        "subject_variants": variants,
        "body": t.body,
        "ab_test_enabled": t.ab_test_enabled,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
    }


@router.get("")
async def list_templates(
    template_type: str = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(EmailTemplate).order_by(EmailTemplate.created_at.desc())
    if template_type:
        query = query.where(EmailTemplate.template_type == template_type)
    result = await db.execute(query)
    templates = result.scalars().all()
    return [template_to_response(t) for t in templates]


@router.post("")
async def create_template(
    name: str,
    template_type: str = "initial",
    subject_variants: str = None,
    body: str = "",
    ab_test_enabled: bool = False,
    db: AsyncSession = Depends(get_db),
):
    if not subject_variants:
        subject_variants = ["Subject line here"]
    else:
        try:
            subject_variants = json.loads(subject_variants)
        except Exception:
            subject_variants = [subject_variants]

    t = EmailTemplate(
        name=name,
        template_type=template_type,
        subject_variants=json.dumps(subject_variants),
        body=body,
        ab_test_enabled=ab_test_enabled,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return template_to_response(t)


@router.put("/{template_id}")
async def update_template(
    template_id: int,
    name: str = None,
    template_type: str = None,
    subject_variants: str = None,
    body: str = None,
    ab_test_enabled: bool = None,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(EmailTemplate).where(EmailTemplate.id == template_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")

    if name is not None:
        t.name = name
    if template_type is not None:
        t.template_type = template_type
    if subject_variants is not None:
        try:
            parsed = json.loads(subject_variants)
        except Exception:
            parsed = [subject_variants]
        t.subject_variants = json.dumps(parsed)
    if body is not None:
        t.body = body
    if ab_test_enabled is not None:
        t.ab_test_enabled = ab_test_enabled
    t.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(t)
    return template_to_response(t)


@router.delete("/{template_id}")
async def delete_template(template_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EmailTemplate).where(EmailTemplate.id == template_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    await db.delete(t)
    await db.commit()
    return {"message": "Template deleted"}


@router.post("/{template_id}/preview")
async def preview_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(EmailTemplate).where(EmailTemplate.id == template_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")

    # Create mock objects for rendering
    class MockLead:
        id = 0
        name = "John Smith"
        business_name = "Smith & Co."
        email = "john@example.com"

    class MockSender:
        display_name = "Your Name"
        email = "you@example.com"

    token = generate_unsubscribe_token(0, "john@example.com")
    rendered = render_template(
        template=t,
        lead=MockLead(),
        sender=MockSender(),
        unsubscribe_token=token,
        lead_index=0,
        ab_enabled=t.ab_test_enabled,
    )

    return {
        "subject": rendered["subject"],
        "body": rendered["body"],
        "subject_variant_index": rendered["subject_variant_index"],
        "has_unsubscribe": "unsubscribe" in rendered["body"].lower(),
    }


@router.post("/{template_id}/spam-check")
async def spam_check_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(EmailTemplate).where(EmailTemplate.id == template_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")

    try:
        variants = json.loads(t.subject_variants)
        subject = variants[0] if variants else ""
    except Exception:
        subject = t.subject_variants or ""

    score_result = check_spam_score(subject, t.body)

    # Log the check
    log = SpamCheckLog(
        template_id=template_id,
        subject=subject,
        body_preview=t.body[:500],
        spam_score=score_result["score"],
        flags=json.dumps(score_result["flags"]),
        is_safe=score_result["is_safe"],
    )
    db.add(log)
    await db.commit()

    return score_result
