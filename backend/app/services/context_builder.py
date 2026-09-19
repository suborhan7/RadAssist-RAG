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

from dataclasses import replace

from app.domain.entities import (
    ClinicalContext,
    EvidenceMode,
    EvidenceSummary,
    LabelEvidencePartition,
    RetrievalMetadata,
    RetrievalStats,
    RetrievedCase,
    VotedLabel,
)


class ContextBuilder:
    """Satisfies domain.interfaces.IContextBuilder.

    Phase 21 §2.2: the evidence mode is injected, not read from `settings`
    here. Step 0 established that this class had NO constructor at all and
    received nothing by injection, so the injection is added rather than
    assumed -- and the injected thing is the MODE, not the whole Settings
    object, matching ModalityGateService's established pattern of taking the
    individual values it needs. That keeps this class testable without a
    Settings instance and keeps "no parameter value in the source" intact.

    The default is FULL, so every existing caller that constructs
    `ContextBuilder()` with no arguments keeps production behaviour
    byte-identically.
    """

    def __init__(self, evidence_mode: EvidenceMode = EvidenceMode.FULL) -> None:
        self._evidence_mode = evidence_mode

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

        # --- Phase 21 ablation (§2.2) -------------------------------------
        # The arm is applied HERE and nowhere else. Retrieval, embedding,
        # dedup, voting and the stats above all run identically in every arm;
        # what changes is only which of their products survive into the
        # context the LLM is given. Suppression is expressed as two booleans
        # derived from one enum so the three arms cannot drift into four
        # states, and so a reader can see at a glance that B differs from C
        # by exactly one thing.
        #
        # §2.1: LABELS_ONLY is retrieval-as-classifier. Retrieval still ran;
        # its free text is withheld and its vote is kept.
        include_case_text = self._evidence_mode is EvidenceMode.FULL
        include_labels = self._evidence_mode is not EvidenceMode.EMPTY

        # top_retrieved_case carries findings/impression prose, so it is
        # withheld with the rest of the case text -- not kept "because it is
        # only one case".
        top_retrieved_case = (deduped_cases[0] if deduped_cases else None) if include_case_text else None
        findings_evidence, impressions_evidence = (
            self._build_text_evidence(deduped_cases) if include_case_text else ((), ())
        )
        # Stats are counts and similarities, never prose, and PromptBuilder
        # does not render them into the prompt at all. They are retained in
        # every arm so the context still records what retrieval actually did,
        # which is what makes the failure-rate parity check (§6.4) and the
        # latency work (§7) interpretable per arm.
        retrieval_stats = self._compute_stats(retrieved, deduped_cases)

        label_evidence: tuple[LabelEvidencePartition, ...] = ()
        if voted_labels and include_labels:
            top_label = voted_labels[0]
            supporting, contradictory = self._partition_for_label(deduped_cases, top_label.label)
            if not include_case_text:
                # The partition holds whole RetrievedCase objects, and those
                # carry findings/impression prose. PromptBuilder currently
                # renders only len() of each bucket, so today the prose does
                # not reach the LLM -- but "today" is not a guarantee, and a
                # LABELS_ONLY context that still CONTAINS the case text is not
                # an honest record of what the arm withheld. Found by the
                # leak test in test_context_builder_evidence_mode.py, not by
                # reading the code.
                #
                # The counts are the label evidence and must survive, so the
                # cases are kept and stripped rather than dropped: len() is
                # unchanged, uid/similarity/labels remain (a uid is not case
                # text, and the labels ARE the vote this arm is built on),
                # and only the prose is removed.
                supporting = tuple(replace(c, findings="", impression="") for c in supporting)
                contradictory = tuple(replace(c, findings="", impression="") for c in contradictory)
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
            # Withheld in A and B for the same reason as the text above: this
            # tuple carries each case's findings and impression prose, and a
            # context that still contained it would not be an honest record of
            # what the arm made available.
            retrieved_cases=tuple(deduped_cases) if include_case_text else (),
            voted_labels=tuple(voted_labels) if include_labels else (),
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
