"""
Unit tests for StructuralValidator, per the frozen Phase 7 architecture
(development_log.md, "Phase 7 -- LLM Orchestrator: Architecture (FROZEN)",
"Unit testing strategy" section). Pure delimiter-marker/shape checks, no
LLM involved.

Delimiter-marker format, not JSON -- changed after Phase 20's real
generation-quality evaluation traced all 17 real content-validation
failures in that run to the same JSON-escaping bug at the disclaimer
field (development_log.md, "Finding: All 17 Generation Failures Share
One Root Cause").
"""
from __future__ import annotations

from app.domain.entities import ReportContent
from app.services.structural_validator import StructuralValidator

_FULL = {
    "examination": "Chest X-ray, PA view",
    "clinical_history": "Cough and fever",
    "technique": "Single frontal radiograph",
    "findings": "Clear lung fields",
    "impression": "No acute cardiopulmonary process",
    "recommendation": "Clinical correlation",
    "disclaimer": "AI-generated draft",
}

_FIELD_ORDER = (
    "examination", "clinical_history", "technique", "findings",
    "impression", "recommendation", "disclaimer",
)


def _marker_text(values: dict[str, str], order: tuple[str, ...] = _FIELD_ORDER) -> str:
    return "\n".join(f"###{name.upper()}###\n{values[name]}" for name in order)


def test_valid_complete_markers_passes():
    is_valid, content, errors = StructuralValidator().validate(_marker_text(_FULL))
    assert is_valid is True
    assert errors == []
    assert content == ReportContent(**_FULL)


def test_missing_marker_fails_with_specific_error():
    order_without_impression = tuple(n for n in _FIELD_ORDER if n != "impression")
    text = _marker_text(_FULL, order_without_impression)
    is_valid, content, errors = StructuralValidator().validate(text)
    assert is_valid is False
    assert content is None
    assert errors == ["missing required field marker: ###IMPRESSION###"]


def test_out_of_order_fields_fail_with_specific_error():
    swapped_order = ("examination", "clinical_history", "technique",
                      "impression", "findings", "recommendation", "disclaimer")
    text = _marker_text(_FULL, swapped_order)
    is_valid, content, errors = StructuralValidator().validate(text)
    assert is_valid is False
    assert content is None
    assert len(errors) == 1
    assert "out of order" in errors[0]
    assert "['examination', 'clinical_history', 'technique', 'impression', 'findings'" in errors[0]


def test_malformed_delimiter_wrong_case_fails_with_specific_error():
    text = _marker_text(_FULL).replace("###FINDINGS###", "###Findings###")
    is_valid, content, errors = StructuralValidator().validate(text)
    assert is_valid is False
    assert content is None
    # 'Findings' also fails to match the missing-marker check for FINDINGS,
    # so both a malformed-marker error and a missing-marker error are real,
    # independent facts about this response and both should be reported.
    assert "malformed field marker: '###Findings###' (expected exactly '###FINDINGS###')" in errors
    assert "missing required field marker: ###FINDINGS###" in errors


def test_malformed_delimiter_wrong_hash_count_fails_with_specific_error():
    text = _marker_text(_FULL).replace("###DISCLAIMER###", "##DISCLAIMER##")
    is_valid, content, errors = StructuralValidator().validate(text)
    assert is_valid is False
    assert content is None
    assert "malformed field marker: '##DISCLAIMER##' (expected exactly '###DISCLAIMER###')" in errors
    assert "missing required field marker: ###DISCLAIMER###" in errors


def test_unrecognized_marker_name_fails_with_specific_error():
    text = _marker_text(_FULL) + "\n###SUMMARY###\nExtra invented field."
    is_valid, content, errors = StructuralValidator().validate(text)
    assert is_valid is False
    assert content is None
    assert "unrecognized field marker: '###SUMMARY###'" in errors


def test_duplicate_marker_fails_with_specific_error():
    text = _marker_text(_FULL) + "\n###FINDINGS###\nA second, duplicate findings block."
    is_valid, content, errors = StructuralValidator().validate(text)
    assert is_valid is False
    assert content is None
    assert "field marker for 'findings' appeared more than once" in errors


def test_no_markers_at_all_fails_as_content_error_not_crash():
    is_valid, content, errors = StructuralValidator().validate("just plain prose, no markers at all")
    assert is_valid is False
    assert content is None
    assert len(errors) == 1
    assert "no recognized field markers" in errors[0]


def test_fenced_markers_with_language_tag_strips_and_parses():
    fenced = "```text\n" + _marker_text(_FULL) + "\n```"
    is_valid, content, errors = StructuralValidator().validate(fenced)
    assert is_valid is True
    assert errors == []
    assert content == ReportContent(**_FULL)


def test_fenced_markers_without_language_tag_strips_and_parses():
    fenced = "```\n" + _marker_text(_FULL) + "\n```"
    is_valid, content, errors = StructuralValidator().validate(fenced)
    assert is_valid is True
    assert errors == []
    assert content == ReportContent(**_FULL)


def test_empty_string_field_values_explicitly_pass():
    empty = {name: "" for name in _FULL}
    is_valid, content, errors = StructuralValidator().validate(_marker_text(empty))
    assert is_valid is True
    assert errors == []
    assert content is not None
    for name in _FULL:
        assert getattr(content, name) == ""


def test_field_content_containing_quotes_and_apostrophes_passes_unescaped():
    """The real, motivating case: disclaimer text citing a label name in
    quotes (e.g. "the top-voted label 'Normal'") is exactly the pattern
    that broke json.loads() under the old JSON format -- confirmed real
    in Phase 20's evaluation data. The marker format has no string-escaping
    boundary for this to break, proven here with a real quote-containing
    value, not just a plain-text fixture."""
    values = dict(_FULL)
    values["disclaimer"] = (
        'Clinical uncertainty: the top-voted label "Normal" is low (0.40), '
        "and the radiologist's review is still required."
    )
    is_valid, content, errors = StructuralValidator().validate(_marker_text(values))
    assert is_valid is True
    assert errors == []
    assert content.disclaimer == values["disclaimer"]
