"""
Integration tests for the Step 11 FastAPI skeleton: GET /health and
POST /retrieve. Uses the REAL BiomedCLIP model and the REAL ChromaDB
collection via TestClient -- no mocks. This is the first true end-to-end
proof-of-concept for the whole backend built across Steps 1-11.
"""
from __future__ import annotations

import time
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as SASession

from app.database.base import Base, SessionLocal, engine
from app.main import app
from app.models.retrieval_session import RetrievalSession
from app.models.retrieved_evidence import RetrievedEvidence
from tests.integration.auth_helpers import register_test_doctor

REPO_ROOT = Path(__file__).resolve().parents[3]
MASKED_DIR = REPO_ROOT / "ml" / "datasets" / "masked"

_startup_elapsed: dict[str, float] = {}


def _pick_sample_image() -> Path:
    for p in sorted(MASKED_DIR.glob("*.png")):
        return p
    pytest.skip(f"no masked images found under {MASKED_DIR}")


def _row_counts(db) -> tuple[int, int]:
    return db.query(RetrievalSession).count(), db.query(RetrievedEvidence).count()


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(engine)
    start = time.perf_counter()
    with TestClient(app, raise_server_exceptions=False) as c:
        # lifespan startup (incl. real BiomedCLIP model load) has completed
        # by the time TestClient's context manager returns.
        _startup_elapsed["seconds"] = time.perf_counter() - start
        register_test_doctor(c)
        yield c
    Base.metadata.drop_all(engine)


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_retrieve_with_real_image_returns_full_contract(client):
    sample = _pick_sample_image()
    with open(sample, "rb") as f:
        response = client.post(
            "/retrieve",
            files={"file": (sample.name, f, "image/png")},
            data={"top_k": "5", "min_similarity": "0.0"},
        )
    assert response.status_code == 200
    body = response.json()

    for field in (
        "session_id", "retrieval_time_ms", "embedding_model", "embedding_version",
        "collection_name", "retrieved_cases", "voted_labels",
    ):
        assert field in body, f"missing frozen contract field: {field}"

    assert body["embedding_model"] == "biomedclip"
    assert body["embedding_version"] == "v1"
    assert body["collection_name"] == "iu_cxr_biomedclip_v1_train"

    assert len(body["retrieved_cases"]) > 0
    for case in body["retrieved_cases"]:
        for field in (
            "rank", "similarity", "study_uid", "primary_label", "label_set",
            "cluster_id", "findings", "impression", "image_path",
        ):
            assert field in case

    assert len(body["voted_labels"]) > 0
    for voted in body["voted_labels"]:
        for field in ("label", "vote_weight", "agreement"):
            assert field in voted


def test_db_rows_match_successful_response(client):
    sample = _pick_sample_image()
    with open(sample, "rb") as f:
        response = client.post("/retrieve", files={"file": (sample.name, f, "image/png")})
    assert response.status_code == 200
    body = response.json()
    session_id = uuid.UUID(body["session_id"])
    expected_evidence_count = len(body["retrieved_cases"])

    db = SessionLocal()
    try:
        sessions = db.query(RetrievalSession).filter(RetrievalSession.id == session_id).all()
        assert len(sessions) == 1
        evidence = db.query(RetrievedEvidence).filter(RetrievedEvidence.session_id == session_id).all()
        assert len(evidence) == expected_evidence_count
    finally:
        db.close()


def test_retrieve_with_corrupt_file_returns_422_and_no_db_rows(client):
    db = SessionLocal()
    try:
        before = _row_counts(db)
    finally:
        db.close()

    response = client.post(
        "/retrieve",
        files={"file": ("garbage.png", b"this is not a real image file", "image/png")},
    )
    assert response.status_code == 422

    db = SessionLocal()
    try:
        after = _row_counts(db)
    finally:
        db.close()
    assert after == before


def test_model_loaded_once_requests_much_faster_than_startup(client):
    sample = _pick_sample_image()

    with open(sample, "rb") as f:
        start_1 = time.perf_counter()
        r1 = client.post("/retrieve", files={"file": (sample.name, f, "image/png")})
        elapsed_1 = time.perf_counter() - start_1
    assert r1.status_code == 200

    with open(sample, "rb") as f:
        start_2 = time.perf_counter()
        r2 = client.post("/retrieve", files={"file": (sample.name, f, "image/png")})
        elapsed_2 = time.perf_counter() - start_2
    assert r2.status_code == 200

    startup = _startup_elapsed["seconds"]
    print(
        f"\n[model-reload check] lifespan startup (model load): {startup:.3f}s, "
        f"request 1: {elapsed_1:.3f}s, request 2: {elapsed_2:.3f}s"
    )
    # The model loads once, during lifespan startup, before any request is
    # made. If it were (incorrectly) reloaded per-request, request times
    # would be comparable to startup time, not a small fraction of it.
    assert elapsed_1 < startup * 0.5
    assert elapsed_2 < startup * 0.5


def test_transaction_atomicity_on_persistence_failure(client, monkeypatch):
    db = SessionLocal()
    try:
        before = _row_counts(db)
    finally:
        db.close()

    def failing_commit(self):
        # Real proof, not a trivial short-circuit: actually flush pending
        # objects (sends the INSERT statements within the still-open
        # transaction) before failing, simulating a failure between "rows
        # sent to the DB" and "transaction finalized" -- e.g. a constraint
        # violation or dropped connection at COMMIT time.
        self.flush()
        raise RuntimeError("simulated persistence failure after flush, before commit")

    monkeypatch.setattr(SASession, "commit", failing_commit)

    sample = _pick_sample_image()
    with open(sample, "rb") as f:
        response = client.post("/retrieve", files={"file": (sample.name, f, "image/png")})

    assert response.status_code == 500

    # monkeypatch reverts automatically after this test; use a fresh
    # session/connection to confirm nothing was actually persisted.
    db = SessionLocal()
    try:
        after = _row_counts(db)
    finally:
        db.close()

    assert after == before, (
        f"orphaned rows leaked despite commit failure: before={before}, after={after}"
    )