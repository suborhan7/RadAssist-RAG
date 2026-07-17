"""
app/api/doctors.py
====================================================================
GET /doctors/{doctor_id} (Phase 15). Thin route, same standard as every
prior endpoint: request validation, a single call into the existing
DoctorService (Phase 13a), and typed response serialization -- no
business logic here.

A real gap closed by this route, not speculative: OwnershipChip
(design_specification.md §7) needs to show another doctor's name when a
session/report/comparison/explanation isn't the current doctor's own,
and no endpoint could answer "get this doctor's public info from just
their id" -- GET /auth/me only ever returns the CURRENTLY authenticated
doctor. Returns DoctorPublicResponse (id + full_name only), not the full
DoctorResponse -- a doctor's email/created_at are their own business,
not exposed to every other authenticated doctor in the shared registry.

Malformed or missing doctor_id both 404, matching GET /patients/{id}'s
precedent for a different resource: a genuinely nonexistent id is a real
404 for a singular-resource-by-id lookup (not a list, so no
empty-result-is-not-an-error semantics apply here).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_doctor, get_db
from app.api.schemas import DoctorPublicResponse
from app.domain.entities import Doctor
from app.services.doctor_service import DoctorService

router = APIRouter()


@router.get("/doctors/{doctor_id}", response_model=DoctorPublicResponse)
def get_doctor(
    doctor_id: str,
    db: Session = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
) -> DoctorPublicResponse:
    service = DoctorService(db=db)
    try:
        doctor = service.find_by_id(doctor_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"no doctor found for doctor_id={doctor_id}")
    if doctor is None:
        raise HTTPException(status_code=404, detail=f"no doctor found for doctor_id={doctor_id}")
    return DoctorPublicResponse(id=doctor.id, full_name=doctor.full_name)
