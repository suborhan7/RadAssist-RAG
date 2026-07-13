"""
Unit tests for ReportFormatter, per the frozen Phase 8 architecture
(development_log.md, "Phase 8 -- Response Validator + Hospital Report
Formatter: Architecture (FROZEN)", "Unit testing strategy" section).
Pure function, no collaborators to fake.
"""
from __future__ import annotations

import pytest

from app.domain.entities import ReportContent
from app.services.report_formatter import ReportFormatter

_CONTENT = ReportContent(
    examination="Chest X-ray", clinical_history="Cough", technique="PA view",
    findings="Clear lungs", impression="No acute process",
    recommendation="Clinical correlation", disclaimer="AI-generated draft",
)


def test_correct_headers_for_english():
    result = ReportFormatter().format(_CONTENT, "en", "2026-07-12")

    assert result.section_headers == {
        "examination": "Examination",
        "clinical_history": "Clinical History",
        "technique": "Technique",
        "findings": "Findings",
        "impression": "Impression",
        "recommendation": "Recommendation",
        "disclaimer": "Disclaimer",
    }


def test_correct_headers_for_bengali():
    result = ReportFormatter().format(_CONTENT, "bn", "2026-07-12")

    assert set(result.section_headers.keys()) == {
        "examination", "clinical_history", "technique", "findings",
        "impression", "recommendation", "disclaimer",
    }
    # provisional placeholder terms -- not asserting exact clinical
    # correctness, only that a real (non-empty) label exists per field
    for header in result.section_headers.values():
        assert isinstance(header, str)
        assert header.strip() != ""


def test_report_date_passed_through_unchanged():
    result = ReportFormatter().format(_CONTENT, "en", "2026-01-01")
    assert result.report_date == "2026-01-01"

    result2 = ReportFormatter().format(_CONTENT, "en", "some-caller-supplied-string")
    assert result2.report_date == "some-caller-supplied-string"


def test_determinism_same_inputs_produce_identical_output():
    first = ReportFormatter().format(_CONTENT, "en", "2026-07-12")
    second = ReportFormatter().format(_CONTENT, "en", "2026-07-12")
    assert first == second


def test_unsupported_language_raises_value_error():
    with pytest.raises(ValueError, match="unsupported language"):
        ReportFormatter().format(_CONTENT, "fr", "2026-07-12")
