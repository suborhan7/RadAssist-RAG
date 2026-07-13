"""
Unit tests for ResponseValidator, per the frozen Phase 8 architecture
(development_log.md, "Phase 8 -- Response Validator + Hospital Report
Formatter: Architecture (FROZEN)", "Unit testing strategy" section). Real,
hand-built ReportContent/EvidenceSummary/VotedLabel fixtures, same
convention as Phase 5/6's unit tests.
"""
from __future__ import annotations

import pytest

from app.domain.entities import (
    EvidenceSummary,
    LabelEvidencePartition,
    ReportContent,
    RetrievalStats,
    RetrievedCase,
    VotedLabel,
)
from app.services.response_validator import TOP_LABEL_AGREEMENT_THRESHOLD, ResponseValidator


def _case(uid, labels=(), sim=0.9):
    return RetrievedCase(source_uid=uid, similarity=sim, findings="", impression="", labels=labels)


def _stats() -> RetrievalStats:
    return RetrievalStats(
        num_cases=2, num_cases_after_dedup=2, num_near_duplicates_collapsed=0,
        mean_similarity=0.9, min_similarity=0.85, max_similarity=0.95,
        num_unique_labels=2, num_clusters_represented=0,
    )


def _evidence_summary(top_label: str, supporting_cases, contradictory_cases) -> EvidenceSummary:
    partition = LabelEvidencePartition(
        label=top_label, vote_weight=1.5, agreement=0.67,
        supporting_cases=tuple(supporting_cases), contradictory_cases=tuple(contradictory_cases),
    )
    return EvidenceSummary(
        top_retrieved_case=supporting_cases[0] if supporting_cases else None,
        findings_evidence=(), impressions_evidence=(),
        retrieval_stats=_stats(), retrieval_metadata=None,
        label_evidence=(partition,),
    )


def _content(findings="", impression="") -> ReportContent:
    return ReportContent(
        examination="Chest X-ray", clinical_history="Unknown", technique="PA view",
        findings=findings, impression=impression, recommendation="", disclaimer="",
    )


def test_clean_well_supported_report_is_clean_with_no_false_positives():
    evidence = _evidence_summary(
        "Pneumonia",
        supporting_cases=[_case("a", labels=("Pneumonia",))],
        contradictory_cases=[_case("b", labels=("Normal",))],
    )
    voted = [VotedLabel(label="Pneumonia", vote_weight=1.5, agreement=0.67)]
    content = _content(
        findings="Findings consistent with pneumonia in the right lower lobe.",
        impression="Pneumonia.",
    )

    result = ResponseValidator().validate_semantic(content, evidence, voted)

    assert result.missing_findings is False
    assert result.missing_impression is False
    assert result.unsupported_terms == ()
    assert result.top_label_unreflected is False
    assert result.warnings == ()
    assert result.is_clean is True


def test_empty_findings_flagged():
    evidence = _evidence_summary("Pneumonia", [_case("a", labels=("Pneumonia",))], [])
    voted = [VotedLabel(label="Pneumonia", vote_weight=1.0, agreement=1.0)]
    content = _content(findings="   ", impression="Pneumonia.")

    result = ResponseValidator().validate_semantic(content, evidence, voted)

    assert result.missing_findings is True
    assert "Findings section is empty" in result.warnings
    assert result.is_clean is False


def test_empty_impression_flagged():
    evidence = _evidence_summary("Pneumonia", [_case("a", labels=("Pneumonia",))], [])
    voted = [VotedLabel(label="Pneumonia", vote_weight=1.0, agreement=1.0)]
    content = _content(findings="Findings consistent with pneumonia.", impression="")

    result = ResponseValidator().validate_semantic(content, evidence, voted)

    assert result.missing_impression is True
    assert "Impression section is empty" in result.warnings
    assert result.is_clean is False


def test_taxonomy_term_absent_from_evidence_flagged_as_unsupported():
    # evidence carries only Pneumonia (supporting) and Normal (contradictory) --
    # Cardiomegaly appears nowhere in the retrieved evidence at all.
    evidence = _evidence_summary(
        "Pneumonia",
        supporting_cases=[_case("a", labels=("Pneumonia",))],
        contradictory_cases=[_case("b", labels=("Normal",))],
    )
    voted = [VotedLabel(label="Pneumonia", vote_weight=1.0, agreement=1.0)]
    content = _content(
        findings="Findings consistent with pneumonia. Cardiomegaly is also noted.",
        impression="Pneumonia with cardiomegaly.",
    )

    result = ResponseValidator().validate_semantic(content, evidence, voted)

    assert result.unsupported_terms == ("Cardiomegaly",)
    assert any("Cardiomegaly" in w and "not supported by retrieved evidence" in w for w in result.warnings)
    assert result.is_clean is False


def test_high_agreement_top_label_absent_from_text_flagged():
    evidence = _evidence_summary("Pneumonia", [_case("a", labels=("Pneumonia",))], [])
    voted = [VotedLabel(label="Pneumonia", vote_weight=1.0, agreement=0.8)]
    content = _content(
        findings="The lungs are clear with no focal abnormality.",
        impression="No acute cardiopulmonary process.",
    )

    result = ResponseValidator().validate_semantic(content, evidence, voted)

    assert result.top_label_unreflected is True
    assert any(
        "Pneumonia" in w and "agreement 0.80" in w and "not reflected" in w for w in result.warnings
    )
    assert result.is_clean is False


def test_low_agreement_top_label_absent_from_text_not_flagged():
    """Proves the agreement threshold actually gates the check both ways --
    a low-agreement top label being absent from the text is not itself
    treated as a problem (the model may reasonably be uncertain)."""
    evidence = _evidence_summary("Pneumonia", [_case("a", labels=("Pneumonia",))], [])
    below_threshold = TOP_LABEL_AGREEMENT_THRESHOLD - 0.1
    voted = [VotedLabel(label="Pneumonia", vote_weight=1.0, agreement=below_threshold)]
    content = _content(
        findings="The lungs are clear with no focal abnormality.",
        impression="No acute cardiopulmonary process.",
    )

    result = ResponseValidator().validate_semantic(content, evidence, voted)

    assert result.top_label_unreflected is False
    assert result.is_clean is True


def test_zero_false_positives_with_varied_phrasing_and_secondary_evidence_backed_finding():
    """A report mentioning a SECOND real finding (Atelectasis) that lives in
    the partition's contradictory_cases bucket (not supporting_cases) must
    NOT be flagged as unsupported -- proves the evidence-label union covers
    both buckets, not just the ones carrying the top voted label."""
    evidence = _evidence_summary(
        "Pneumonia",
        supporting_cases=[_case("a", labels=("Pneumonia",))],
        contradictory_cases=[_case("b", labels=("Atelectasis",))],
    )
    voted = [VotedLabel(label="Pneumonia", vote_weight=1.5, agreement=0.67)]
    content = _content(
        findings="Findings consistent with PNEUMONIA and mild atelectasis at the lung bases.",
        impression="Pneumonia with atelectasis.",
    )

    result = ResponseValidator().validate_semantic(content, evidence, voted)

    assert result.unsupported_terms == ()
    assert result.top_label_unreflected is False  # case-insensitive match on "PNEUMONIA"
    assert result.is_clean is True
