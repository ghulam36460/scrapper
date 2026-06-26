"""Non-destructive noise-reduction and data-cleaning pipeline.

This module implements the project's ``noise reduction`` and
``data-validation`` SKILLs. Its guiding principle is:

    **Clean and score records, never silently drop them.**

The earlier inline cleaning logic discarded any record whose name failed a
strict check, which caused the result set to collapse to zero. Instead, these
helpers normalize every field and attach a *confidence score* (0.0 - 1.0)
plus a list of human-readable quality issues. Downstream code can then decide
what to do with low-confidence records (export, flag for review, etc.) rather
than losing the data outright.
"""

from __future__ import annotations

import html
import logging
import re
import unicodedata
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Text fields that should be whitespace/entity/unicode normalized.
_TEXT_FIELDS = ("name", "address", "city", "category")

# Leading boilerplate often prepended to page titles used as a business name.
_NAME_PREFIX_RE = re.compile(r"^(home|welcome|about)\s*[\|\-–—:]\s*", re.IGNORECASE)
# A trailing " | Some Tagline" / " - Best in town" segment after the name.
_NAME_TAGLINE_RE = re.compile(r"\s*[\|\-–—]\s+.*$")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MULTISPACE_RE = re.compile(r"\s+")

# Scoring weights. Start at 1.0 and subtract for each detected issue.
_MISSING_NAME_PENALTY = 0.40
_SUSPECT_NAME_PENALTY = 0.15
_MISSING_CONTACT_PENALTY = 0.35  # no phone, whatsapp, or email at all
_MISSING_LOCATION_PENALTY = 0.10
_ENCODING_FIX_PENALTY = 0.05
_MIN_CONFIDENCE = 0.0


@dataclass
class CleaningResult:
    """Outcome of cleaning a single record's fields.

    Attributes:
        fields: Cleaned field values keyed by field name.
        confidence: Quality score in the range 0.0 - 1.0.
        issues: Human-readable descriptions of every quality problem found.
    """

    fields: dict[str, str] = field(default_factory=dict)
    confidence: float = 1.0
    issues: list[str] = field(default_factory=list)


def normalize_text(value: str | None) -> str:
    """Strip HTML, decode entities, normalize unicode and whitespace.

    Returns an empty string for falsy input. This never raises.
    """
    if not value:
        return ""
    text = html.unescape(str(value))
    text = _HTML_TAG_RE.sub(" ", text)
    text = unicodedata.normalize("NFKC", text)
    text = _MULTISPACE_RE.sub(" ", text)
    return text.strip()


def repair_mojibake(value: str) -> tuple[str, bool]:
    """Fix UTF-8 text that was mis-decoded as Latin-1 (mojibake).

    Returns the (possibly repaired) text and a flag indicating whether a
    repair was applied. Safe on already-correct text.
    """
    if not value:
        return value, False
    # Only attempt a repair when typical mojibake markers are present, to
    # avoid corrupting valid text.
    if not any(marker in value for marker in ("Ã", "â€", "Â", " Â")):
        return value, False
    try:
        repaired = value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value, False
    return (repaired, True) if repaired != value else (value, False)


def clean_business_name(raw: str | None) -> str:
    """Normalize a business name without ever discarding it.

    Unlike the previous ``clean_name`` (which returned "" for short/long
    names and caused records to be dropped), this only strips boilerplate
    and trims length. The caller scores quality separately.
    """
    text = normalize_text(raw)
    if not text:
        return ""
    text = _NAME_PREFIX_RE.sub("", text)
    text = _NAME_TAGLINE_RE.sub("", text).strip()
    # Cap excessively long names but keep the meaningful head.
    if len(text) > 120:
        text = text[:120].rsplit(" ", 1)[0].strip()
    return text


def _name_looks_suspect(name: str) -> bool:
    """Heuristic: does this name look like noise rather than a real name?"""
    if not name:
        return True
    if len(name) < 2:
        return True
    # Mostly digits/symbols, or generic page words.
    alpha = sum(ch.isalpha() for ch in name)
    if alpha < 2:
        return True
    if name.lower() in {"home", "welcome", "untitled", "index", "page not found"}:
        return True
    return False


def clean_record_fields(
    fields: dict[str, str | None],
    *,
    has_contact: bool,
) -> CleaningResult:
    """Clean a record's text fields and compute a confidence score.

    Args:
        fields: Mapping of field name to raw value. Recognized text fields
            (name, address, city, category) are normalized; others pass
            through untouched after a light trim.
        has_contact: Whether the record has at least one of phone / whatsapp
            / email. Used only for scoring; the record is never dropped.

    Returns:
        A :class:`CleaningResult` with cleaned fields, a confidence score and
        a list of detected issues.
    """
    result = CleaningResult()
    confidence = 1.0

    for key, raw in fields.items():
        if key == "name":
            cleaned = clean_business_name(raw)
        elif key in _TEXT_FIELDS:
            cleaned = normalize_text(raw)
        else:
            cleaned = (str(raw).strip() if raw else "")
        cleaned, repaired = repair_mojibake(cleaned)
        if repaired:
            confidence -= _ENCODING_FIX_PENALTY
            result.issues.append(f"encoding repaired in '{key}'")
        result.fields[key] = cleaned

    name = result.fields.get("name", "")
    if not name:
        confidence -= _MISSING_NAME_PENALTY
        result.issues.append("missing business name")
    elif _name_looks_suspect(name):
        confidence -= _SUSPECT_NAME_PENALTY
        result.issues.append("business name looks low quality")

    if not has_contact:
        confidence -= _MISSING_CONTACT_PENALTY
        result.issues.append("no phone, whatsapp or email found")

    if not result.fields.get("city") and not result.fields.get("address"):
        confidence -= _MISSING_LOCATION_PENALTY
        result.issues.append("no city or address found")

    result.confidence = round(max(_MIN_CONFIDENCE, min(1.0, confidence)), 3)
    if result.issues:
        logger.debug(
            "Record cleaned with confidence %.3f and %d issue(s): %s",
            result.confidence,
            len(result.issues),
            result.issues,
        )
    return result


def format_csv_cell(value: object) -> str:
    """Render any record value as a clean, single-line CSV cell.

    - Lists become ``", "``-joined strings.
    - Dicts become ``"key: value"`` pairs joined by ``"; "``.
    - ``None`` becomes an empty string.
    - All values are stripped of HTML, newlines and repeated whitespace so
      the resulting CSV is tidy and predictable.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        return "; ".join(f"{k}: {format_csv_cell(v)}" for k, v in value.items() if v not in (None, "", [], {}))
    if isinstance(value, (list, tuple, set)):
        return ", ".join(format_csv_cell(item) for item in value if item not in (None, ""))
    text = normalize_text(str(value))
    return text
