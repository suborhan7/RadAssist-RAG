"""
app/services/context_builder.py
====================================================================
Implements IContextBuilder. Deterministic, session-agnostic organizer of
RetrievalService + LabelVotingService output into ClinicalContext, per the
frozen Phase 5 architecture (development_log.md, "Phase 5 -- Context
Builder: Architecture (FROZEN)"). Organizes and partitions evidence only --
no diagnosis, no report generation, no LLM calls, no textual synthesis.

Determinism is the load-bearing property here: every output collection's
order is derived from one explicit initial sort by (-similarity,
source_uid), never from dict/set iteration order.
"""
from __future__ import annotations

from app.domain.entities import (
    ClinicalContext,
    EvidenceSummary,
    LabelEvidencePartition,
    RetrievalMetadata,
    RetrievalStats,
    RetrievedCase,
    VotedLabel,
)


class ContextBuilder:
    """Satisfies domain.interfaces.IContextBuilder."""

    def build(
        self,
        retrieved: list[RetrievedCase],
        voted_labels: list[VotedLabel],
        questionnaire_answers: dict[str, str] | None = None,
        clinical_notes: str = "",
        retrieval_metadata: RetrievalMetadata | None = None,
    ) -> ClinicalContext:
        questionnaire_answers = questionnaire_answers or {}

        sorted_cases = sorted(retrieved, key=lambda c: (-c.similarity, c.source_uid))
        deduped_cases = self._collapse_near_duplicates(sorted_cases)

        top_retrieved_case = deduped_cases[0] if deduped_cases else None
        findings_evidence, impressions_evidence = self._build_text_evidence(deduped_cases)
        retrieval_stats = self._compute_stats(retrieved, deduped_cases)

        label_evidence: tuple[LabelEvidencePartition, ...] = ()
        if voted_labels:
            top_label = voted_labels[0]
            supporting, contradictory = self._partition_for_label(deduped_cases, top_label.label)
            label_evidence = (
                LabelEvidencePartition(
                    label=top_label.label,
                    vote_weight=top_label.vote_weight,
                    agreement=top_label.agreement,
                    supporting_cases=supporting,
                    contradictory_cases=contradictory,
                ),
            )

        evidence_summary = EvidenceSummary(
            top_retrieved_case=top_retrieved_case,
            findings_evidence=findings_evidence,
            impressions_evidence=impressions_evidence,
            retrieval_stats=retrieval_stats,
            retrieval_metadata=retrieval_metadata,
            label_evidence=label_evidence,
        )

        return ClinicalContext(
            retrieved_cases=tuple(deduped_cases),
            voted_labels=tuple(voted_labels),
            questionnaire_answers=questionnaire_answers,
            clinical_notes=clinical_notes,
            evidence_summary=evidence_summary,
        )

    @staticmethod
    def _collapse_near_duplicates(sorted_cases: list[RetrievedCase]) -> list[RetrievedCase]:
        """sorted_cases is already ordered by (-similarity, source_uid), so
        within any real cluster_id group the first occurrence encountered
        here is the highest-similarity one -- collapsing to first-seen-per-
        cluster is a direct consequence of that sort, not an independent
        re-sort. cluster_id == -1 means "not part of any near-dup cluster"
        (per RetrievedCase's own field comment), so those cases must NOT be
        collapsed against each other -- each is kept as its own singleton.
        """
        seen_clusters: set[int] = set()
        result: list[RetrievedCase] = []
        for case in sorted_cases:
            if case.cluster_id == -1:
                result.append(case)
                continue
            if case.cluster_id in seen_clusters:
                continue
            seen_clusters.add(case.cluster_id)
            result.append(case)
        return result

    @staticmethod
    def _partition_for_label(
        cases: list[RetrievedCase], label: str
    ) -> tuple[tuple[RetrievedCase, ...], tuple[RetrievedCase, ...]]:
        """Generic on purpose: partitions supporting/contradictory cases for
        ANY label passed in, via exact set-intersection on case.labels. Phase
        5 calls this exactly once, for the top voted label (see call site in
        build()) -- a future Differential Diagnosis phase can call this same
        helper in a loop over multiple labels with zero changes here."""
        supporting = tuple(c for c in cases if label in c.labels)
        contradictory = tuple(c for c in cases if label not in c.labels)
        return supporting, contradictory

    @staticmethod
    def _build_text_evidence(
        cases: list[RetrievedCase],
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        seen_findings: set[str] = set()
        seen_impressions: set[str] = set()
        findings: list[str] = []
        impressions: list[str] = []
        for case in cases:
            if case.findings not in seen_findings:
                seen_findings.add(case.findings)
                findings.append(case.findings)
            if case.impression not in seen_impressions:
                seen_impressions.add(case.impression)
                impressions.append(case.impression)
        return tuple(findings), tuple(impressions)

    @staticmethod
    def _compute_stats(
        original: list[RetrievedCase], deduped: list[RetrievedCase]
    ) -> RetrievalStats:
        num_cases = len(original)
        num_after = len(deduped)
        similarities = [c.similarity for c in deduped]
        unique_labels = {label for c in deduped for label in c.labels}
        unique_clusters = {c.cluster_id for c in deduped if c.cluster_id != -1}
        return RetrievalStats(
            num_cases=num_cases,
            num_cases_after_dedup=num_after,
            num_near_duplicates_collapsed=num_cases - num_after,
            mean_similarity=sum(similarities) / num_after if num_after else 0.0,
            min_similarity=min(similarities) if similarities else 0.0,
            max_similarity=max(similarities) if similarities else 0.0,
            num_unique_labels=len(unique_labels),
            num_clusters_represented=len(unique_clusters),
        )
