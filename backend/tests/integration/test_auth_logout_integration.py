"""
Integration test: POST /auth/logout, added alongside Phase 17's screen-
coverage check (item #1 -- no logout mechanism existed anywhere in this
system). Real TestClient round-trip, no fakes: register -> GET /auth/me
succeeds (real cookie set) -> POST /auth/logout -> GET /auth/me now fails
(real cookie cleared). The auth cookie is httpOnly (Phase 13a), so this
is the only way to prove logout actually works -- a client-side cookie
clear could never touch it, and only a real Set-Cookie expiring it on a
real response can be verified this way.

`with TestClient(app, ...) as client` (not a bare constructor call) is
required here, same as every other integration test in this suite --
the `with` block is what triggers FastAPI's lifespan startup, which is
where app.state.password_hasher/token_service (needed by AuthService)
actually get created.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.database.base import Base, engine
from app.main import app


@pytest.fixture
def client():
    Base.metadata.create_all(engine)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    Base.metadata.drop_all(engine)


def test_logout_clears_the_auth_cookie_and_deauthenticates(client):
    email = f"logout-test-{uuid.uuid4()}@example.com"
    register_response = client.post(
        "/auth/register",
        json={"email": email, "password": "test-password-123", "full_name": "Dr. Logout Test"},
    )
    assert register_response.status_code == 200, register_response.text

    # authenticated call succeeds before logout
    me_before = client.get("/auth/me")
    assert me_before.status_code == 200, me_before.text
    assert me_before.json()["email"] == email

    logout_response = client.post("/auth/logout")
    assert logout_response.status_code == 200, logout_response.text
    assert logout_response.json() == {"success": True}

    # authenticated call now fails -- real proof the cookie was cleared,
    # not just that the endpoint returned 200
    me_after = client.get("/auth/me")
    assert me_after.status_code == 401, me_after.text


def test_logout_with_no_cookie_still_succeeds(client):
    """Logging out when already logged out (or never logged in) is not an
    error -- there's no auth dependency on this route, deliberately (see
    app/api/auth.py's logout() docstring)."""
    logout_response = client.post("/auth/logout")
    assert logout_response.status_code == 200, logout_response.text
    assert logout_response.json() == {"success": True}
