"""Unit tests for the non-destructive noise-reduction pipeline.

These tests follow the testing-standards SKILL: they cover the happy path
plus edge cases (empty fields, mojibake, HTML entities, listing/dict CSV
cells) and assert the key guarantee that records are scored, never dropped.
"""

from __future__ import annotations

from asagus.layers.noise_reduction import (
    clean_business_name,
    clean_record_fields,
    format_csv_cell,
    normalize_text,
    repair_mojibake,
)


def test_normalize_text_decodes_entities_and_collapses_whitespace() -> None:
    assert normalize_text("  Caf&eacute;\n\n   Bar  ") == "Café Bar"


def test_normalize_text_strips_html_tags() -> None:
    assert normalize_text("<b>Joe</b> &amp; Sons") == "Joe & Sons"


def test_normalize_text_handles_none() -> None:
    assert normalize_text(None) == ""


def test_clean_business_name_strips_boilerplate_and_tagline() -> None:
    assert clean_business_name("Home | Best Pizza in Town") == "Best Pizza in Town"
    assert clean_business_name("Acme Foods - Cheapest deals") == "Acme Foods"


def test_clean_business_name_caps_length_without_dropping() -> None:
    long_name = "Word " * 60
    result = clean_business_name(long_name)
    assert result  # never returns empty for valid text
    assert len(result) <= 120


def test_repair_mojibake_fixes_double_encoded_text() -> None:
    broken = "Caf\u00c3\u00a9"  # "Café" mis-decoded as latin-1
    repaired, changed = repair_mojibake(broken)
    assert changed is True
    assert repaired == "Café"


def test_repair_mojibake_leaves_clean_text_untouched() -> None:
    repaired, changed = repair_mojibake("Café Bar")
    assert changed is False
    assert repaired == "Café Bar"


def test_empty_record_is_kept_and_scored_low() -> None:
    result = clean_record_fields(
        {"name": "", "address": "", "city": "", "category": ""},
        has_contact=False,
    )
    # The critical guarantee: the record is NOT dropped, just scored low.
    assert result.fields["name"] == ""
    assert result.confidence < 0.5
    assert "missing business name" in result.issues
    assert "no phone, whatsapp or email found" in result.issues


def test_complete_record_gets_full_confidence() -> None:
    result = clean_record_fields(
        {
            "name": "Joe's Diner",
            "address": "12 Main St",
            "city": "Lahore",
            "category": "Restaurant",
        },
        has_contact=True,
    )
    assert result.confidence == 1.0
    assert result.issues == []
    assert result.fields["name"] == "Joe's Diner"


def test_missing_contact_only_reduces_confidence() -> None:
    result = clean_record_fields(
        {"name": "Cafe X", "address": "Road 1", "city": "Dubai", "category": ""},
        has_contact=False,
    )
    assert 0.0 < result.confidence < 1.0
    assert "no phone, whatsapp or email found" in result.issues


def test_format_csv_cell_variants() -> None:
    assert format_csv_cell(None) == ""
    assert format_csv_cell(True) == "yes"
    assert format_csv_cell(False) == "no"
    assert format_csv_cell(42) == "42"
    assert format_csv_cell(["a", "", None, "b"]) == "a, b"
    assert format_csv_cell({"x": 1, "y": None, "z": "q"}) == "x: 1; z: q"


def test_format_csv_cell_flattens_newlines() -> None:
    assert format_csv_cell("line1\nline2\t  line3") == "line1 line2 line3"
