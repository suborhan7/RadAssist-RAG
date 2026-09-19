"""
Phase 21 §2.2 -- the evidence-mode branching in ContextBuilder.

These tests exist to hold the experiment's central claim: that the three arms
run the identical production code path and differ ONLY in the evidence carried
into ClinicalContext. That claim is what makes a between-arm difference
attributable to evidence rather than to anything else, so it is asserted
directly rather than trusted.

§2.1's naming discipline is also tested, in the only way a test can express it:
LABELS_ONLY must still carry the vote. A LABELS_ONLY context that lost its
voted labels would be an EMPTY context wearing the wrong name.
"""
from __future__ import annotations

import pytest

from app.domain.entities import EvidenceMode, RetrievalMetadata, RetrievedCase, VotedLabel
from app.services.context_builder import ContextBuilder

CASES = [
    RetrievedCase(source_uid="2491", similarity=0.97, findings="Diffuse interstitial markings.",
                  impression="Interstitial lung disease.", labels=("Lung Opacity",), cluster_id=11),
    RetrievedCase(source_uid="316", similarity=0.95, findings="Clear lungs.",
                  impression="Normal.", labels=("Normal",), cluster_id=12),
    RetrievedCase(source_uid="282", similarity=0.93, findings="Mild bibasilar prominence.",
                  impression="Mild interstitial changes.", labels=("Lung Opacity",), cluster_id=13),
]
VOTED = [
    VotedLabel(label="Lung Opacity", vote_weight=1.90, agreement=0.67),
    VotedLabel(label="Normal", vote_weight=0.95, agreement=0.33),
]
ANSWERS = {"duration": "3 days"}
NOTES = "Referred for cough."
META = RetrievalMetadata("iu_cxr_biomedclip_v1_train", "biomedclip", "v1", "2026-08-20T00:00:00Z")


def build(mode: EvidenceMode):
    return ContextBuilder(evidence_mode=mode).build(
        list(CASES), list(VOTED), questionnaire_answers=dict(ANSWERS),
        clinical_notes=NOTES, retrieval_metadata=META,
    )


def test_full_carries_case_text_and_labels():
    ctx = build(EvidenceMode.FULL)
    assert ctx.evidence_summary.findings_evidence  # prose present
    assert ctx.evidence_summary.impressions_evidence
    assert ctx.evidence_summary.top_retrieved_case is not None
    assert ctx.evidence_summary.label_evidence
    assert ctx.retrieved_cases and ctx.voted_labels


def test_labels_only_withholds_every_carrier_of_case_prose():
    """Retrieval-as-classifier: the vote survives, the text does not.

    Each assertion names a distinct carrier of case prose. Checking only
    findings_evidence would pass while impression text still reached the LLM
    through top_retrieved_case.
    """
    ctx = build(EvidenceMode.LABELS_ONLY)
    assert ctx.evidence_summary.findings_evidence == ()
    assert ctx.evidence_summary.impressions_evidence == ()
    assert ctx.evidence_summary.top_retrieved_case is None
    assert ctx.retrieved_cases == ()
    # ...but the vote is intact. This is the line that distinguishes B from A.
    assert ctx.voted_labels == tuple(VOTED)
    assert ctx.evidence_summary.label_evidence
    assert ctx.evidence_summary.label_evidence[0].label == "Lung Opacity"


def test_empty_withholds_labels_as_well():
    ctx = build(EvidenceMode.EMPTY)
    assert ctx.evidence_summary.findings_evidence == ()
    assert ctx.evidence_summary.impressions_evidence == ()
    assert ctx.evidence_summary.top_retrieved_case is None
    assert ctx.retrieved_cases == ()
    assert ctx.voted_labels == ()
    assert ctx.evidence_summary.label_evidence == ()


@pytest.mark.parametrize("mode", list(EvidenceMode))
def test_non_evidence_inputs_are_identical_across_all_three_arms(mode):
    """The arms must differ in evidence and in nothing else.

    Questionnaire answers, clinical notes and retrieval metadata are carried
    through untouched in every mode; if an arm altered them, a between-arm
    difference could not be attributed to evidence.
    """
    ctx = build(mode)
    assert ctx.questionnaire_answers == ANSWERS
    assert ctx.clinical_notes == NOTES
    assert ctx.evidence_summary.retrieval_metadata == META


@pytest.mark.parametrize("mode", list(EvidenceMode))
def test_retrieval_stats_are_identical_across_arms(mode):
    """Retrieval itself runs identically in every arm (§2.1). The stats are
    computed from the raw retrieved list, so they must not vary -- that is the
    evidence that suppression happens after retrieval, not instead of it."""
    stats = build(mode).evidence_summary.retrieval_stats
    full_stats = build(EvidenceMode.FULL).evidence_summary.retrieval_stats
    assert stats == full_stats
    assert stats.num_cases == len(CASES)


def test_default_is_full_so_production_behaviour_is_unchanged():
    """Every existing caller constructs ContextBuilder() with no arguments."""
    assert ContextBuilder().build(list(CASES), list(VOTED)).retrieved_cases != ()


def test_no_case_prose_survives_into_a_suppressed_context():
    """Belt-and-braces: search the whole context for any retrieved case's exact
    findings/impression string. A future field added to ClinicalContext that
    happens to carry prose would slip past the field-by-field assertions above,
    but not past this one."""
    for mode in (EvidenceMode.LABELS_ONLY, EvidenceMode.EMPTY):
        blob = repr(build(mode))
        for case in CASES:
            assert case.findings not in blob, f"{mode}: leaked findings of {case.source_uid}"
            assert case.impression not in blob, f"{mode}: leaked impression of {case.source_uid}"
