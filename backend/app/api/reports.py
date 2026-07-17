"""
app/api/reports.py
====================================================================
GET /reports/{report_id}. Thin route, same standard as every prior
endpoint: request validation (path parameter), a single call into
ReportDetailService (built once per request from app.state singletons,
same pattern as app/api/generation.py), and typed response serialization
-- no business/medical logic here. All orchestration lives in
ReportDetailService, which this step does not modify.

ReportNotFoundError -> 404 for BOTH malformed and missing report_id,
matching app/api/explainability.py's existing precedent for this exact
resource (see ReportDetailService's own docstring for why this is NOT
the same 400-malformed/404-missing split app/api/patients.py uses).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_doctor, get_db
from app.api.schemas import (
    GenerationMetadataResponse,
    ReportContentResponse,
    ReportDetailResponse,
    RetrievedCaseResponse,
    ValidationResponse,
)
from app.domain.entities import Doctor
from app.services.exceptions import ReportNotFoundError
from app.services.report_detail_service import ReportDetail, ReportDetailService

router = APIRouter()


def _build_response(detail: ReportDetail) -> ReportDetailResponse:
    return ReportDetailResponse(
        report_id=detail.report_id,
        session_id=detail.session_id,
        patient_id=detail.patient_id,
        content=ReportContentResponse(
            examination=detail.content.examination,
            clinical_history=detail.content.clinical_history,
            technique=detail.content.technique,
            findings=detail.content.findings,
            impression=detail.content.impression,
            recommendation=detail.content.recommendation,
            disclaimer=detail.content.disclaimer,
        ),
        language=detail.language,
        status=detail.status.value,
        validation=ValidationResponse(
            is_clean=len(detail.validation_warnings) == 0,
            warnings=list(detail.validation_warnings),
        ),
        generation_metadata=GenerationMetadataResponse(
            llm_model=detail.llm_model,
            llm_temperature=detail.llm_temperature,
            embedding_model=detail.embedding_model,
            embedding_version=detail.embedding_version,
            collection_name=detail.collection_name,
        ),
        report_date=detail.report_date,
        created_at=detail.created_at,
        retrieved_cases=[
            RetrievedCaseResponse(
                rank=rank,
                similarity=case.similarity,
                study_uid=case.source_uid,
                primary_label=case.labels[0] if case.labels else "",
                label_set=";".join(case.labels),
                cluster_id=case.cluster_id,
                findings=case.findings,
                impression=case.impression,
                image_path=case.image_path,
            )
            for rank, case in enumerate(detail.retrieved_cases, start=1)
        ],
    )


@router.get("/reports/{report_id}", response_model=ReportDetailResponse)
def get_report(
    report_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
) -> ReportDetailResponse:
    service = ReportDetailService(
        db=db,
        vector_store=request.app.state.vector_store,
        label_voting_service=request.app.state.label_voting_service,
    )
    try:
        detail = service.get_report_detail(report_id)
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return _build_response(detail)
