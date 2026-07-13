"""
app/api/generation.py
====================================================================
POST /generate-report. Thin route, same standard as Phase 4 Step 11: request
validation (via a Pydantic request body model), a single call into the
already-constructed ReportGenerationService (built once per request from
singletons on app.state, same pattern as app/api/retrieval.py), and typed
response serialization -- no business/medical logic here. All orchestration
lives in ReportGenerationService, which this step does not modify.

Exception -> HTTP status mapping (each is a distinct failure mode, per the
frozen Phase 8 spec):
  SessionNotFoundError          -> 404 (the referenced session simply doesn't exist)
  LLMTransportError              -> 502 (Ollama, an upstream dependency this API
                                    acts as a client of, failed to produce a usable
                                    response -- this server itself is healthy, so
                                    502 Bad Gateway is the more accurate status than
                                    503 Service Unavailable, which would imply THIS
                                    server is the one overloaded/down)
  LLMGenerationValidationError   -> 422 (the request was well-formed, but semantic
                                    generation could not be validated after
                                    exhausting the content retry budget) -- the
                                    response body includes the last raw response
                                    and validation errors so a caller can see
                                    exactly what went wrong, not just a bare 422.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.api.schemas import (
    FormattedReportResponse,
    GenerateReportResponse,
    GenerationMetadataResponse,
    ReportContentResponse,
    ValidationResponse,
)
from app.domain.entities import FormattedReport, GenerationMetadata, SemanticValidationResult
from app.services.exceptions import LLMGenerationValidationError, LLMTransportError, SessionNotFoundError
from app.services.report_generation_service import ReportGenerationService

router = APIRouter()


class GenerateReportRequest(BaseModel):
    session_id: str
    language: str = "en"


def _build_response(
    report_id,
    session_id: str,
    formatted_report: FormattedReport,
    validation: SemanticValidationResult,
    generation_metadata: GenerationMetadata,
) -> GenerateReportResponse:
    return GenerateReportResponse(
        report_id=str(report_id),
        session_id=session_id,
        formatted_report=FormattedReportResponse(
            content=ReportContentResponse(
                examination=formatted_report.content.examination,
                clinical_history=formatted_report.content.clinical_history,
                technique=formatted_report.content.technique,
                findings=formatted_report.content.findings,
                impression=formatted_report.content.impression,
                recommendation=formatted_report.content.recommendation,
                disclaimer=formatted_report.content.disclaimer,
            ),
            language=formatted_report.language,
            report_date=formatted_report.report_date,
            section_headers=formatted_report.section_headers,
        ),
        validation=ValidationResponse(is_clean=validation.is_clean, warnings=list(validation.warnings)),
        generation_metadata=GenerationMetadataResponse(
            llm_model=generation_metadata.llm_model,
            llm_temperature=generation_metadata.llm_temperature,
            embedding_model=generation_metadata.embedding_model,
            embedding_version=generation_metadata.embedding_version,
            collection_name=generation_metadata.collection_name,
        ),
    )


@router.post("/generate-report", response_model=GenerateReportResponse)
def generate_report(
    request_body: GenerateReportRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> GenerateReportResponse:
    service = ReportGenerationService(
        db=db,
        vector_store=request.app.state.vector_store,
        label_voting_service=request.app.state.label_voting_service,
        context_builder=request.app.state.context_builder,
        llm_orchestrator=request.app.state.llm_orchestrator,
        response_validator=request.app.state.response_validator,
        report_formatter=request.app.state.report_formatter,
    )

    try:
        report_id, formatted_report, validation, generation_metadata = service.generate(
            request_body.session_id, request_body.language
        )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LLMTransportError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except LLMGenerationValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "message": str(exc),
                "last_raw_response": exc.last_raw_response,
                "last_validation_errors": exc.last_validation_errors,
            },
        ) from exc

    return _build_response(report_id, request_body.session_id, formatted_report, validation, generation_metadata)
