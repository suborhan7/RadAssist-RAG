"""
Unit tests for ContextBuilder, per the frozen Phase 5 architecture
(development_log.md, "Phase 5 -- Context Builder: Architecture (FROZEN)",
"Unit testing strategy" section). Pure function tests, no collaborators to
fake. Hand-calculated expected values throughout, same convention as
test_label_voting_service.py.
"""
from __future__ import annotations

import random

import pytest

from app.domain.entities import RetrievalMetadata, RetrievedCase, VotedLabel
from app.services.context_builder import ContextBuilder


def _case(uid, sim, findings="", impression="", labels=(), cluster_id=-1):
    return RetrievedCase(
        source_uid=uid, similarity=sim, findings=findings, impression=impression,
        labels=labels, cluster_id=cluster_id,
    )


def _voted(label, weight, agreement):
    return VotedLabel(label=label, vote_weight=weight, agreement=agreement)


def test_global_sort_tie_break():
    # 0.9 sorts first; the two 0.5-similarity cases tie-break by source_uid
    # ascending ("a" < "z"), per the frozen determinism rule.
    cases = [_case("z", 0.5), _case("a", 0.5), _case("m", 0.9)]
    ctx = ContextBuilder().build(cases, [])
    assert [c.source_uid for c in ctx.retrieved_cases] == ["m", "a", "z"]


def test_near_dup_collapse_keeps_highest_similarity():
    # a1, a2 share cluster_id=10 -- a2 (0.95) must survive over a1 (0.9),
    # a3 is a different cluster and always survives.
    cases = [_case("a1", 0.9, cluster_id=10), _case("a2", 0.95, cluster_id=10), _case("a3", 0.7, cluster_id=20)]
    ctx = ContextBuilder().build(cases, [])
    assert [c.source_uid for c in ctx.retrieved_cases] == ["a2", "a3"]


def test_unset_cluster_id_singletons_not_collapsed():
    # cluster_id=-1 means "not part of any cluster" -- three such cases
    # must NOT be collapsed into one another.
    cases = [_case("u1", 0.5, cluster_id=-1), _case("u2", 0.6, cluster_id=-1), _case("u3", 0.55, cluster_id=-1)]
    ctx = ContextBuilder().build(cases, [])
    assert len(ctx.retrieved_cases) == 3
    assert {c.source_uid for c in ctx.retrieved_cases} == {"u1", "u2", "u3"}


def test_all_cases_share_one_cluster_collapses_to_single_survivor():
    cases = [_case("q1", 0.9, cluster_id=7), _case("q2", 0.95, cluster_id=7), _case("q3", 0.4, cluster_id=7)]
    ctx = ContextBuilder().build(cases, [])
    assert len(ctx.retrieved_cases) == 1
    assert ctx.retrieved_cases[0].source_uid == "q2"


def test_top_retrieved_case_first_post_dedup_and_none_on_empty():
    cases = [_case("low", 0.3), _case("high", 0.9)]
    ctx = ContextBuilder().build(cases, [])
    assert ctx.evidence_summary.top_retrieved_case.source_uid == "high"

    empty_ctx = ContextBuilder().build([], [])
    assert empty_ctx.evidence_summary.top_retrieved_case is None


def test_partition_for_label_is_generic_across_different_labels():
    cases = [
        _case("a", 0.9, labels=("Pneumonia",)),
        _case("b", 0.8, labels=("Normal",)),
        _case("c", 0.7, labels=("Normal",)),
    ]
    sup_pneu, contra_pneu = ContextBuilder()._partition_for_label(cases, "Pneumonia")
    sup_norm, contra_norm = ContextBuilder()._partition_for_label(cases, "Normal")

    assert [c.source_uid for c in sup_pneu] == ["a"]
    assert [c.source_uid for c in contra_pneu] == ["b", "c"]
    assert [c.source_uid for c in sup_norm] == ["b", "c"]
    assert [c.source_uid for c in contra_norm] == ["a"]
    assert sup_pneu != sup_norm  # proves the helper is not hardcoded to one label


def test_findings_and_impressions_dedup_by_text_across_different_clusters():
    # p1 and p2 are in DIFFERENT clusters (1 vs 2) but share identical
    # findings text -- dedup must key off text content, not cluster_id, so
    # p2's findings text is dropped even though it wasn't near-dup-collapsed.
    cases = [
        _case("p1", 0.9, findings="same findings text", impression="impr-1", cluster_id=1),
        _case("p2", 0.85, findings="same findings text", impression="impr-2", cluster_id=2),
        _case("p3", 0.7, findings="unique findings", impression="impr-2", cluster_id=3),
    ]
    ctx = ContextBuilder().build(cases, [])
    # all 3 survive dedup (distinct clusters) -- proves this is a text-level dedup
    assert len(ctx.retrieved_cases) == 3
    assert ctx.evidence_summary.findings_evidence == ("same findings text", "unique findings")
    assert ctx.evidence_summary.impressions_evidence == ("impr-1", "impr-2")


def test_retrieval_stats_hand_calculated():
    # x1, x2 share cluster_id=1 -> x2 collapsed (lower similarity); x3, x4 survive.
    # Post-dedup: x1(0.9, labels={A}), x3(0.6, labels={C}), x4(0.4, labels={A})
    # mean = (0.9+0.6+0.4)/3 = 0.63333...; min=0.4; max=0.9
    # unique_labels = {A, C} = 2; unique_clusters (excl. -1) = {1, 2} = 2
    cases = [
        _case("x1", 0.9, labels=("A",), cluster_id=1),
        _case("x2", 0.8, labels=("A", "B"), cluster_id=1),
        _case("x3", 0.6, labels=("C",), cluster_id=2),
        _case("x4", 0.4, labels=("A",), cluster_id=-1),
    ]
    ctx = ContextBuilder().build(cases, [])
    stats = ctx.evidence_summary.retrieval_stats

    assert stats.num_cases == 4
    assert stats.num_cases_after_dedup == 3
    assert stats.num_near_duplicates_collapsed == 1
    assert stats.mean_similarity == pytest.approx((0.9 + 0.6 + 0.4) / 3)
    assert stats.min_similarity == pytest.approx(0.4)
    assert stats.max_similarity == pytest.approx(0.9)
    assert stats.num_unique_labels == 2
    assert stats.num_clusters_represented == 2


def test_retrieval_metadata_passthrough_and_default_none():
    meta = RetrievalMetadata(
        collection_name="iu_cxr_biomedclip_v1_train",
        embedding_model="BiomedCLIP",
        embedding_version="v1",
        retrieved_at="2026-07-12T00:00:00Z",
    )
    cases = [_case("a", 0.9)]

    ctx_with_meta = ContextBuilder().build(cases, [], retrieval_metadata=meta)
    assert ctx_with_meta.evidence_summary.retrieval_metadata == meta

    ctx_without_meta = ContextBuilder().build(cases, [])
    assert ctx_without_meta.evidence_summary.retrieval_metadata is None


def test_build_label_evidence_is_single_tuple_for_top_voted_label():
    cases = [
        _case("a", 0.9, labels=("Effusion",)),
        _case("b", 0.8, labels=("Pneumonia",)),
    ]
    voted = [_voted("Effusion", 0.9, 0.5), _voted("Pneumonia", 0.8, 0.5)]
    ctx = ContextBuilder().build(cases, voted)

    assert len(ctx.evidence_summary.label_evidence) == 1
    partition = ctx.evidence_summary.label_evidence[0]
    assert partition.label == "Effusion"
    assert partition.vote_weight == pytest.approx(0.9)
    assert partition.agreement == pytest.approx(0.5)
    assert [c.source_uid for c in partition.supporting_cases] == ["a"]
    assert [c.source_uid for c in partition.contradictory_cases] == ["b"]


def test_determinism_shuffled_input_same_output():
    cases = [
        _case("a1", 0.9, findings="f-a", impression="i-a", labels=("Pneumonia",), cluster_id=0),
        _case("b1", 0.85, findings="f-a", impression="i-a", labels=("Pneumonia", "Effusion"), cluster_id=0),
        _case("c1", 0.7, findings="f-c", impression="i-c", labels=("Normal",), cluster_id=-1),
        _case("d1", 0.6, findings="f-d", impression="i-d", labels=("Normal",), cluster_id=-1),
        _case("e1", 0.95, findings="f-e", impression="i-e", labels=("Effusion",), cluster_id=1),
        _case("f1", 0.65, findings="f-e", impression="i-f", labels=("Effusion",), cluster_id=1),
    ]
    voted = [_voted("Effusion", 1.8, 0.5), _voted("Pneumonia", 0.9, 1 / 6)]

    baseline = ContextBuilder().build(cases, voted)

    shuffled = cases[:]
    random.shuffle(shuffled)
    result = ContextBuilder().build(shuffled, voted)

    assert result == baseline


def test_build_with_only_required_args_has_no_ellipsis_leak():
    cases = [_case("a", 0.9)]
    voted = [_voted("Normal", 0.9, 1.0)]

    ctx = ContextBuilder().build(cases, voted)  # omits all 3 optional params

    assert ctx.questionnaire_answers == {}
    assert isinstance(ctx.questionnaire_answers, dict)
    assert ctx.clinical_notes == ""
    assert ctx.evidence_summary.retrieval_metadata is None


def test_empty_input_returns_zeroed_evidence_summary_without_raising():
    ctx = ContextBuilder().build([], [])
    es = ctx.evidence_summary

    assert ctx.retrieved_cases == ()
    assert es.top_retrieved_case is None
    assert es.findings_evidence == ()
    assert es.impressions_evidence == ()
    assert es.label_evidence == ()
    assert es.retrieval_stats.num_cases == 0
    assert es.retrieval_stats.num_cases_after_dedup == 0
    assert es.retrieval_stats.num_near_duplicates_collapsed == 0
    assert es.retrieval_stats.mean_similarity == 0.0
    assert es.retrieval_stats.min_similarity == 0.0
    assert es.retrieval_stats.max_similarity == 0.0
    assert es.retrieval_stats.num_unique_labels == 0
    assert es.retrieval_stats.num_clusters_represented == 0
