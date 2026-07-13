"""
app/api/comparisons.py
====================================================================
POST /comparisons. Thin route, same standard as every prior endpoint:
request validation (a Pydantic body model), a single call into
ComparisonService (built once per request -- patient_repository is a
per-request PatientService, same reasoning as app/api/patients.py, since
it depends on nothing but the per-request db session; deterministic_comparator/
prompt_builder/llm_orchestrator are the already-constructed singletons
from app.state, same pattern as app/api/explainability.py), and typed
response serialization -- no business/medical logic here. All
orchestration lives in ComparisonService, which this step does not modify.

Error mapping, stated explicitly per the frozen spec's requirement not to
collapse distinct failure modes into an indistinguishable response: both
ReportNotFoundError and NoPriorReportError map to HTTP 404 (both are, from
an HTTP semantics standpoint, "the resource needed to fulfill this request
doesn't exist") -- but the two exceptions represent genuinely different
client-facing problems (a bad/nonexistent report_id vs. a patient with
nothing to compare against yet), so each is given a distinct, prefixed
detail message ("Report not found: ..." vs. "No prior report available:
...") rather than one generic "not found" string for both. A client
cannot distinguish them by status code alone here, but can by response
body content -- same principle as Step 8's exception-type split, applied
now at the HTTP boundary instead of the Python exception-type boundary.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.api.schemas import ComparisonFactsResponse, ComparisonResponse
from app.domain.entities import Comparison
from app.services.comparison_service import ComparisonService
from app.services.exceptions import NoPriorReportError, ReportNotFoundError
from app.services.patient_service import PatientService

router = APIRouter()


class CreateComparisonRequest(BaseModel):
    patient_id: str
    current_report_id: str
    compare_against_report_id: str | None = None


def _build_response(comparison: Comparison) -> ComparisonResponse:
    return ComparisonResponse(
        id=comparison.id,
        patient_id=comparison.patient_id,
        previous_report_id=comparison.previous_report_id,
        current_report_id=comparison.current_report_id,
        facts=ComparisonFactsResponse(
            previous_report_id=comparison.facts.previous_report_id,
            current_report_id=comparison.facts.current_report_id,
            resolved_findings=list(comparison.facts.resolved_findings),
            persistent_findings=list(comparison.facts.persistent_findings),
            new_findings=list(comparison.facts.new_findings),
            days_between_studies=comparison.facts.days_between_studies,
        ),
        narrative=comparison.narrative,
        created_at=comparison.created_at,
    )


@router.post("/comparisons", response_model=ComparisonResponse)
def create_comparison(
    request_body: CreateComparisonRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ComparisonResponse:
    service = ComparisonService(
        db=db,
        patient_repository=PatientService(db=db),
        deterministic_comparator=request.app.state.deterministic_comparator,
        prompt_builder=request.app.state.prompt_builder,
        llm_orchestrator=request.app.state.llm_orchestrator,
    )

    try:
        comparison = service.compare(
            request_body.patient_id,
            request_body.current_report_id,
            request_body.compare_against_report_id,
        )
    except NoPriorReportError as exc:
        raise HTTPException(status_code=404, detail=f"No prior report available: {exc}") from exc
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Report not found: {exc}") from exc

    return _build_response(comparison)
