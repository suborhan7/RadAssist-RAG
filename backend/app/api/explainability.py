"""
app/api/explainability.py
====================================================================
POST /reports/{report_id}/explain. Thin route, same standard as every
prior endpoint: request validation (path parameter + a Pydantic request
body model), a single call into the already-constructed
ExplainabilityService (built once per request from singletons on
app.state, same pattern as app/api/generation.py and
app/api/questionnaire.py), and typed response serialization -- no
business/medical logic here. All orchestration lives in
ExplainabilityService, which this step does not modify.

ReportNotFoundError -> 404, same mapping pattern as every prior not-found
case (SessionNotFoundError -> 404 in generation.py/questionnaire.py).

LLMTransportError -> 502 (Phase 12 fix, found while building the frontend
Explainability Chat page): a real, pre-existing gap since Phase 10 --
answer_question() reuses the exact same transport-retry mechanism as
generate_draft() and can genuinely raise LLMTransportError once that
budget is exhausted, but this route never caught it, so a real Ollama
outage during /explain would have propagated as an unhandled exception
(no clean detail, likely no CORS headers either -- the same failure
shape Phase 12 Step 2 found with an unhandled 500 elsewhere), never
exercised by any existing test. Mapped identically to
app/api/generation.py's existing LLMTransportError -> 502 precedent for
the same exception type. answer_question() has no content-retry loop
(free-text has no schema to validate), so LLMGenerationValidationError
cannot occur here and needs no handler.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_doctor, get_db
from app.api.schemas import ExplanationResponse
from app.domain.entities import Doctor, ExplanationRecord
from app.services.exceptions import LLMTransportError, ReportNotFoundError
from app.services.explainability_service import ExplainabilityService

router = APIRouter()


class ExplainRequest(BaseModel):
    question: str


def _build_response(explanation: ExplanationRecord) -> ExplanationResponse:
    return ExplanationResponse(
        id=explanation.id,
        report_id=explanation.report_id,
        question=explanation.question,
        answer=explanation.answer,
        created_at=explanation.created_at,
    )


@router.post("/reports/{report_id}/explain", response_model=ExplanationResponse)
def explain_report(
    report_id: str,
    request_body: ExplainRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
) -> ExplanationResponse:
    service = ExplainabilityService(
        db=db,
        vector_store=request.app.state.vector_store,
        label_voting_service=request.app.state.label_voting_service,
        context_builder=request.app.state.context_builder,
        prompt_builder=request.app.state.prompt_builder,
        llm_orchestrator=request.app.state.llm_orchestrator,
    )

    try:
        explanation = service.explain(report_id, request_body.question, current_doctor_id=current_doctor.id)
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LLMTransportError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return _build_response(explanation)
