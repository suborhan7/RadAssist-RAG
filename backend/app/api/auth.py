"""
app/api/auth.py
====================================================================
POST /auth/register, POST /auth/login, GET /auth/me. Thin routes, same
standard as every prior endpoint: request validation, a single call into
AuthService (built once per request from a per-request DoctorService plus
the shared password_hasher/token_service singletons on app.state, same
mixed pattern as Phase 12's ComparisonService construction), and typed
response serialization -- no business logic here.

Named flat here (app/api/auth.py), not app/api/routes/auth.py -- this
codebase has never used a routes/ subdirectory; every router module lives
directly under app/api/ (patients.py, comparisons.py, reports.py, ...).

The JWT is set as an httpOnly cookie on successful register/login (the
frozen auth mechanism -- inaccessible to frontend JS, mitigating XSS
token theft) AND returned in the JSON body, matching
phase13_auth_architecture.md's literal {doctor, token}/{token} response
contracts. These are not in tension: httpOnly protects the cookie from
being READ by injected JS after the fact; it doesn't prevent the
legitimate response the browser itself just received from containing the
same value once.

get_current_doctor is used here for /auth/me only in this step --
wiring it onto every OTHER existing Phase 4-11 route is Step 5, kept
separate since that step touches many already-frozen router files one at
a time.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import AUTH_COOKIE_NAME, get_current_doctor, get_db
from app.api.schemas import DoctorResponse, LoginResponse, RegisterResponse
from app.core.config import settings
from app.domain.entities import Doctor
from app.services.auth_service import AuthService
from app.services.doctor_service import DoctorService
from app.services.exceptions import EmailAlreadyRegisteredError, InvalidCredentialsError

router = APIRouter()


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str


class LoginRequest(BaseModel):
    email: str
    password: str


def _build_doctor_response(doctor: Doctor) -> DoctorResponse:
    return DoctorResponse(
        id=doctor.id, email=doctor.email, full_name=doctor.full_name, created_at=doctor.created_at
    )


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.JWT_EXPIRATION_MINUTES * 60,
    )


def _build_auth_service(request: Request, db: Session) -> AuthService:
    return AuthService(
        doctor_repository=DoctorService(db=db),
        password_hasher=request.app.state.password_hasher,
        token_service=request.app.state.token_service,
    )


@router.post("/auth/register", response_model=RegisterResponse)
def register(
    request_body: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> RegisterResponse:
    service = _build_auth_service(request, db)

    try:
        doctor, token = service.register(request_body.email, request_body.password, request_body.full_name)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    _set_auth_cookie(response, token)
    return RegisterResponse(doctor=_build_doctor_response(doctor), token=token)


@router.post("/auth/login", response_model=LoginResponse)
def login(
    request_body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> LoginResponse:
    service = _build_auth_service(request, db)

    try:
        token = service.login(request_body.email, request_body.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    _set_auth_cookie(response, token)
    return LoginResponse(token=token)


@router.get("/auth/me", response_model=DoctorResponse)
def me(current_doctor: Doctor = Depends(get_current_doctor)) -> DoctorResponse:
    return _build_doctor_response(current_doctor)
