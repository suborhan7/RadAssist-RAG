"""
app/services/auth_service.py
====================================================================
Pure orchestration over IDoctorRepository/IPasswordHasher/ITokenService --
no persistence or crypto logic of its own, same "services orchestrate,
collaborators do the real work" discipline as every prior service in this
project.

register(): a pre-check (find_by_email) plus the doctors.email UNIQUE
index (Step 2's migration) as the actual guarantee -- same documented
concurrency caveat as PatientService's patient_code generation: two
concurrent registrations for the same email could both pass the
pre-check before either commits, but the UNIQUE constraint makes a
genuine race fail loudly (IntegrityError), not silently create a
duplicate. Acceptable for this thesis system's expected usage.

login(): deliberately returns the SAME InvalidCredentialsError for both
"no such email" and "wrong password" -- see that exception's own
docstring for why this is a security property, not a missed
distinct-failure-modes case.
"""
from __future__ import annotations

from app.domain.entities import Doctor
from app.domain.interfaces import IDoctorRepository, IPasswordHasher, ITokenService
from app.services.exceptions import EmailAlreadyRegisteredError, InvalidCredentialsError


class AuthService:
    def __init__(
        self,
        doctor_repository: IDoctorRepository,
        password_hasher: IPasswordHasher,
        token_service: ITokenService,
    ) -> None:
        self._doctor_repository = doctor_repository
        self._password_hasher = password_hasher
        self._token_service = token_service

    def register(self, email: str, password: str, full_name: str) -> tuple[Doctor, str]:
        if self._doctor_repository.find_by_email(email) is not None:
            raise EmailAlreadyRegisteredError(f"a doctor with email={email!r} is already registered")

        password_hash = self._password_hasher.hash(password)
        doctor = self._doctor_repository.create(email, password_hash, full_name)
        token = self._token_service.issue(doctor.id)
        return doctor, token

    def login(self, email: str, password: str) -> str:
        doctor = self._doctor_repository.find_by_email(email)
        if doctor is None or not self._password_hasher.verify(password, doctor.password_hash):
            raise InvalidCredentialsError("invalid email or password")

        return self._token_service.issue(doctor.id)
