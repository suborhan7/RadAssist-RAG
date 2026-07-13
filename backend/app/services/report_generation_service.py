"""
app/services/report_generation_service.py
====================================================================
Orchestrates the full Phase 8 chain, per the frozen sequence diagram:
fetch session evidence -> reconstruct cases -> vote -> build context ->
generate -> semantically validate -> format -> persist. Pure sequencing
over its injected collaborators -- no business logic, no clinical
judgment, no prompt/report content decisions of its own -- same discipline
as RetrievalService (Phase 4).

Exception propagation policy (deliberate, stated explicitly): LLMTransportError
and LLMGenerationValidationError from llm_orchestrator.generate_draft() are
NOT caught here -- they propagate unchanged to the caller (Step 7's API
route). This mirrors Phase 4's precedent exactly: RetrievalService lets
ValueError propagate up to app/api/retrieval.py, the one place that knows
how to translate a domain exception into an HTTP status code. Catching and
re-wrapping here would duplicate that translation responsibility in two
places instead of one.

Reproducibility-metadata gap, flagged rather than silently worked around:
RetrievalSession (Phase 4's frozen schema) does NOT persist collection_name/
embedding_model/embedding_version per-session -- only Settings holds these
(as the current config, not necessarily what was true at the original
retrieval time if config has changed since). Sourced from Settings here,
consistent with how /retrieve's own response and Phase 7's integration test
both already source the identical values -- not a new precedent, but worth
naming as a real limitation: if the collection/model config changes between
a session's original retrieval and a later report-generation call, the
persisted reproducibility metadata reflects the LATER config, not
necessarily what actually produced that session's retrieved cases.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.entities import (
    FormattedReport,
    GenerationMetadata,
    ReportStatus,
    RetrievalMetadata,
    SemanticValidationResult,
)
from app.domain.interfaces import (
    IContextBuilder,
    ILabelVoter,
    ILLMOrchestrator,
    IReportFormatter,
    IResponseValidator,
    IVectorStore,
)
from app.models.report import ReportRecord
from app.services.session_reconstruction import reconstruct_session_evidence


class ReportGenerationService:
    def __init__(
        self,
        db: Session,
        vector_store: IVectorStore,
        label_voting_service: ILabelVoter,
        context_builder: IContextBuilder,
        llm_orchestrator: ILLMOrchestrator,
        response_validator: IResponseValidator,
        report_formatter: IReportFormatter,
    ) -> None:
        self._db = db
        self._vector_store = vector_store
        self._label_voting_service = label_voting_service
        self._context_builder = context_builder
        self._llm_orchestrator = llm_orchestrator
        self._response_validator = response_validator
        self._report_formatter = report_formatter

    def generate(
        self,
        session_id: str,
        language: str,
        questionnaire_answers: dict[str, str] | None = None,
        clinical_notes: str = "",
    ) -> tuple[uuid.UUID, FormattedReport, SemanticValidationResult, GenerationMetadata]:
        # Phase 9 additive extension: questionnaire_answers/clinical_notes
        # default to None/"" (same null-handling convention as
        # PromptBuilder's own build() defaults from Phase 6 --
        # None-then-convert for the mutable dict, never a mutable literal
        # as the actual default argument value). Omitting both entirely
        # must be byte-identical to Phase 8's existing behavior -- see
        # test_no_questionnaire_data_produces_byte_identical_behavior_to_phase_8.
        questionnaire_answers = questionnaire_answers or {}

        # Shared with QuestionnaireService (Phase 9) -- see
        # session_reconstruction.py's own docstring for why this is
        # extracted rather than duplicated.
        retrieval_session, retrieved_cases, voted_labels = reconstruct_session_evidence(
            self._db, self._vector_store, self._label_voting_service, session_id
        )

        retrieval_metadata = RetrievalMetadata(
            collection_name=settings.CHROMA_COLLECTION_NAME,
            embedding_model=settings.CHROMA_EMBEDDING_MODEL,
            embedding_version=settings.CHROMA_EMBEDDING_VERSION,
            retrieved_at=retrieval_session.created_at.isoformat() if retrieval_session.created_at else "",
        )
        context = self._context_builder.build(
            retrieved_cases,
            voted_labels,
            questionnaire_answers=questionnaire_answers,
            clinical_notes=clinical_notes,
            retrieval_metadata=retrieval_metadata,
        )

        # LLMTransportError / LLMGenerationValidationError intentionally
        # NOT caught here -- see module docstring's propagation policy.
        content = self._llm_orchestrator.generate_draft(context, language)

        validation_result = self._response_validator.validate_semantic(
            content, context.evidence_summary, voted_labels
        )

        # report_date generated HERE, not inside ReportFormatter (which must
        # stay a pure, deterministic function -- Phase 8 Decision 4).
        report_date = datetime.now(timezone.utc).date().isoformat()

        formatted_report = self._report_formatter.format(content, language, report_date)

        report_record = ReportRecord(
            session_id=retrieval_session.id,
            language=language,
            status=ReportStatus.AI_DRAFT,
            ai_content=asdict(content),
            validation_warnings=list(validation_result.warnings),
            report_date=report_date,
            llm_model=settings.OLLAMA_MODEL,
            llm_temperature=settings.LLM_TEMPERATURE,
            embedding_model=retrieval_metadata.embedding_model,
            embedding_version=retrieval_metadata.embedding_version,
            collection_name=retrieval_metadata.collection_name,
        )
        self._db.add(report_record)
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        # Populated from the exact same values just persisted onto
        # report_record (not re-queried from the DB) -- one computation,
        # reused, rather than a second, potentially-inconsistent read.
        generation_metadata = GenerationMetadata(
            llm_model=report_record.llm_model,
            llm_temperature=report_record.llm_temperature,
            embedding_model=report_record.embedding_model,
            embedding_version=report_record.embedding_version,
            collection_name=report_record.collection_name,
        )

        # report_id returned as uuid.UUID (its native type here, same as
        # RetrievalSession.id/ReportRecord.id throughout the service layer)
        # -- consistent with Phase 4's own boundary convention: the domain/
        # service layer works in real uuid.UUID objects, and only the API
        # layer (Step 7) converts to str for JSON serialization, same as
        # app/api/retrieval.py's _build_response() does for session_id.
        return report_record.id, formatted_report, validation_result, generation_metadata
