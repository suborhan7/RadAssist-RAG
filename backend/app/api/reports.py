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

Phase 17 Step 4: PATCH /reports/{report_id} -- the first real write
endpoint for this resource. All business logic (ownership check, 409-
when-final guard, DOCTOR_EDITED transition, audit log insert) lives in
ReportEditService; this route only validates the request body, maps
ReportEditService's exceptions to HTTP status codes, and re-fetches the
full detail via ReportDetailService afterward (reusing the exact same
reconstruction path GET /reports/{report_id} already uses, rather than
building a second, parallel response-assembly path).

ReportUpdateRequest's 5 fields are all Optional[str] = None (partial-PATCH
semantics): only fields actually present and non-None are applied to
final_content, matching Step 7's per-section independent-commit design
(each section save is expected to PATCH only the one field just edited).
`examination`/`disclaimer` are deliberately NOT in this schema -- both
stay AI-set/read-only per the frozen doc's reasoning.

Phase 17 Step 5: PATCH /reports/{report_id}/finalize -- no request body
(finalize takes no input, just current_doctor's identity from the auth
cookie). Same error-mapping/re-fetch pattern as Step 4's PATCH route, plus
ReportValidationError -> 422 (empty findings/impression at finalize time).
Valid from both AI_DRAFT (doctor accepts as-is) and DOCTOR_EDITED -- not
gated on having been edited first.

Phase 17 Step 6: ReportDetailResponse gains ai_draft_content (the
immutable AI draft, for "Restore AI Draft"), finalized_at/finalized_by
(nullable), and audit_log (edit history, oldest first) -- all additive,
all assembled by ReportDetailService/ReportDetail, this route only
serializes them. `content` itself already sources final_content (resolved
before this step).

Phase 19: POST /reports/{report_id}/regenerate-section -- produces a
candidate only, no DB write (Decision 1: accepting one is a normal
PATCH /reports/{report_id} call, made separately). Same ownership/
already-final error mapping as the routes above, reusing the exact same
ForbiddenError/ReportAlreadyFinalizedError types. No 422 mapping needed
for an invalid `field` -- RegenerateSectionRequest's EditableReportField
type makes Pydantic reject that before this function ever runs. Was a
fresh, independent Literal here originally, duplicating
prompt_builder.py's separate _SECTION_FIELD_LABELS dict keys -- both now
derive from the single EditableReportField enum (app/domain/entities.py).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_doctor, get_db
from app.api.schemas import (
    GenerationMetadataResponse,
    RegenerateSectionResponse,
    ReportAuditLogEntryResponse,
    ReportContentResponse,
    ReportDetailResponse,
    ReportListItemResponse,
    RetrievedCaseResponse,
    ValidationResponse,
)
from app.domain.entities import Doctor, EditableReportField
from app.services.exceptions import (
    ForbiddenError,
    ReportAlreadyFinalizedError,
    ReportNotFoundError,
    ReportValidationError,
)
from app.services.report_detail_service import ReportDetail, ReportDetailService
from app.services.report_edit_service import ReportEditService

router = APIRouter()


class RegenerateSectionRequest(BaseModel):
    # EditableReportField (app/domain/entities.py) is the single canonical
    # 5-field type -- Pydantic validates/422s an invalid name at the API
    # boundary automatically, before ReportEditService.regenerate_section()
    # is ever called (that method trusts `field` is already valid rather
    # than re-checking).
    field: EditableReportField


class ReportUpdateRequest(BaseModel):
    clinical_history: str | None = None
    technique: str | None = None
    findings: str | None = None
    impression: str | None = None
    recommendation: str | None = None


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
        ai_draft_content=ReportContentResponse(
            examination=detail.ai_draft_content.examination,
            clinical_history=detail.ai_draft_content.clinical_history,
            technique=detail.ai_draft_content.technique,
            findings=detail.ai_draft_content.findings,
            impression=detail.ai_draft_content.impression,
            recommendation=detail.ai_draft_content.recommendation,
            disclaimer=detail.ai_draft_content.disclaimer,
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
        doctor_id=detail.doctor_id,
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
        finalized_at=detail.finalized_at,
        finalized_by=detail.finalized_by,
        audit_log=[
            ReportAuditLogEntryResponse(
                id=entry.id, doctor_id=entry.doctor_id, action=entry.action, at=entry.at
            )
            for entry in detail.audit_log
        ],
    )


@router.get("/reports", response_model=list[ReportListItemResponse])
def list_reports(
    request: Request,
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
) -> list[ReportListItemResponse]:
    service = ReportDetailService(
        db=db,
        vector_store=request.app.state.vector_store,
        label_voting_service=request.app.state.label_voting_service,
    )
    items = service.list_reports_for_doctor(current_doctor.id, limit)
    return [
        ReportListItemResponse(
            report_id=item.report_id,
            patient_id=item.patient_id,
            patient_name=item.patient_name,
            patient_code=item.patient_code,
            status=item.status.value,
            report_date=item.report_date,
            created_at=item.created_at,
            content=ReportContentResponse(
                examination=item.content.examination,
                clinical_history=item.content.clinical_history,
                technique=item.content.technique,
                findings=item.content.findings,
                impression=item.content.impression,
                recommendation=item.content.recommendation,
                disclaimer=item.content.disclaimer,
            ),
            ai_draft_content=ReportContentResponse(
                examination=item.ai_draft_content.examination,
                clinical_history=item.ai_draft_content.clinical_history,
                technique=item.ai_draft_content.technique,
                findings=item.ai_draft_content.findings,
                impression=item.ai_draft_content.impression,
                recommendation=item.ai_draft_content.recommendation,
                disclaimer=item.ai_draft_content.disclaimer,
            ),
        )
        for item in items
    ]


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


@router.patch("/reports/{report_id}", response_model=ReportDetailResponse)
def update_report(
    report_id: str,
    request_body: ReportUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
) -> ReportDetailResponse:
    # Only fields actually present and non-None are applied -- see this
    # module's docstring for why partial-PATCH semantics matter here.
    updates = {
        field: value
        for field, value in request_body.model_dump().items()
        if value is not None
    }

    edit_service = ReportEditService(db=db)
    try:
        edit_service.update_content(report_id, current_doctor.id, updates)
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ReportAlreadyFinalizedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    detail_service = ReportDetailService(
        db=db,
        vector_store=request.app.state.vector_store,
        label_voting_service=request.app.state.label_voting_service,
    )
    detail = detail_service.get_report_detail(report_id)
    return _build_response(detail)


@router.patch("/reports/{report_id}/finalize", response_model=ReportDetailResponse)
def finalize_report(
    report_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
) -> ReportDetailResponse:
    edit_service = ReportEditService(db=db)
    try:
        edit_service.finalize(report_id, current_doctor.id)
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ReportAlreadyFinalizedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ReportValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    detail_service = ReportDetailService(
        db=db,
        vector_store=request.app.state.vector_store,
        label_voting_service=request.app.state.label_voting_service,
    )
    detail = detail_service.get_report_detail(report_id)
    return _build_response(detail)


@router.post("/reports/{report_id}/regenerate-section", response_model=RegenerateSectionResponse)
def regenerate_section(
    report_id: str,
    request_body: RegenerateSectionRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
) -> RegenerateSectionResponse:
    edit_service = ReportEditService(
        db=db,
        vector_store=request.app.state.vector_store,
        label_voting_service=request.app.state.label_voting_service,
        context_builder=request.app.state.context_builder,
        llm_orchestrator=request.app.state.llm_orchestrator,
        prompt_builder=request.app.state.prompt_builder,
    )
    try:
        candidate, context_incomplete = edit_service.regenerate_section(
            report_id, request_body.field, current_doctor.id
        )
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ReportAlreadyFinalizedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return RegenerateSectionResponse(
        field=request_body.field, candidate=candidate, context_incomplete=context_incomplete
    )
