"""
app/api/dependencies.py
====================================================================
Shared FastAPI dependencies used by more than one route module.
get_db() was previously duplicated identically in both api/retrieval.py
(Phase 4) and api/generation.py (Phase 8) -- consolidated here since
neither is a frozen interface, unlike the get_db()-in-retrieval.py
duplication that would have required touching a frozen file to fix.

get_current_doctor() (Phase 13) reads the JWT from an httpOnly cookie
(per phase13_auth_architecture.md's frozen auth mechanism -- not an
Authorization header, so the token is inaccessible to frontend JS,
mitigating XSS token theft), verifies it via the shared ITokenService
singleton on app.state (same "expensive/shared collaborator lives on
app.state" pattern as every other cross-cutting singleton in main.py's
lifespan), and resolves the real Doctor. This module builds ONLY the
dependency itself -- wiring it onto every Phase 4-11 route is Step 5,
kept separate since that step touches many already-frozen router files
one at a time, not because this dependency isn't ready sooner (GET
/auth/me, Step 4, already needs it).
"""
from __future__ import annotations

from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database.base import SessionLocal
from app.domain.entities import Doctor
from app.services.doctor_service import DoctorService
from app.services.exceptions import InvalidTokenError

AUTH_COOKIE_NAME = "radassist_token"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_doctor(
    request: Request,
    db: Session = Depends(get_db),
    radassist_token: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
) -> Doctor:
    if radassist_token is None:
        raise HTTPException(status_code=401, detail="not authenticated")

    token_service = request.app.state.token_service
    try:
        doctor_id = token_service.verify(radassist_token)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    doctor_repository = DoctorService(db=db)
    try:
        doctor = doctor_repository.find_by_id(doctor_id)
    except ValueError:
        # The doctor_id inside a validly-signed token should always be a
        # real UUID (we issued it), but defensively treat a malformed
        # subject the same as "no such doctor" rather than a 500.
        doctor = None
    if doctor is None:
        raise HTTPException(status_code=401, detail="doctor for this token no longer exists")

    return doctor
