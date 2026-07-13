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
    EvidenceSummary,
    FormattedReport,
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
    def build_explanation_prompt(self, report: Report, question: str) -> str: ...   # unimplemented, Phase 10
    def build_translation_prompt(self, content: ReportContent, target_language: str) -> str: ...  # unimplemented


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
class IStudyRepository(Protocol):
    def get(self, study_id: str) -> Study | None: ...
    def save(self, study: Study) -> None: ...


@runtime_checkable
class IReportRepository(Protocol):
    def get(self, report_id: str) -> Report | None: ...
    def save(self, report: Report) -> None: ...
    def list_by_study(self, study_id: str) -> list[Report]: ...
