"""
Integration test: the Phase 13a gate, per phase13_auth_architecture.md's
Step 8 (adapted -- see note below). Real POST /auth/register (twice, two
distinct doctors) -> real POST /patients (shared/institutional, no
doctor_id) -> real POST /retrieve + real POST /generate-report as doctor A
-> real GET /reports/{report_id} as doctor B (200, read is universal) ->
real POST /retrieve as doctor B against the SAME shared patient (200,
creates doctor B's own new, separately-owned session). No fakes/mocks
anywhere in this path.

Single TestClient instance, used deliberately: TestClient's underlying
httpx client persists cookies in one jar, so registering doctor B after
doctor A's actions are done overwrites the auth cookie from A's token to
B's -- exactly the mechanism this test uses to act "as" each doctor in
turn (A's actions all happen before B is ever registered).

Scope note (adapted gate, per explicit user decision): the frozen doc's
Step 8 also specifies "doctor B attempts to finalize [the report] (403)".
No finalize/edit/regenerate endpoint exists anywhere in this codebase
(ReportStatus is AI_DRAFT-only, no PATCH/PUT/DELETE route exists at all --
a pre-existing gap from Phase 8/12, unrelated to Phase 13, see
phase13_auth_architecture.md's Risks section). There is currently no
ownership-guarded write endpoint anywhere in this system to exercise a 403
against, since creation is universal (any authenticated doctor may create
a session/comparison/explanation; the creator is simply tagged as owner)
and read is universal. This test therefore proves creation-time ownership
tagging and universal read only -- NOT write-rejection, which has no real
code path to test yet. Add a write-rejection case here once the first
ownership-guarded mutation (e.g. report finalize) is built.

Requires Ollama running locally with settings.OLLAMA_MODEL pulled (only
POST /generate-report needs it) -- the client fixture checks reachability
first and skips with a clear, actionable message if it isn't running.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.database.base import Base, SessionLocal, engine
from app.main import app
from app.models.retrieval_session import RetrievalSession

REPO_ROOT = Path(__file__).resolve().parents[3]
MASKED_DIR = REPO_ROOT / "ml" / "datasets" / "masked"


def _sample_images(n: int) -> list[Path]:
    images = sorted(MASKED_DIR.glob("*.png"))
    if len(images) < n:
        pytest.skip(f"fewer than {n} masked images found under {MASKED_DIR}")
    return images[:n]


def _ollama_available() -> bool:
    try:
        response = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=3.0)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


@pytest.fixture(scope="module")
def client():
    if not _ollama_available():
        pytest.skip(
            f"Ollama not reachable at {settings.OLLAMA_BASE_URL} -- start Ollama and "
            f"ensure '{settings.OLLAMA_MODEL}' is pulled before running this integration test."
        )
    Base.metadata.create_all(engine)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    Base.metadata.drop_all(engine)


def _register(client, full_name: str) -> str:
    email = f"phase13-gate-{uuid.uuid4()}@example.com"
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "test-password-123", "full_name": full_name},
    )
    assert response.status_code == 200, f"failed to register {full_name}: {response.text}"
    return response.json()["doctor"]["id"]


def test_two_doctor_shared_patient_ownership_gate(client):
    doctor_a_id = _register(client, "Dr. A")

    patient_response = client.post(
        "/patients",
        json={"name": "Shared Registry Patient", "date_of_birth": "1980-05-05", "gender": "M"},
    )
    assert patient_response.status_code == 200, f"failed to create shared patient: {patient_response.text}"
    patient_id = patient_response.json()["id"]

    image_a, image_b = _sample_images(2)

    # --- doctor A creates a session + report on the shared patient ---
    with open(image_a, "rb") as f:
        retrieve_response = client.post(
            "/retrieve",
            files={"file": (image_a.name, f, "image/png")},
            data={"top_k": "5", "min_similarity": "0.0", "patient_id": patient_id},
        )
    assert retrieve_response.status_code == 200, f"doctor A's /retrieve failed: {retrieve_response.text}"
    session_a_id = retrieve_response.json()["session_id"]

    generate_response = client.post("/generate-report", json={"session_id": session_a_id, "language": "en"})
    assert generate_response.status_code == 200, f"doctor A's /generate-report failed: {generate_response.text}"
    report_a_id = generate_response.json()["report_id"]

    # --- doctor B registers; the shared TestClient's cookie jar now
    # authenticates every subsequent request as doctor B ---
    doctor_b_id = _register(client, "Dr. B")
    assert doctor_b_id != doctor_a_id

    # doctor B reads doctor A's report: 200, read is universal
    read_response = client.get(f"/reports/{report_a_id}")
    assert read_response.status_code == 200, f"doctor B's read of doctor A's report failed: {read_response.text}"
    assert read_response.json()["report_id"] == report_a_id

    # doctor B creates their OWN new session against the SAME shared patient: 200
    with open(image_b, "rb") as f:
        retrieve_response_b = client.post(
            "/retrieve",
            files={"file": (image_b.name, f, "image/png")},
            data={"top_k": "5", "min_similarity": "0.0", "patient_id": patient_id},
        )
    assert retrieve_response_b.status_code == 200, f"doctor B's /retrieve failed: {retrieve_response_b.text}"
    session_b_id = retrieve_response_b.json()["session_id"]
    assert session_b_id != session_a_id

    # --- real DB verification: each session is independently owned; the
    # shared patient_id is identical on both, doctor A's session is
    # untouched by doctor B's later action ---
    db = SessionLocal()
    try:
        session_a = db.query(RetrievalSession).filter(RetrievalSession.id == uuid.UUID(session_a_id)).one()
        session_b = db.query(RetrievalSession).filter(RetrievalSession.id == uuid.UUID(session_b_id)).one()

        assert str(session_a.doctor_id) == doctor_a_id
        assert str(session_b.doctor_id) == doctor_b_id
        assert str(session_a.patient_id) == patient_id
        assert str(session_b.patient_id) == patient_id
    finally:
        db.close()
