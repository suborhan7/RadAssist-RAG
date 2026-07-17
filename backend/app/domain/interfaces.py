"""
app/domain/interfaces.py
====================================================================
Protocol-based interfaces. Services depend on these, never on concrete
infrastructure classes. This is what makes the encoder/LLM/vector-store
swappable and every service unit-testable behind a mock.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.entities import (
    ClinicalContext,
    ComparisonFacts,
    Doctor,
    EvidenceSummary,
    FormattedReport,
    Patient,
    QuestionnaireQuestion,
    Report,
    ReportContent,
    RetrievalMetadata,
    RetrievedCase,
    SemanticValidationResult,
    Study,
    VotedLabel,
)


@runtime_checkable
class IEmbedder(Protocol):
    """Wraps the frozen encoder (BiomedCLIP). Infrastructure: app/infrastructure/biomedclip.py"""

    def embed_image(self, image_path: str) -> list[float]: ...
    def embed_text(self, text: str) -> list[float]: ...


@runtime_checkable
class IVectorStore(Protocol):
    """Wraps ChromaDB. Infrastructure: app/infrastructure/chroma_store.py"""

    def query(self, embedding: list[float], top_k: int) -> list[RetrievedCase]: ...
    def upsert(self, uid: str, embedding: list[float], metadata: dict) -> None: ...
    def get_by_ids(self, uids: list[str]) -> list[RetrievedCase]:
        """Phase 8: reconstructs full RetrievedCase content (findings/impression/
        labels) for a set of study_uids -- retrieved_evidence (Phase 4) only
        persists study_uid/rank/similarity, not the full case content."""
        ...

    def count(self) -> int:
        """Phase 16: real index size for Settings/System (design_specification.md
        §8.16). A thin passthrough to the underlying chromadb collection's
        own .count() -- not a new capability this system computes, just one
        this interface didn't expose yet."""
        ...


@runtime_checkable
class IImageValidator(Protocol):
    """Phase 4: validates an uploaded image before it enters the retrieval
    pipeline. Infrastructure: app/services/image_validator.py"""

    def validate(self, image_path: str) -> None:
        """Raises ValueError (or subclass) on invalid input. Returns None on success."""
        ...


@runtime_checkable
class ISimilaritySearchPolicy(Protocol):
    """Phase 4: top-K selection + similarity thresholding over raw retrieval
    results. Infrastructure: app/services/similarity_search.py"""

    def select(
        self, raw_results: list[RetrievedCase], top_k: int, min_similarity: float
    ) -> list[RetrievedCase]: ...


@runtime_checkable
class ILabelVoter(Protocol):
    """LabelVotingService: similarity-weighted vote over retrieved cases."""

    def vote(self, retrieved: list[RetrievedCase]) -> list[VotedLabel]: ...


@runtime_checkable
class IContextBuilder(Protocol):
    def build(
        self,
        retrieved: list[RetrievedCase],
        voted_labels: list[VotedLabel],
        questionnaire_answers: dict[str, str] = ...,
        clinical_notes: str = ...,
        retrieval_metadata: RetrievalMetadata | None = ...,
    ) -> ClinicalContext: ...


@runtime_checkable
class IPromptBuilder(Protocol):
    def build_generation_prompt(self, context: ClinicalContext, language: str) -> str: ...
    def build_retry_prompt(
        self,
        context: ClinicalContext,
        language: str,
        previous_response: str,
        validation_errors: list[str],
    ) -> str: ...
    def build_explanation_prompt(
        self, report: Report, question: str, evidence_summary: EvidenceSummary
    ) -> str: ...   # implemented Phase 10; evidence_summary added since it wasn't an accessible
    # concept at this stub's original Phase 6 freeze
    def build_translation_prompt(self, content: ReportContent, target_language: str) -> str: ...  # unimplemented
    def build_comparison_prompt(
        self, facts: ComparisonFacts, previous: ReportContent, current: ReportContent
    ) -> str:
        """Phase 11: narrates deterministic ComparisonFacts (already computed,
        zero LLM involvement) into readable language. The LLM converts facts
        to prose; it does not perform clinical reasoning of its own."""
        ...


@runtime_checkable
class ILLMClient(Protocol):
    """Wraps Ollama. Infrastructure: app/infrastructure/ollama_client.py"""

    def complete(self, prompt: str) -> str: ...


@runtime_checkable
class IStructuralValidator(Protocol):
    """Phase 7: validates that a raw LLM response is well-formed JSON matching
    ReportContent's shape. Infrastructure: app/services/structural_validator.py"""

    def validate(self, raw_response: str) -> tuple[bool, ReportContent | None, list[str]]:
        """Returns (is_valid, parsed_content_or_None, validation_errors)."""
        ...


@runtime_checkable
class ILLMOrchestrator(Protocol):
    """Phase 7: orchestrates PromptBuilder + ILLMClient + IStructuralValidator
    with two independent retry budgets. Infrastructure: app/services/llm_orchestrator.py"""

    def generate_draft(self, context: ClinicalContext, language: str) -> ReportContent: ...

    def answer_question(self, prompt: str) -> str:
        """Phase 10: free-text explainability chat. Reuses the same
        transport-retry protection as generate_draft() (a transport failure
        is equally real here), but has NO content-retry/structural-
        validation loop -- free-text answers have no schema to validate
        against."""
        ...


@runtime_checkable
class IResponseValidator(Protocol):
    """Phase 8: semantic/clinical validation of an already structurally-valid
    ReportContent. Produces warnings for human review, never a pass/fail gate
    that triggers automated retry. Infrastructure: app/services/response_validator.py"""

    def validate_semantic(
        self,
        content: ReportContent,
        evidence_summary: EvidenceSummary,
        voted_labels: list[VotedLabel],
    ) -> SemanticValidationResult: ...


@runtime_checkable
class IReportFormatter(Protocol):
    """Phase 8: formats a validated ReportContent into a structured object
    (never rendered PDF/HTML). Infrastructure: app/services/report_formatter.py"""

    def format(self, content: ReportContent, language: str, report_date: str) -> FormattedReport: ...


@runtime_checkable
class IQuestionnaireProvider(Protocol):
    """Phase 9: static, label-keyed question templates -- no LLM call.
    Infrastructure: app/services/questionnaire_templates.py"""

    def get_questions_for_label(self, label: str) -> tuple[QuestionnaireQuestion, ...]: ...


@runtime_checkable
class IPatientRepository(Protocol):
    """Phase 11: patient registration, exact-match search, chronological
    history. Infrastructure: app/services/patient_service.py.

    find_by_id (Phase 12, additive) exists for a real gap found while
    building the frontend's Patient Profile page: neither find_by_code/
    find_by_name_and_dob (both require info the page doesn't have from
    just a patient_id in the URL) nor get_history (returns only report
    fields, no patient details) can answer "get this patient's own
    details given only their id" -- needed for the Profile page to be
    correct on a direct URL load, refresh, or bookmark, not only when
    navigated to in-app with patient details already in hand.

    get_history's return type is list[Report] (the frozen domain entity),
    NOT list[ReportRecord] -- the frozen spec's prose named ReportRecord,
    but that's the Phase 8 SQLAlchemy ORM model (app/models/report.py),
    which imports SQLAlchemy; domain/interfaces.py must stay
    framework-free (see entities.py's own docstring: "No FastAPI, no
    SQLAlchemy... imports here"), and IReportRepository/IStudyRepository
    immediately above already establish Report (not ReportRecord) as this
    layer's convention. Same category of spec-text slip as Phase 5's
    study_uid/source_uid mismatch -- corrected to the domain entity, not
    silently imported across the domain/infrastructure boundary."""

    def create(self, name: str, date_of_birth: str, gender: str) -> Patient: ...
    def find_by_code(self, patient_code: str) -> Patient | None: ...
    def find_by_name_and_dob(self, name: str, date_of_birth: str) -> list[Patient]: ...
    def find_by_id(self, patient_id: str) -> Patient | None: ...
    def get_history(self, patient_id: str) -> list[Report]: ...  # chronological


@runtime_checkable
class IDeterministicComparator(Protocol):
    """Phase 11: pure, no LLM, no DB -- diffs two reports' taxonomy-class
    presence into resolved/persistent/new findings. Infrastructure:
    app/services/deterministic_comparator.py

    previous_report_id/current_report_id are plain string pass-through
    params, not a DB lookup -- ComparisonFacts (domain/entities.py) carries
    both report IDs, and nothing else in a pure, DB-free function can
    supply them; the caller (ComparisonService, Step 8) already has both
    IDs on hand from whatever it fetched, so this is free plumbing, not
    new orchestration logic. Corrects an initial Step 1 spec gap where
    compare()'s params couldn't actually populate ComparisonFacts'
    required id fields."""

    def compare(
        self,
        previous: ReportContent,
        current: ReportContent,
        previous_date: str,
        current_date: str,
        previous_report_id: str,
        current_report_id: str,
    ) -> ComparisonFacts: ...


@runtime_checkable
class IStudyRepository(Protocol):
    def get(self, study_id: str) -> Study | None: ...
    def save(self, study: Study) -> None: ...


@runtime_checkable
class IReportRepository(Protocol):
    def get(self, report_id: str) -> Report | None: ...
    def save(self, report: Report) -> None: ...
    def list_by_study(self, study_id: str) -> list[Report]: ...


@runtime_checkable
class IDoctorRepository(Protocol):
    """Phase 13: authentication + doctor ownership.
    Infrastructure: app/services/doctor_service.py (matches
    IPatientRepository's precedent -- the repository-Protocol
    implementation lives in app/services/ as a plain `xxx_service.py`,
    not in a separate infrastructure/repositories/ layer; this codebase
    has never had that extra layer, and introducing it for exactly one
    new entity would fragment an otherwise consistent convention for no
    stated benefit)."""

    def create(self, email: str, password_hash: str, full_name: str) -> Doctor: ...
    def find_by_email(self, email: str) -> Doctor | None: ...
    def find_by_id(self, doctor_id: str) -> Doctor | None: ...

    def update_profile(self, doctor_id: str, **fields: object) -> Doctor:
        """Phase 16: partial self-update (full_name, bmdc_number, the five
        default_* workspace preferences). Only keys actually present in
        **fields are changed -- omitted fields are left untouched, not
        reset to None."""
        ...


@runtime_checkable
class IPasswordHasher(Protocol):
    """Phase 13. Infrastructure: app/infrastructure/password_hasher.py
    (flat, matching every other infrastructure adapter in this
    package -- no auth/ subdirectory precedent exists anywhere in
    app/infrastructure/)."""

    def hash(self, plain: str) -> str: ...
    def verify(self, plain: str, hashed: str) -> bool: ...


@runtime_checkable
class ITokenService(Protocol):
    """Phase 13. Infrastructure: app/infrastructure/jwt_handler.py."""

    def issue(self, doctor_id: str) -> str: ...
    def verify(self, token: str) -> str: ...  # returns doctor_id or raises
