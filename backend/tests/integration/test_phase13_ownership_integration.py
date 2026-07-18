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

Scope note (RESOLVED, Phase 17 Step 9): the frozen doc's Step 8 also
specifies "doctor B attempts to finalize [the report] (403)". At Phase 13a
this was deferred -- no finalize/edit/regenerate endpoint existed anywhere
in this codebase yet (ReportStatus was AI_DRAFT-only, no PATCH/PUT/DELETE
route existed at all), so there was no ownership-guarded write endpoint to
exercise a 403 against; creation and read were both universal. Phase 17
built the first one (PATCH /reports/{id}/finalize), so this test now
includes the originally-deferred write-rejection case directly, closing
this note rather than leaving it as a permanent gap. See
test_phase17_edit_finalize_ownership_gate below for the fuller edit/
finalize lifecycle gate (audit log, DOCTOR_EDITED transition, 409-when-
final) that Phase 17 added as its own dedicated test.

Requires Ollama running locally with settings.OLLAMA_MODEL pulled (only
POST /generate-report needs it) -- the client fixture checks reachability
first and skips with a clear, actionable message if it isn't running.

test_ownership_exposed_via_api_and_real_dashboard_counts (Phase 15):
doctor_id has been persisted since Phase 13a, but no API response ever
returned it until this phase -- this test proves GET /reports/{id} and
GET /patients/{id}/history now actually carry it, that the new
GET /doctors/{id} resolves a real name (and 404s for a real nonexistent
id), and that GET /dashboard/stats returns real, distinct per-doctor
counts against a genuinely shared registry (same total_reports/
total_patients seen by both doctors, different my_reports/my_patients).
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

    # Phase 17 Step 9: the frozen doc's original Step 8 write-rejection
    # case, closed now that PATCH /reports/{id}/finalize exists -- doctor B
    # attempts to finalize doctor A's report: real 403 (see this file's
    # module docstring, "Scope note", for why this was deferred at Phase 13a).
    finalize_attempt = client.patch(f"/reports/{report_a_id}/finalize")
    assert finalize_attempt.status_code == 403, (
        f"doctor B's finalize attempt on doctor A's report should be forbidden: {finalize_attempt.text}"
    )

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


def test_ownership_exposed_via_api_and_real_dashboard_counts(client):
    """
    Phase 15 gate: doctor_id (persisted since Phase 13a) is now actually
    RETURNED by the API, not just sitting in the database -- and
    GET /doctors/{doctor_id} + GET /dashboard/stats, both new this phase,
    resolve correctly against real, independently-owned data.
    """
    doctor_a_id = _register(client, "Dr. Fifteen A")

    patient_response = client.post(
        "/patients",
        json={"name": "Phase 15 Ownership Patient", "date_of_birth": "1990-02-02", "gender": "F"},
    )
    assert patient_response.status_code == 200
    patient_id = patient_response.json()["id"]

    image_a, image_b = _sample_images(2)

    with open(image_a, "rb") as f:
        retrieve_response = client.post(
            "/retrieve",
            files={"file": (image_a.name, f, "image/png")},
            data={"top_k": "5", "min_similarity": "0.0", "patient_id": patient_id},
        )
    assert retrieve_response.status_code == 200
    session_a_id = retrieve_response.json()["session_id"]

    generate_response = client.post("/generate-report", json={"session_id": session_a_id, "language": "en"})
    assert generate_response.status_code == 200
    report_a_id = generate_response.json()["report_id"]

    # real dashboard stats for doctor A, BEFORE doctor B does anything
    stats_a_before = client.get("/dashboard/stats")
    assert stats_a_before.status_code == 200
    stats_a_before_body = stats_a_before.json()
    assert stats_a_before_body["my_reports"] >= 1
    assert stats_a_before_body["my_patients"] >= 1
    assert stats_a_before_body["total_reports"] >= stats_a_before_body["my_reports"]
    assert stats_a_before_body["total_patients"] >= stats_a_before_body["my_patients"]

    doctor_b_id = _register(client, "Dr. Fifteen B")

    # GET /reports/{id} now returns doctor_id -- the real point of Phase 15
    report_response = client.get(f"/reports/{report_a_id}")
    assert report_response.status_code == 200
    assert report_response.json()["doctor_id"] == doctor_a_id

    # GET /patients/{id}/history also carries doctor_id per entry
    history_response = client.get(f"/patients/{patient_id}/history")
    assert history_response.status_code == 200
    history_body = history_response.json()
    assert len(history_body) == 1
    assert history_body[0]["doctor_id"] == doctor_a_id

    # doctor B resolves doctor A's real name via the new GET /doctors/{id}
    doctor_a_lookup = client.get(f"/doctors/{doctor_a_id}")
    assert doctor_a_lookup.status_code == 200
    assert doctor_a_lookup.json() == {"id": doctor_a_id, "full_name": "Dr. Fifteen A"}

    # a real 404 for a well-formed but nonexistent doctor_id
    nonexistent_lookup = client.get(f"/doctors/{uuid.uuid4()}")
    assert nonexistent_lookup.status_code == 404

    # doctor B creates their own session on the SAME shared patient
    with open(image_b, "rb") as f:
        retrieve_response_b = client.post(
            "/retrieve",
            files={"file": (image_b.name, f, "image/png")},
            data={"top_k": "5", "min_similarity": "0.0", "patient_id": patient_id},
        )
    assert retrieve_response_b.status_code == 200

    # doctor B's real dashboard stats: their own 1 patient/session, but the
    # SAME total_reports/total_patients as doctor A saw (shared registry)
    stats_b = client.get("/dashboard/stats")
    assert stats_b.status_code == 200
    stats_b_body = stats_b.json()
    assert stats_b_body["my_reports"] == 0  # doctor B never called /generate-report
    assert stats_b_body["my_patients"] == 1  # doctor B's own new session on this patient
    assert stats_b_body["total_reports"] == stats_a_before_body["total_reports"]
    assert stats_b_body["total_patients"] == stats_a_before_body["total_patients"]


def test_phase17_edit_finalize_ownership_gate(client):
    """
    Phase 17 Step 8: the full edit/finalize ownership gate, extending this
    phase's own two-doctor fixture -- closes the write-rejection gap this
    file's own docstring flagged above ("no ownership-guarded write
    endpoint exists yet to exercise a 403 against... add a write-rejection
    case here once the first ownership-guarded mutation (e.g. report
    finalize) is built").

    Depends on the module-scoped `client` fixture purely for its Ollama-
    reachability check and real table setup/teardown -- the two doctors in
    THIS test get their own independent TestClient instances, NOT the
    single-shared-cookie-jar-switching trick the tests above use. Those
    tests do all of doctor A's work BEFORE doctor B is ever registered, so
    switching one jar from A's cookie to B's was fine. This sequence
    genuinely interleaves A and B's actions (B's forbidden edit attempt
    happens WHILE the report is still mid-lifecycle for A, and B reads
    again after A finalizes), so each doctor needs their own persistent,
    independent session alive at the same time.
    """
    client_a = TestClient(app, raise_server_exceptions=False)
    client_b = TestClient(app, raise_server_exceptions=False)

    doctor_a_id = _register(client_a, "Dr. Phase17 A")
    doctor_b_id = _register(client_b, "Dr. Phase17 B")
    assert doctor_a_id != doctor_b_id

    patient_response = client_a.post(
        "/patients",
        json={"name": "Phase17 Ownership Patient", "date_of_birth": "1975-03-03", "gender": "M"},
    )
    assert patient_response.status_code == 200, patient_response.text
    patient_id = patient_response.json()["id"]

    image_a = _sample_images(1)[0]

    with open(image_a, "rb") as f:
        retrieve_response = client_a.post(
            "/retrieve",
            files={"file": (image_a.name, f, "image/png")},
            data={"top_k": "5", "min_similarity": "0.0", "patient_id": patient_id},
        )
    assert retrieve_response.status_code == 200, retrieve_response.text
    session_id = retrieve_response.json()["session_id"]

    generate_response = client_a.post("/generate-report", json={"session_id": session_id, "language": "en"})
    assert generate_response.status_code == 200, generate_response.text
    report_id = generate_response.json()["report_id"]

    # doctor B attempts to edit doctor A's report: real 403
    forbidden_edit = client_b.patch(f"/reports/{report_id}", json={"findings": "hijacked"})
    assert forbidden_edit.status_code == 403, forbidden_edit.text

    # doctor A edits for real: DOCTOR_EDITED + first audit log row
    first_edit = client_a.patch(f"/reports/{report_id}", json={"findings": "Doctor A's first edit."})
    assert first_edit.status_code == 200, first_edit.text
    first_edit_body = first_edit.json()
    assert first_edit_body["status"] == "doctor_edited"
    assert first_edit_body["content"]["findings"] == "Doctor A's first edit."
    audit_after_first = first_edit_body["audit_log"]
    assert len(audit_after_first) == 1
    assert audit_after_first[0]["doctor_id"] == doctor_a_id
    assert audit_after_first[0]["action"] == "EDITED"

    # doctor A edits again: a SECOND, distinct audit log row -- proving no overwrite
    second_edit = client_a.patch(f"/reports/{report_id}", json={"findings": "Doctor A's second edit."})
    assert second_edit.status_code == 200, second_edit.text
    second_edit_body = second_edit.json()
    audit_after_second = second_edit_body["audit_log"]
    assert len(audit_after_second) == 2
    assert audit_after_second[0]["id"] != audit_after_second[1]["id"]
    assert second_edit_body["content"]["findings"] == "Doctor A's second edit."

    # doctor A finalizes: real 200, finalized_by/finalized_at set
    finalize_response = client_a.patch(f"/reports/{report_id}/finalize")
    assert finalize_response.status_code == 200, finalize_response.text
    finalize_body = finalize_response.json()
    assert finalize_body["status"] == "final"
    assert finalize_body["finalized_by"] == doctor_a_id
    assert finalize_body["finalized_at"] is not None

    # doctor A attempts a second edit post-finalize: real 409
    post_finalize_edit = client_a.patch(f"/reports/{report_id}", json={"findings": "too late"})
    assert post_finalize_edit.status_code == 409, post_finalize_edit.text

    # doctor B's read still works -- read is universal, unaffected by
    # ownership or finalize state
    doctor_b_read = client_b.get(f"/reports/{report_id}")
    assert doctor_b_read.status_code == 200, doctor_b_read.text
    assert doctor_b_read.json()["status"] == "final"

    # separately: finalize a fresh, unedited AI_DRAFT report directly --
    # no PATCH first. Valid from AI_DRAFT, not gated on having been edited.
    with open(image_a, "rb") as f:
        retrieve_response_2 = client_a.post(
            "/retrieve",
            files={"file": (image_a.name, f, "image/png")},
            data={"top_k": "5", "min_similarity": "0.0", "patient_id": patient_id},
        )
    assert retrieve_response_2.status_code == 200, retrieve_response_2.text
    session_id_2 = retrieve_response_2.json()["session_id"]

    generate_response_2 = client_a.post(
        "/generate-report", json={"session_id": session_id_2, "language": "en"}
    )
    assert generate_response_2.status_code == 200, generate_response_2.text
    report_id_2 = generate_response_2.json()["report_id"]

    direct_finalize = client_a.patch(f"/reports/{report_id_2}/finalize")
    assert direct_finalize.status_code == 200, direct_finalize.text
    assert direct_finalize.json()["status"] == "final"
