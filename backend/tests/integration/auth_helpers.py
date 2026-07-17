"""
tests/integration/auth_helpers.py
====================================================================
Shared helper for Phase 13: registers a real, uniquely-emailed doctor via
POST /auth/register on a given TestClient before any other request is
made. TestClient's underlying httpx client persists cookies across
requests automatically, so the real httpOnly auth cookie this call
receives covers every subsequent request that SAME client instance makes
-- exactly the mechanism every existing integration test now needs, since
Phase 13 Step 5 wires Depends(get_current_doctor) onto every Phase 4-12
route.

A fresh, uniquely-emailed doctor per call (not a shared fixture account)
avoids any cross-test coupling through the real doctors table.
"""
from __future__ import annotations

import uuid


def register_test_doctor(client, full_name: str = "Test Doctor") -> str:
    """Registers a real doctor with a random unique email; returns the
    real doctor_id. Asserts a real 200, not a silent skip, so a broken
    auth wiring fails this helper loudly rather than producing confusing
    401s three calls later in whichever test used it."""
    email = f"test-{uuid.uuid4()}@example.com"
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "test-password-123", "full_name": full_name},
    )
    assert response.status_code == 200, f"failed to register test doctor: {response.text}"
    return response.json()["doctor"]["id"]
