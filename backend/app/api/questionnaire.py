"""
app/api/questionnaire.py
====================================================================
GET /questionnaire/{session_id}. Thin route, same standard as every prior
endpoint: request validation (the path parameter, via FastAPI's own
typing), a single call into the already-constructed QuestionnaireService
(built once per request from singletons on app.state, same pattern as
app/api/generation.py), and typed response serialization -- no business/
medical logic here. All orchestration lives in QuestionnaireService,
which this step does not modify.

SessionNotFoundError -> 404, same mapping as /generate-report's existing
precedent (app/api/generation.py).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.api.schemas import QuestionnaireQuestionResponse, QuestionnaireResponse
from app.domain.entities import Questionnaire
from app.services.exceptions import SessionNotFoundError
from app.services.questionnaire_service import QuestionnaireService

router = APIRouter()


def _build_response(questionnaire: Questionnaire) -> QuestionnaireResponse:
    return QuestionnaireResponse(
        session_id=questionnaire.session_id,
        based_on_label=questionnaire.based_on_label,
        questions=[
            QuestionnaireQuestionResponse(key=q.key, text=q.text, input_type=q.input_type)
            for q in questionnaire.questions
        ],
    )


@router.get("/questionnaire/{session_id}", response_model=QuestionnaireResponse)
def get_questionnaire(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> QuestionnaireResponse:
    service = QuestionnaireService(
        db=db,
        vector_store=request.app.state.vector_store,
        label_voting_service=request.app.state.label_voting_service,
        questionnaire_provider=request.app.state.questionnaire_provider,
    )

    try:
        questionnaire = service.get_questionnaire(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return _build_response(questionnaire)
