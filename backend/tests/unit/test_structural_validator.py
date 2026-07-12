"""
Unit tests for StructuralValidator, per the frozen Phase 7 architecture
(development_log.md, "Phase 7 -- LLM Orchestrator: Architecture (FROZEN)",
"Unit testing strategy" section). Pure JSON/shape checks, no LLM involved.
"""
from __future__ import annotations

import json

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


def test_valid_complete_json_passes():
    is_valid, content, errors = StructuralValidator().validate(json.dumps(_FULL))
    assert is_valid is True
    assert errors == []
    assert content == ReportContent(**_FULL)


def test_missing_key_fails_with_specific_error():
    missing = dict(_FULL)
    del missing["impression"]
    is_valid, content, errors = StructuralValidator().validate(json.dumps(missing))
    assert is_valid is False
    assert content is None
    assert errors == ["missing required field: impression"]


def test_wrong_typed_value_fails_with_specific_error():
    wrong_type = dict(_FULL)
    wrong_type["findings"] = 123
    is_valid, content, errors = StructuralValidator().validate(json.dumps(wrong_type))
    assert is_valid is False
    assert content is None
    assert errors == ["field 'findings' must be a string, got int"]


def test_fenced_json_with_language_tag_strips_and_parses():
    fenced = "```json\n" + json.dumps(_FULL) + "\n```"
    is_valid, content, errors = StructuralValidator().validate(fenced)
    assert is_valid is True
    assert errors == []
    assert content == ReportContent(**_FULL)


def test_fenced_json_without_language_tag_strips_and_parses():
    fenced = "```\n" + json.dumps(_FULL) + "\n```"
    is_valid, content, errors = StructuralValidator().validate(fenced)
    assert is_valid is True
    assert errors == []
    assert content == ReportContent(**_FULL)


def test_fenced_but_still_invalid_json_fails_as_content_error_not_crash():
    fenced_invalid = "```json\nthis is not json at all, just prose\n```"
    is_valid, content, errors = StructuralValidator().validate(fenced_invalid)
    assert is_valid is False
    assert content is None
    assert len(errors) == 1
    assert "not valid JSON" in errors[0]


def test_unparseable_json_without_fence_fails_as_content_error_not_crash():
    is_valid, content, errors = StructuralValidator().validate("not json, no fence either")
    assert is_valid is False
    assert content is None
    assert len(errors) == 1
    assert "not valid JSON" in errors[0]


def test_empty_string_field_values_explicitly_pass():
    empty = {name: "" for name in _FULL}
    is_valid, content, errors = StructuralValidator().validate(json.dumps(empty))
    assert is_valid is True
    assert errors == []
    assert content is not None
    for name in _FULL:
        assert getattr(content, name) == ""
