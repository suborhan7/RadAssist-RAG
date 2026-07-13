"""
Unit tests for DeterministicComparator, per the frozen Phase 11 architecture
(development_log.md, "Phase 11 -- Longitudinal Patient History &
Comparison: Architecture (FROZEN)"). Pure, no I/O -- hand-built
ReportContent pairs, real taxonomy classes from the actual
label_mapping.yaml (same convention as test_response_validator.py's use
of real class names like "Pneumonia"/"Cardiomegaly", rather than an
injected fake taxonomy).
"""
from __future__ import annotations

from app.domain.entities import ReportContent
from app.services.deterministic_comparator import DeterministicComparator


def _content(findings: str, impression: str) -> ReportContent:
    return ReportContent(
        examination="Chest X-ray", clinical_history="Unknown", technique="PA view",
        findings=findings, impression=impression, recommendation="", disclaimer="",
    )


def test_resolved_persistent_and_new_all_populated():
    # previous: Pneumonia + Cardiomegaly. current: Cardiomegaly + Pleural Effusion.
    # -> resolved = Pneumonia (gone), persistent = Cardiomegaly (stayed),
    #    new = Pleural Effusion (newly appeared).
    previous = _content(
        findings="Findings consistent with pneumonia. Cardiomegaly is noted.",
        impression="Pneumonia with cardiomegaly.",
    )
    current = _content(
        findings="Cardiomegaly persists. New pleural effusion is seen.",
        impression="Cardiomegaly with pleural effusion.",
    )

    facts = DeterministicComparator().compare(
        previous, current, previous_date="2026-01-01", current_date="2026-02-01",
        previous_report_id="prev-id", current_report_id="curr-id",
    )

    assert facts.previous_report_id == "prev-id"
    assert facts.current_report_id == "curr-id"
    assert facts.resolved_findings == ("Pneumonia",)
    assert facts.persistent_findings == ("Cardiomegaly",)
    assert facts.new_findings == ("Pleural Effusion",)
    assert facts.days_between_studies == 31


def test_zero_findings_changed_all_persistent():
    previous = _content(
        findings="Findings consistent with pneumonia.",
        impression="Pneumonia.",
    )
    current = _content(
        findings="Findings consistent with pneumonia, unchanged from prior.",
        impression="Pneumonia, stable.",
    )

    facts = DeterministicComparator().compare(
        previous, current, previous_date="2026-01-01", current_date="2026-01-15",
        previous_report_id="prev-id", current_report_id="curr-id",
    )

    assert facts.persistent_findings == ("Pneumonia",)
    assert facts.resolved_findings == ()
    assert facts.new_findings == ()


def test_completely_disjoint_findings():
    previous = _content(
        findings="Findings consistent with pneumonia.",
        impression="Pneumonia.",
    )
    current = _content(
        findings="Cardiomegaly is noted with pleural effusion.",
        impression="Cardiomegaly with pleural effusion.",
    )

    facts = DeterministicComparator().compare(
        previous, current, previous_date="2026-01-01", current_date="2026-01-10",
        previous_report_id="prev-id", current_report_id="curr-id",
    )

    assert facts.persistent_findings == ()
    assert set(facts.resolved_findings) == {"Pneumonia"}
    assert set(facts.new_findings) == {"Cardiomegaly", "Pleural Effusion"}


def test_word_boundary_safe_normal_not_matched_inside_abnormality():
    """Same 'normal' inside 'abnormality' scenario as Phase 8's original
    bug -- a naive substring implementation would incorrectly report
    'Normal' as mentioned in a report that only says 'no focal
    abnormality', which would misclassify a still-ongoing finding as
    resolved/persistent Normal-ness that was never actually stated."""
    previous = _content(
        findings="The lungs are clear with no focal abnormality.",
        impression="No acute cardiopulmonary process.",
    )
    current = _content(
        findings="The lungs are clear with no focal abnormality.",
        impression="No acute cardiopulmonary process.",
    )

    facts = DeterministicComparator().compare(
        previous, current, previous_date="2026-01-01", current_date="2026-01-10",
        previous_report_id="prev-id", current_report_id="curr-id",
    )

    assert "Normal" not in facts.persistent_findings
    assert "Normal" not in facts.resolved_findings
    assert "Normal" not in facts.new_findings


def test_days_between_studies_correct_for_known_date_pair():
    previous = _content(findings="Pneumonia.", impression="Pneumonia.")
    current = _content(findings="Pneumonia.", impression="Pneumonia.")

    facts = DeterministicComparator().compare(
        previous, current, previous_date="2026-01-01", current_date="2026-04-01",
        previous_report_id="prev-id", current_report_id="curr-id",
    )

    assert facts.days_between_studies == 90
