"""
app/domain/entities.py
====================================================================
Pure domain entities. No FastAPI, no SQLAlchemy, no BiomedCLIP/torch imports
here -- this layer must be importable and testable with zero infrastructure.
Infrastructure adapters (Postgres repositories, ChromaDB client, etc.) map
to/from these types; they never leak their own types back into this layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional


class ReportStatus(str, Enum):
    AI_DRAFT = "ai_draft"
    UNDER_REVIEW = "under_review"
    DOCTOR_EDITED = "doctor_edited"
    FINAL = "final"


class Language(str, Enum):
    ENGLISH = "en"
    BENGALI = "bn"


@dataclass(frozen=True)
class Patient:
    """Redefined in place for Phase 11 (Longitudinal Patient History &
    Comparison), replacing the original Phase 0 stub (id, external_ref,
    age, gender) rather than renaming this new arrival -- a deliberate
    exception to the Phase 8 Report/ReportRecord precedent, not a reversal
    of it. That precedent renamed the NEW class because the OLD Report
    entity was actively load-bearing (real ReportContent flowed through it
    across Phases 7-10). This old Patient shape was confirmed dead first
    (grepped for `Patient(` constructor calls and `external_ref` field
    references -- zero real hits anywhere), never wired to any
    infrastructure, sitting unused since the original speculative domain
    scaffolding. A second, independent reason to replace rather than
    rename: the old shape stored `age` directly, which is exactly what
    this same phase's frozen Decision 3 rejects (age-at-visit computed on
    read from date_of_birth, never stored, to avoid staleness across
    visits) -- keeping the old Patient around under a different name would
    leave a second, contradictory representation of "patient" in the
    codebase, one that directly violates a decision just frozen in this
    phase. That is worse than a naming collision."""
    id: str
    patient_code: str        # "PAT-000001", auto-generated, never manually assigned
    name: str
    date_of_birth: str        # ISO date; age-at-visit computed on read, never stored
    gender: str


@dataclass(frozen=True)
class Doctor:
    """Phase 13: authentication + doctor ownership. Grepped clean first --
    no prior `Doctor` name existed anywhere in this codebase.

    Patients remain shared/institutional (no `doctor_id` on `Patient` --
    unchanged since Phase 11); ownership instead attaches to the WORK a
    doctor performs (retrieval_sessions/comparisons/explanations each gain
    a `doctor_id` at the persistence layer, not here -- this entity's
    shape carries no ownership fields of its own, since a doctor doesn't
    own themselves)."""
    id: str
    email: str
    password_hash: str
    full_name: str
    created_at: str


@dataclass(frozen=True)
class StudyImage:
    id: str
    file_path: str
    projection: str             # "Frontal" | "Lateral"


@dataclass(frozen=True)
class Study:
    id: str
    patient_id: str
    study_date: date
    images: tuple[StudyImage, ...] = field(default_factory=tuple)

    def frontal_image(self) -> Optional[StudyImage]:
        return next((img for img in self.images if img.projection == "Frontal"), None)


@dataclass(frozen=True)
class RetrievedCase:
    """One neighbor returned by RetrievalService, with full provenance."""
    source_uid: str
    similarity: float
    findings: str
    impression: str
    labels: tuple[str, ...] = field(default_factory=tuple)
    image_path: str = ""        # masked path (Phase 3 Correction-2), matches what was embedded
    cluster_id: int = -1        # near-dup cluster diagnostic; -1 = unset


@dataclass(frozen=True)
class VotedLabel:
    """Output of LabelVotingService: similarity-weighted label vote."""
    label: str
    vote_weight: float          # sum of similarity weights supporting this label
    agreement: float            # fraction of top-K neighbors agreeing -> confidence signal


@dataclass(frozen=True)
class RetrievalStats:
    num_cases: int
    num_cases_after_dedup: int
    num_near_duplicates_collapsed: int
    mean_similarity: float
    min_similarity: float
    max_similarity: float
    num_unique_labels: int
    num_clusters_represented: int


@dataclass(frozen=True)
class RetrievalMetadata:
    collection_name: str
    embedding_model: str
    embedding_version: str
    retrieved_at: str   # ISO 8601, caller-supplied


@dataclass(frozen=True)
class LabelEvidencePartition:
    label: str
    vote_weight: float
    agreement: float
    supporting_cases: tuple[RetrievedCase, ...]
    contradictory_cases: tuple[RetrievedCase, ...]


@dataclass(frozen=True)
class EvidenceSummary:
    top_retrieved_case: Optional[RetrievedCase]
    findings_evidence: tuple[str, ...]
    impressions_evidence: tuple[str, ...]
    retrieval_stats: RetrievalStats
    retrieval_metadata: Optional[RetrievalMetadata]
    label_evidence: tuple[LabelEvidencePartition, ...]


@dataclass(frozen=True)
class ClinicalContext:
    """ContextBuilderService output: aggregated evidence handed to PromptBuilderService."""
    retrieved_cases: tuple[RetrievedCase, ...]
    voted_labels: tuple[VotedLabel, ...]
    questionnaire_answers: dict[str, str] = field(default_factory=dict)
    clinical_notes: str = ""
    evidence_summary: Optional[EvidenceSummary] = None


@dataclass(frozen=True)
class SemanticValidationResult:
    """ResponseValidator output: semantic/clinical warnings, never a pass/fail
    gate -- surfaced to a human reviewer, never triggers automated retry."""
    missing_findings: bool
    missing_impression: bool
    unsupported_terms: tuple[str, ...]
    top_label_unreflected: bool
    warnings: tuple[str, ...]
    is_clean: bool


@dataclass(frozen=True)
class FormattedReport:
    """ReportFormatter output: a structured object only, never rendered PDF/HTML."""
    content: ReportContent
    language: str
    report_date: str
    section_headers: dict[str, str]


@dataclass(frozen=True)
class GenerationMetadata:
    """Reproducibility metadata persisted with every generated report."""
    llm_model: str
    llm_temperature: float
    embedding_model: str
    embedding_version: str
    collection_name: str


@dataclass(frozen=True)
class QuestionnaireQuestion:
    key: str
    text: str
    input_type: str   # "text" | "yes_no" | "select"


@dataclass(frozen=True)
class Questionnaire:
    session_id: str
    based_on_label: str
    questions: tuple[QuestionnaireQuestion, ...]


@dataclass(frozen=True)
class ExplanationRecord:
    id: str
    report_id: str
    question: str
    answer: str
    created_at: str


@dataclass(frozen=True)
class ComparisonFacts:
    previous_report_id: str
    current_report_id: str
    resolved_findings: tuple[str, ...]      # present before, absent now
    persistent_findings: tuple[str, ...]    # present in both
    new_findings: tuple[str, ...]           # absent before, present now
    days_between_studies: int


@dataclass(frozen=True)
class Comparison:
    id: str
    patient_id: str
    previous_report_id: str
    current_report_id: str
    facts: ComparisonFacts
    narrative: str
    created_at: str


@dataclass
class ReportContent:
    """Mutable: a report has an AI-generated version and a doctor-edited version."""
    examination: str = ""
    clinical_history: str = ""
    technique: str = ""
    findings: str = ""
    impression: str = ""
    recommendation: str = ""
    disclaimer: str = ""


@dataclass
class Report:
    id: str
    study_id: str
    language: Language
    status: ReportStatus
    ai_content: ReportContent
    final_content: ReportContent
    evidence: tuple[RetrievedCase, ...] = field(default_factory=tuple)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
