"""
app/api/patients.py
====================================================================
POST /patients, GET /patients/search, GET /patients/{patient_id}/history.
Thin routes, same standard as every prior endpoint: request validation, a
single call into PatientService (built once per request from a
per-request db session -- PatientService has no other collaborators to
inject, unlike every prior service), and typed response serialization --
no business/medical logic here.

GET /patients/search handles both lookup modes via plain query
parameters, on a single route: `?code=...` (exact patient_code match) OR
`?name=...&dob=...` (exact name+date-of-birth match, no fuzzy matching --
frozen Decision 4). If `code` is supplied it takes precedence over
name+dob (the more precise identifier wins if a caller somehow supplies
both) -- chosen over two separate routes since the frozen spec describes
this as one logical search operation with two equally-valid inputs, not
two different resources. Neither lookup mode being satisfiable (all three
params missing/incomplete) is a 400 -- a malformed request, distinct from
a well-formed search that simply finds zero matches (which returns an
empty list normally, per the frozen spec's "doctor selects from results"
flow -- this endpoint never errors on zero or multiple matches).

GET /patients/{patient_id}/history: a malformed patient_id is a 400, NOT
an empty list. This is deliberately NOT the same "just return what you
find" philosophy as /patients/search's zero-match case, and the
distinction matters clinically: /patients/search's empty list means "a
well-formed query legitimately matched nothing" (a real, valid outcome a
doctor should be able to trust -- "no patient with this exact name+DOB
exists yet"). A malformed patient_id, by contrast, is not a well-formed
query at all -- it's invalid input, structurally the same class of
problem as /patients/search's missing-params case (also a 400, not an
empty list). Silently mapping "malformed ID" to "empty history" would let
a doctor who mistyped or received a garbage patient_id read the response
as "this patient has no prior visits" -- a clinically misleading
conflation of "invalid request" with "confirmed no history" that could
affect a real clinical judgment. So the ValueError from uuid.UUID()'s
parse is caught here and re-raised as HTTPException(400), not swallowed
into `reports = []`; a syntactically valid but unknown/nonexistent
patient_id still legitimately falls through to get_history() returning an
empty list, same as any other "well-formed query, no rows" case elsewhere
in this project.

GET /patients/{patient_id} (Phase 12, additive): added for a real gap
found while building the frontend's Patient Profile page -- neither
/patients/search (needs a code or name+dob, not just an id) nor
/patients/{patient_id}/history (returns only report fields, no patient
details) can answer "get this patient's own details from just their id."
Unlike /patients/search's never-errors-on-zero-matches list semantics,
this is a single-resource-by-id fetch, so a genuinely nonexistent
patient_id is a real 404 here (standard REST semantics for a singular
resource lookup, not a list) -- while a malformed (non-UUID) patient_id
is still a 400, same distinction and same reasoning as the /history route
directly above.

Route registration order note: this route is declared AFTER
/patients/search so the static "search" path segment is matched first,
not swallowed by this dynamic {patient_id} segment.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_doctor, get_db
from app.api.schemas import PatientHistoryReportResponse, PatientResponse, ReportContentResponse
from app.domain.entities import Doctor, Patient, Report
from app.models.retrieval_session import RetrievalSession
from app.services.patient_service import PatientService

router = APIRouter()


class CreatePatientRequest(BaseModel):
    name: str
    date_of_birth: str
    gender: str


def _build_patient_response(patient: Patient) -> PatientResponse:
    return PatientResponse(
        id=patient.id,
        patient_code=patient.patient_code,
        name=patient.name,
        date_of_birth=patient.date_of_birth,
        gender=patient.gender,
    )


def _build_history_response(report: Report, doctor_id: str | None) -> PatientHistoryReportResponse:
    return PatientHistoryReportResponse(
        id=report.id,
        language=report.language.value,
        status=report.status.value,
        # Phase 17 (pre-Step-6 resolution): "what does this report
        # currently say" -> SOURCE is final_content (the doctor's current,
        # possibly-edited version), not the immutable AI draft -- explicit
        # user decision. The response schema's own field name stays
        # `ai_content` though -- a known, minor naming inconsistency left
        # for future cleanup, not fixed this phase (renaming a public
        # response field is a separate API-contract change this step
        # doesn't authorize).
        ai_content=ReportContentResponse(
            examination=report.final_content.examination,
            clinical_history=report.final_content.clinical_history,
            technique=report.final_content.technique,
            findings=report.final_content.findings,
            impression=report.final_content.impression,
            recommendation=report.final_content.recommendation,
            disclaimer=report.final_content.disclaimer,
        ),
        created_at=report.created_at.isoformat() if report.created_at else "",
        doctor_id=doctor_id,
    )


@router.post("/patients", response_model=PatientResponse)
def create_patient(
    request_body: CreatePatientRequest,
    db: Session = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
) -> PatientResponse:
    service = PatientService(db=db)
    patient = service.create(request_body.name, request_body.date_of_birth, request_body.gender)
    return _build_patient_response(patient)


@router.get("/patients/search", response_model=list[PatientResponse])
def search_patients(
    code: str | None = None,
    name: str | None = None,
    dob: str | None = None,
    db: Session = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
) -> list[PatientResponse]:
    service = PatientService(db=db)

    if code is not None:
        found = service.find_by_code(code)
        patients = [found] if found is not None else []
    elif name is not None and dob is not None:
        patients = service.find_by_name_and_dob(name, dob)
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'code', or both 'name' and 'dob', as query parameters.",
        )

    return [_build_patient_response(p) for p in patients]


@router.get("/patients/{patient_id}", response_model=PatientResponse)
def get_patient(
    patient_id: str,
    db: Session = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
) -> PatientResponse:
    service = PatientService(db=db)
    try:
        patient = service.find_by_id(patient_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="patient_id is not a valid UUID.")
    if patient is None:
        raise HTTPException(status_code=404, detail=f"no patient found for patient_id={patient_id}")
    return _build_patient_response(patient)


@router.get("/patients/{patient_id}/history", response_model=list[PatientHistoryReportResponse])
def get_patient_history(
    patient_id: str,
    db: Session = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
) -> list[PatientHistoryReportResponse]:
    service = PatientService(db=db)
    try:
        reports = service.get_history(patient_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="patient_id is not a valid UUID.")

    # Phase 15: each report's owner is derived via its session's doctor_id
    # (per phase13_auth_architecture.md -- reports have no doctor_id of
    # their own). IPatientRepository.get_history()'s frozen Report entity
    # has no session_id field; report.study_id IS str(session_id), a
    # documented substitution (see report_reconstruction.py) reused here
    # rather than changing the frozen interface's return type, which
    # ComparisonService also depends on.
    session_ids = [uuid.UUID(r.study_id) for r in reports]
    sessions = (
        db.query(RetrievalSession).filter(RetrievalSession.id.in_(session_ids)).all()
        if session_ids
        else []
    )
    doctor_by_session_id = {str(s.id): (str(s.doctor_id) if s.doctor_id else None) for s in sessions}

    return [_build_history_response(r, doctor_by_session_id.get(r.study_id)) for r in reports]
