"""
Jinja2 template rendering + A/B subject line logic.
Handles variable substitution and unsubscribe token generation.
"""

import json
import hashlib
import os
import re
from typing import Tuple


def pick_subject_variant(subject_variants_json: str, lead_index: int, ab_enabled: bool) -> Tuple[str, int]:
    """
    Pick the correct subject line variant for this lead.
    If A/B test enabled, distribute evenly by lead_index modulo number of variants.
    Returns (subject_string, variant_index).
    """
    try:
        variants = json.loads(subject_variants_json)
    except (json.JSONDecodeError, TypeError):
        variants = [subject_variants_json] if subject_variants_json else ["No subject"]

    if not variants:
        return ("No subject", 0)

    if ab_enabled and len(variants) > 1:
        idx = lead_index % len(variants)
        return (variants[idx], idx)

    return (variants[0], 0)


def generate_unsubscribe_token(lead_id: int, email: str) -> str:
    """Generate a unique unsubscribe token for a lead."""
    secret = os.environ.get("SECRET_KEY", "default-secret")
    data = f"{lead_id}:{email}:{secret}"
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def render_jinja_string(template_str: str, context: dict) -> str:
    """Render a template string with simple variable substitution."""
    result = template_str
    for key, value in context.items():
        result = result.replace("{{" + key + "}}", str(value) if value else "")
        result = result.replace("{{ " + key + " }}", str(value) if value else "")
    return result


def render_template(
    template,
    lead,
    sender,
    unsubscribe_token: str,
    lead_index: int,
    ab_enabled: bool,
) -> dict:
    """
    Render an email template for a specific lead and sender.
    Returns {"subject": str, "body": str, "subject_variant_index": int}.
    """
    subject_str, variant_idx = pick_subject_variant(
        template.subject_variants, lead_index, ab_enabled
    )

    unsubscribe_url = f"http://localhost:8000/unsubscribe/{unsubscribe_token}"

    context = {
        "name": lead.name or "there",
        "business": lead.business_name or "your business",
        "sender_name": sender.display_name,
        "unsubscribe_link": unsubscribe_url,
    }

    rendered_subject = render_jinja_string(subject_str, context)
    rendered_body = render_jinja_string(template.body, context)

    return {
        "subject": rendered_subject,
        "body": rendered_body,
        "subject_variant_index": variant_idx,
    }


def normalize_subject(subject: str) -> str:
    """
    Remove Re:, Fwd:, AW:, Re[2]: prefixes and normalize subject for matching.
    """
    if not subject:
        return ""
    # Remove common reply/forward prefixes
    pattern = r'^(re|fw|fwd|aw|antwort|sv|vs|rv|r)(\[\d+\])?:\s*'
    cleaned = re.sub(pattern, "", subject.strip(), flags=re.IGNORECASE)
    # Collapse whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip().lower()
    return cleaned
