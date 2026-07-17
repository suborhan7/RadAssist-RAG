"""
Unit tests for Phase 13's two new infrastructure adapters:
Argon2PasswordHasher (IPasswordHasher) and JWTHandler (ITokenService).
Pure, no DB, no FastAPI -- these are infrastructure-layer components
tested in isolation, same convention as test_structural_validator.py.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import settings
from app.infrastructure.jwt_handler import JWTHandler
from app.infrastructure.password_hasher import Argon2PasswordHasher
from app.services.exceptions import InvalidTokenError


def test_password_hash_round_trips_correctly():
    hasher = Argon2PasswordHasher()
    hashed = hasher.hash("correct horse battery staple")

    assert hashed != "correct horse battery staple"  # never store plaintext
    assert hasher.verify("correct horse battery staple", hashed) is True


def test_password_verify_rejects_wrong_password():
    hasher = Argon2PasswordHasher()
    hashed = hasher.hash("correct horse battery staple")

    assert hasher.verify("wrong password", hashed) is False


def test_jwt_issue_and_verify_round_trip():
    handler = JWTHandler()
    doctor_id = "11111111-1111-1111-1111-111111111111"

    token = handler.issue(doctor_id)
    assert handler.verify(token) == doctor_id


def test_jwt_verify_rejects_expired_token():
    # Construct an already-expired token directly (not via handler.issue(),
    # which always sets a future expiration) -- real proof the expiration
    # claim is actually checked, not just present and ignored.
    now = datetime.now(timezone.utc)
    expired_payload = {
        "sub": "11111111-1111-1111-1111-111111111111",
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),
    }
    expired_token = jwt.encode(expired_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    handler = JWTHandler()
    with pytest.raises(InvalidTokenError):
        handler.verify(expired_token)


def test_jwt_verify_rejects_tampered_token():
    handler = JWTHandler()
    token = handler.issue("11111111-1111-1111-1111-111111111111")

    # Flip the last character of the signature segment -- a real tampered
    # token, not a synthetic invalid string, proving signature verification
    # itself is what catches this.
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")

    with pytest.raises(InvalidTokenError):
        handler.verify(tampered)


def test_jwt_verify_rejects_token_signed_with_a_different_secret():
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "11111111-1111-1111-1111-111111111111",
        "iat": now,
        "exp": now + timedelta(minutes=60),
    }
    forged_token = jwt.encode(
        payload, "a-completely-different-secret-key-value", algorithm=settings.JWT_ALGORITHM
    )

    handler = JWTHandler()
    with pytest.raises(InvalidTokenError):
        handler.verify(forged_token)
