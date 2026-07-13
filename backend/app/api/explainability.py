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
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.api.schemas import ExplanationResponse
from app.domain.entities import ExplanationRecord
from app.services.exceptions import ReportNotFoundError
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
        explanation = service.explain(report_id, request_body.question)
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return _build_response(explanation)
