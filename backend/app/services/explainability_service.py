"""
app/services/explainability_service.py
====================================================================
Implements the Phase 10 explainability-chat use case: reconstructs the
evidence that produced a persisted report, builds a grounded explanation
prompt, calls the LLM for a free-text answer, and persists the exchange.
Pure sequencing over its injected collaborators -- no business logic, no
clinical judgment of its own.

Evidence reconstruction, not persistence (frozen Phase 10 Decision 1):
ReportGenerationService.generate() computes a ClinicalContext/EvidenceSummary
transiently and discards it. Since retrieval/voting/context-building are
all deterministic and ReportRecord.session_id is stored, re-running the
shared reconstruct_session_evidence() helper (Phase 9 Step 4; this is its
third caller, after ReportGenerationService and QuestionnaireService)
against that session_id reproduces the identical evidence used at
generation time -- valid only because nothing in this system mutates
ChromaDB records or retrieved_evidence rows after a session is created
(explicit, documented assumption, per the frozen spec).

Known limitation, stated plainly rather than silently glossed over: the
reconstructed EvidenceSummary reflects the retrieval evidence only.
Any questionnaire_answers/clinical_notes a clinician supplied at the
ORIGINAL /generate-report call are not persisted anywhere on ReportRecord
(Phase 9's schema doesn't store them), so they cannot be recovered here --
the explanation prompt is grounded in the report content and retrieval
evidence, not in whatever supplementary context (if any) originally
influenced generation.

Report domain-entity reconstruction is delegated to the shared
build_report_domain_entity() helper (app/services/report_reconstruction.py,
extracted this phase) rather than a private method here -- Phase 11's
PatientService needs the identical reconstruction for get_history(), so
this is now shared rather than re-derived a second time.

current_doctor_id (Phase 13, additive): the asking doctor becomes this
explanation's owner, per phase13_auth_architecture.md's "creating a
brand-new explanation makes the creating doctor its owner automatically"
decision. No ownership CHECK here -- any authenticated doctor may ask a
question about any shared/readable report; this parameter only tags who
asked.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.domain.entities import ExplanationRecord
from app.domain.interfaces import (
    IContextBuilder,
    ILabelVoter,
    ILLMOrchestrator,
    IPromptBuilder,
    IVectorStore,
)
from app.models.explanation import Explanation
from app.models.report import ReportRecord
from app.services.exceptions import ReportNotFoundError
from app.services.report_reconstruction import build_report_domain_entity
from app.services.session_reconstruction import reconstruct_session_evidence


class ExplainabilityService:
    def __init__(
        self,
        db: Session,
        vector_store: IVectorStore,
        label_voting_service: ILabelVoter,
        context_builder: IContextBuilder,
        prompt_builder: IPromptBuilder,
        llm_orchestrator: ILLMOrchestrator,
    ) -> None:
        self._db = db
        self._vector_store = vector_store
        self._label_voting_service = label_voting_service
        self._context_builder = context_builder
        self._prompt_builder = prompt_builder
        self._llm_orchestrator = llm_orchestrator

    def explain(
        self, report_id: str, question: str, current_doctor_id: str | None = None
    ) -> ExplanationRecord:
        # Same Uuid-typed-column lesson as Phase 8 Step 6: parse once,
        # raise a clean, specific error for both "malformed" and "missing."
        try:
            report_uuid = uuid.UUID(report_id)
        except ValueError:
            raise ReportNotFoundError(f"report_id is not a valid UUID: {report_id!r}") from None

        report_record = self._db.query(ReportRecord).filter(ReportRecord.id == report_uuid).one_or_none()
        if report_record is None:
            raise ReportNotFoundError(f"no ReportRecord found for report_id={report_id}")

        # Third caller of reconstruct_session_evidence() (after
        # ReportGenerationService and QuestionnaireService) -- same shared
        # helper, not a fourth copy of session/evidence reconstruction.
        _retrieval_session, retrieved_cases, voted_labels = reconstruct_session_evidence(
            self._db, self._vector_store, self._label_voting_service, str(report_record.session_id)
        )
        context = self._context_builder.build(retrieved_cases, voted_labels)

        report = build_report_domain_entity(report_record)

        prompt = self._prompt_builder.build_explanation_prompt(report, question, context.evidence_summary)
        answer = self._llm_orchestrator.answer_question(prompt)

        explanation = Explanation(
            report_id=report_record.id,
            question=question,
            answer=answer,
            doctor_id=uuid.UUID(current_doctor_id) if current_doctor_id is not None else None,
        )
        self._db.add(explanation)
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        return ExplanationRecord(
            id=str(explanation.id),
            report_id=str(explanation.report_id),
            question=question,
            answer=answer,
            created_at=(
                explanation.created_at.isoformat()
                if explanation.created_at
                else datetime.now(timezone.utc).isoformat()
            ),
        )
