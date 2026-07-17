"""
app/infrastructure/jwt_handler.py
====================================================================
Implements ITokenService. Thin wrapper over PyJWT. `sub` (subject) claim
carries the doctor_id; `exp` is set from settings.JWT_EXPIRATION_MINUTES
and PyJWT validates it automatically on decode. Every PyJWT failure mode
(expired, tampered signature, malformed token) is caught under the single
base `jwt.PyJWTError` and re-raised as this project's own
InvalidTokenError -- callers depend on this project's exception type, not
PyJWT's, so the token library itself stays swappable (same reasoning as
every other Protocol-backed infrastructure adapter in this codebase).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings
from app.services.exceptions import InvalidTokenError


class JWTHandler:
    """Satisfies domain.interfaces.ITokenService."""

    def issue(self, doctor_id: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": doctor_id,
            "iat": now,
            "exp": now + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES),
        }
        return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    def verify(self, token: str) -> str:
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        except jwt.PyJWTError as exc:
            raise InvalidTokenError(f"invalid or expired token: {exc}") from exc
        return payload["sub"]
