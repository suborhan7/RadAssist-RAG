"""
Integration test: Phase 16 Settings路Profile, via real HTTP through
FastAPI's TestClient. Real POST /auth/register -> real PATCH /auth/me
(partial update) -> real GET /auth/me (confirms it persisted) -> real
GET /system/stats (confirms real, non-negative counts) -> a second real
doctor confirms GET /doctors/{id} (the Phase 15 public endpoint) never
leaks the first doctor's bmdc_number/default_* fields, the one real
regression risk this phase introduces.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.database.base import Base, engine
from app.main import app


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(engine)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    Base.metadata.drop_all(engine)


def _register(client, full_name: str) -> str:
    email = f"phase16-{uuid.uuid4()}@example.com"
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "test-password-123", "full_name": full_name},
    )
    assert response.status_code == 200, response.text
    return response.json()["doctor"]["id"]


def test_patch_auth_me_partial_update_persists_and_stays_self_only(client):
    doctor_a_id = _register(client, "Dr. Settings A")

    # a doctor freshly registered has every profile/preference field None
    me_before = client.get("/auth/me")
    assert me_before.status_code == 200
    assert me_before.json()["bmdc_number"] is None
    assert me_before.json()["default_top_k"] is None

    # partial update: only bmdc_number and default_top_k
    patch_response = client.patch(
        "/auth/me", json={"bmdc_number": "A-98765", "default_top_k": 10}
    )
    assert patch_response.status_code == 200, patch_response.text
    patched_body = patch_response.json()
    assert patched_body["bmdc_number"] == "A-98765"
    assert patched_body["default_top_k"] == 10
    assert patched_body["default_language"] is None  # untouched by this call
    assert patched_body["full_name"] == "Dr. Settings A"  # untouched by this call

    # a second partial update to a DIFFERENT field must not erase the first
    second_patch = client.patch("/auth/me", json={"default_language": "bn"})
    assert second_patch.status_code == 200
    assert second_patch.json()["bmdc_number"] == "A-98765"
    assert second_patch.json()["default_language"] == "bn"

    # GET /auth/me reflects the real persisted state
    me_after = client.get("/auth/me")
    assert me_after.status_code == 200
    assert me_after.json()["bmdc_number"] == "A-98765"
    assert me_after.json()["default_language"] == "bn"

    # --- the real regression risk: a second doctor resolving doctor A's
    # name via the Phase 15 public endpoint must NEVER see these fields ---
    _register(client, "Dr. Settings B")  # cookie jar now authenticates as B
    public_lookup = client.get(f"/doctors/{doctor_a_id}")
    assert public_lookup.status_code == 200
    public_body = public_lookup.json()
    assert public_body == {"id": doctor_a_id, "full_name": "Dr. Settings A"}
    assert "bmdc_number" not in public_body
    assert "default_top_k" not in public_body
    assert "email" not in public_body


def test_system_stats_returns_real_nonnegative_counts(client):
    _register(client, "Dr. Settings Stats")

    response = client.get("/system/stats")
    assert response.status_code == 200, response.text
    body = response.json()

    for field in (
        "masked_images_stored",
        "original_images_stored",
        "index_size",
        "embedding_model",
        "embedding_version",
        "collection_name",
    ):
        assert field in body, f"missing field: {field}"

    # structural guarantee, not a live count -- see SystemStatsService's
    # own module docstring for why this is always exactly 0
    assert body["original_images_stored"] == 0
    assert body["masked_images_stored"] >= 0
    assert body["index_size"] >= 0
    assert body["embedding_model"] == "biomedclip"
    assert body["embedding_version"] == "v1"
