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
    Report,
    ReportContent,
    RetrievedCase,
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
        questionnaire_answers: dict[str, str],
        clinical_notes: str,
    ) -> ClinicalContext: ...


@runtime_checkable
class IPromptBuilder(Protocol):
    def build_generation_prompt(self, context: ClinicalContext, language: str) -> str: ...
    def build_explanation_prompt(self, report: Report, question: str) -> str: ...
    def build_translation_prompt(self, content: ReportContent, target_language: str) -> str: ...


@runtime_checkable
class ILLMClient(Protocol):
    """Wraps Ollama. Infrastructure: app/infrastructure/ollama_client.py"""

    def complete(self, prompt: str) -> str: ...


@runtime_checkable
class IStudyRepository(Protocol):
    def get(self, study_id: str) -> Study | None: ...
    def save(self, study: Study) -> None: ...


@runtime_checkable
class IReportRepository(Protocol):
    def get(self, report_id: str) -> Report | None: ...
    def save(self, report: Report) -> None: ...
    def list_by_study(self, study_id: str) -> list[Report]: ...
