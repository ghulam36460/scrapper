"""
Smart CSV parsing + column auto-detection + deduplication.
"""

import re
import json
import io
import os
from typing import Optional, Dict, List

import pandas as pd

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

EMAIL_ALIASES = {"email", "e-mail", "email address", "mail", "e_mail", "emailaddress", "email_address"}
NAME_ALIASES = {"name", "first name", "contact name", "person", "full name", "first_name", "fullname", "contact"}
BUSINESS_ALIASES = {"business", "company", "business name", "org", "organization", "company name",
                    "business_name", "companyname", "organisation"}
PHONE_ALIASES = {"phone", "mobile", "contact", "tel", "telephone", "phone number", "phonenumber", "mobile number"}


def normalize_email(email: str) -> str:
    """Lowercase + strip whitespace."""
    if not email:
        return ""
    return str(email).strip().lower()


def is_valid_email(email: str) -> bool:
    """Basic email format validation."""
    return bool(EMAIL_REGEX.match(email))


def auto_detect_columns(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    """
    Auto-detect which CSV column maps to email, name, business, phone.
    Case-insensitive matching against known aliases.
    """
    cols_lower = {c.lower().strip(): c for c in df.columns}
    mapping = {"email": None, "name": None, "business": None, "phone": None}

    for col_lower, col_original in cols_lower.items():
        if col_lower in EMAIL_ALIASES:
            mapping["email"] = col_original
        elif col_lower in NAME_ALIASES and mapping["name"] is None:
            mapping["name"] = col_original
        elif col_lower in BUSINESS_ALIASES and mapping["business"] is None:
            mapping["business"] = col_original
        elif col_lower in PHONE_ALIASES and mapping["phone"] is None:
            mapping["phone"] = col_original

    return mapping


def parse_csv_preview(content: bytes) -> Dict:
    """
    Parse CSV file and return column names + first 5 rows for preview.
    Also auto-detects columns.
    """
    try:
        df = pd.read_csv(io.BytesIO(content), dtype=str)
    except Exception as e:
        raise ValueError(f"Could not parse CSV file: {str(e)}")

    if df.empty:
        raise ValueError("CSV file is empty.")

    df = df.fillna("")
    columns = list(df.columns)
    preview_rows = df.head(5).to_dict(orient="records")
    auto_mapping = auto_detect_columns(df)
    total_rows = len(df)

    return {
        "columns": columns,
        "preview": preview_rows,
        "auto_mapping": auto_mapping,
        "total_rows": total_rows,
    }


def parse_csv_with_mapping(
    content: bytes,
    email_col: str,
    name_col: Optional[str] = None,
    business_col: Optional[str] = None,
    phone_col: Optional[str] = None,
    existing_emails: Optional[set] = None,
) -> Dict:
    """
    Parse CSV with explicit column mapping.
    Returns parsed leads with deduplication stats.
    """
    try:
        df = pd.read_csv(io.BytesIO(content), dtype=str)
    except Exception as e:
        raise ValueError(f"Could not parse CSV file: {str(e)}")

    df = df.fillna("")

    if email_col not in df.columns:
        raise ValueError(f"Email column '{email_col}' not found in CSV.")

    # Determine extra columns
    known_cols = {c for c in [email_col, name_col, business_col, phone_col] if c}
    extra_cols = [c for c in df.columns if c not in known_cols]

    leads = []
    seen_emails = set()
    valid = 0
    invalid = 0
    duplicates_in_file = 0
    already_sent_globally = 0

    for _, row in df.iterrows():
        raw_email = str(row.get(email_col, ""))
        norm_email = normalize_email(raw_email)

        if not norm_email or not is_valid_email(norm_email):
            invalid += 1
            continue

        if norm_email in seen_emails:
            duplicates_in_file += 1
            continue
        seen_emails.add(norm_email)

        globally_sent = False
        if existing_emails and norm_email in existing_emails:
            already_sent_globally += 1
            globally_sent = True

        # Collect extra data
        extra_data = {}
        for ec in extra_cols:
            val = str(row.get(ec, "")).strip()
            if val:
                extra_data[ec] = val

        leads.append({
            "email": norm_email,
            "name": str(row.get(name_col, "")).strip() if name_col else "",
            "business_name": str(row.get(business_col, "")).strip() if business_col else "",
            "phone": str(row.get(phone_col, "")).strip() if phone_col else "",
            "extra_data": json.dumps(extra_data) if extra_data else None,
            "global_email_hash": norm_email,
            "globally_sent": globally_sent,
        })
        valid += 1

    return {
        "total": len(df),
        "valid": valid,
        "invalid": invalid,
        "duplicates_in_file": duplicates_in_file,
        "already_sent_globally": already_sent_globally,
        "leads": leads,
    }
