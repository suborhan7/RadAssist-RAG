"""
app/infrastructure/password_hasher.py
====================================================================
Implements IPasswordHasher. Thin wrapper over argon2-cffi's high-level
PasswordHasher -- Argon2id (the library's default variant) is the
current OWASP-recommended choice over bcrypt/PBKDF2 for new systems, and
argon2-cffi handles salt generation/storage inside the encoded hash
string itself, so no separate salt column is needed on `doctors`
(`password_hash` alone is sufficient, matching phase13_auth_architecture.md's
Doctor entity shape).
"""
from __future__ import annotations

from argon2 import PasswordHasher as Argon2Hasher
from argon2.exceptions import VerifyMismatchError


class Argon2PasswordHasher:
    """Satisfies domain.interfaces.IPasswordHasher."""

    def __init__(self) -> None:
        self._hasher = Argon2Hasher()

    def hash(self, plain: str) -> str:
        return self._hasher.hash(plain)

    def verify(self, plain: str, hashed: str) -> bool:
        try:
            return self._hasher.verify(hashed, plain)
        except VerifyMismatchError:
            return False
