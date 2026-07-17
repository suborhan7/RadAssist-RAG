"""
Unit tests for AuthService, per phase13_auth_architecture.md. Real DB
(in-memory SQLite via StaticPool, same pattern as test_patient_service.py)
for DoctorService; password_hasher/token_service are hand-built fakes,
per the frozen spec's own testing strategy ("ownership-check helper in
isolation") and this project's established "all non-DB collaborators
faked" unit-testing convention.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.services.auth_service import AuthService
from app.services.doctor_service import DoctorService
from app.services.exceptions import EmailAlreadyRegisteredError, InvalidCredentialsError


class FakePasswordHasher:
    """"hash" is reversible on purpose (prefixed marker string) -- this
    fake tests AuthService's OWN orchestration logic, not real Argon2
    behavior (already covered for real in test_auth_infrastructure.py)."""

    def hash(self, plain: str) -> str:
        return f"hashed:{plain}"

    def verify(self, plain: str, hashed: str) -> bool:
        return hashed == f"hashed:{plain}"


class FakeTokenService:
    def __init__(self) -> None:
        self.issue_calls: list[str] = []

    def issue(self, doctor_id: str) -> str:
        self.issue_calls.append(doctor_id)
        return f"token-for-{doctor_id}"

    def verify(self, token: str) -> str:
        raise NotImplementedError


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return engine


def _make_service(db):
    fakes = {"password_hasher": FakePasswordHasher(), "token_service": FakeTokenService()}
    service = AuthService(
        doctor_repository=DoctorService(db=db),
        password_hasher=fakes["password_hasher"],
        token_service=fakes["token_service"],
    )
    return service, fakes


def test_register_creates_doctor_and_returns_token():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    service, fakes = _make_service(db)

    doctor, token = service.register("a@example.com", "hunter2", "Dr. A")

    assert doctor.email == "a@example.com"
    assert doctor.full_name == "Dr. A"
    assert doctor.password_hash == "hashed:hunter2"  # never the plaintext
    assert token == f"token-for-{doctor.id}"
    assert fakes["token_service"].issue_calls == [doctor.id]

    db.close()


def test_register_rejects_duplicate_email():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    service, _ = _make_service(db)
    service.register("a@example.com", "hunter2", "Dr. A")

    with pytest.raises(EmailAlreadyRegisteredError):
        service.register("a@example.com", "different-password", "Dr. A Impersonator")

    db.close()


def test_login_returns_token_for_correct_credentials():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    service, fakes = _make_service(db)
    doctor, _ = service.register("a@example.com", "hunter2", "Dr. A")

    token = service.login("a@example.com", "hunter2")

    assert token == f"token-for-{doctor.id}"

    db.close()


def test_login_rejects_wrong_password():
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    service, _ = _make_service(db)
    service.register("a@example.com", "hunter2", "Dr. A")

    with pytest.raises(InvalidCredentialsError):
        service.login("a@example.com", "wrong-password")

    db.close()


def test_login_rejects_nonexistent_email_with_the_same_error_as_wrong_password():
    """Proves the deliberate non-distinguishing design (see
    InvalidCredentialsError's docstring): a nonexistent email and a wrong
    password for a real email must be indistinguishable to the caller."""
    engine = _make_engine()
    db = sessionmaker(bind=engine)()
    service, _ = _make_service(db)

    with pytest.raises(InvalidCredentialsError):
        service.login("nobody@example.com", "irrelevant")

    db.close()
