"""
Integration test: the full real Phase 11 chain via FastAPI's TestClient.
Real POST /patients -> real POST /retrieve (with the new Phase 11
patient_id form field) -> real POST /generate-report, twice (a "previous"
visit and a "current" visit for the SAME patient) -> real POST /comparisons
omitting compare_against_report_id, exercising the default-to-most-recent-
prior resolution path for real, not just against fakes. Every real
collaborator: real DB, real ChromaDB retrieval, real LabelVotingService,
real ContextBuilder, real LLMOrchestrator (three real Ollama calls -- two
report generations, one comparison narrative), real DeterministicComparator,
real PromptBuilder.build_comparison_prompt, real persistence. No
fakes/mocks anywhere in this path.

Non-determinism discipline, unchanged from every real-LLM integration test
since Phase 7: the LLM narrative is asserted on structurally only (a
non-empty string), never on exact wording. The DETERMINISTIC facts,
however, are fully checkable and ARE checked -- independently recomputed
in this test from the two real reports' actual persisted text via the
same taxonomy_matching helpers DeterministicComparator itself uses, then
compared against the API response. This proves the deterministic layer is
correct against real, non-deterministic LLM output, not just against
hand-built fixtures.

Requires Ollama running locally with settings.OLLAMA_MODEL pulled (same
requirement as every prior real-LLM integration test) -- the client
fixture checks reachability first and skips with a clear, actionable
message if it isn't running.
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import date
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.database.base import Base, SessionLocal, engine
from app.main import app
from app.models.comparison import ComparisonRecord
from app.services.taxonomy_matching import extract_mentioned_classes, load_taxonomy_classes

REPO_ROOT = Path(__file__).resolve().parents[3]
MASKED_DIR = REPO_ROOT / "ml" / "datasets" / "masked"


def _sample_images(n: int) -> list[Path]:
    images = sorted(MASKED_DIR.glob("*.png"))
    if len(images) < n * 5:
        pytest.skip(f"fewer than {n * 5} masked images found under {MASKED_DIR}")
    # Spread selections out (rather than taking the first n contiguous
    # files) -- observed during Step 10 development that one specific real
    # image ("1001_IM-0004-1001.dcm.png", the second file alphabetically)
    # repeatedly drove the real LLM (llama3:8b via Ollama) to exhaust its
    # existing Phase 7/8 content-retry budget with malformed JSON on that
    # image's real findings text, a pre-existing Phase 7/8 LLM-reliability
    # limitation unrelated to anything built in this phase. Not worked
    # around by retrying silently -- documented in the Phase 11 dev log's
    # limitations section instead.
    return [images[i] for i in range(0, n * 5, 5)]


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
            f"ensure '{settings.OLLAMA_MODEL}' is pulled (`ollama pull {settings.OLLAMA_MODEL}`) "
            f"before running this integration test."
        )
    Base.metadata.create_all(engine)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    Base.metadata.drop_all(engine)


def _create_real_patient(client) -> str:
    response = client.post(
        "/patients",
        json={"name": "Integration Test Patient", "date_of_birth": "1970-01-01", "gender": "F"},
    )
    assert response.status_code == 200, f"failed to create a real patient: {response.text}"
    return response.json()["id"]


def _real_visit(client, image_path: Path, patient_id: str) -> dict:
    """Real POST /retrieve (linked to patient_id) -> real POST /generate-report.
    Returns the /generate-report response body."""
    with open(image_path, "rb") as f:
        retrieve_response = client.post(
            "/retrieve",
            files={"file": (image_path.name, f, "image/png")},
            data={"top_k": "5", "min_similarity": "0.0", "patient_id": patient_id},
        )
    assert retrieve_response.status_code == 200, f"failed real /retrieve: {retrieve_response.text}"
    session_id = retrieve_response.json()["session_id"]

    generate_response = client.post("/generate-report", json={"session_id": session_id, "language": "en"})
    assert generate_response.status_code == 200, f"failed real /generate-report: {generate_response.text}"
    return generate_response.json()


def test_comparison_full_real_chain(client):
    patient_id = _create_real_patient(client)
    image_a, image_b = _sample_images(2)

    start = time.perf_counter()
    previous = _real_visit(client, image_a, patient_id)
    current = _real_visit(client, image_b, patient_id)
    elapsed_visits = time.perf_counter() - start

    print(f"\nBoth real visits (2x /retrieve + 2x /generate-report) took: {elapsed_visits:.2f}s")

    previous_report_id = previous["report_id"]
    current_report_id = current["report_id"]
    previous_content = previous["formatted_report"]["content"]
    current_content = current["formatted_report"]["content"]
    previous_report_date = previous["formatted_report"]["report_date"]
    current_report_date = current["formatted_report"]["report_date"]

    # default-to-most-recent-prior path: compare_against_report_id deliberately omitted
    start = time.perf_counter()
    response = client.post(
        "/comparisons",
        json={"patient_id": patient_id, "current_report_id": current_report_id},
    )
    elapsed_comparison = time.perf_counter() - start

    assert response.status_code == 200, f"unexpected status {response.status_code}: {response.text}"
    body = response.json()

    print(f"/comparisons real wall-clock time: {elapsed_comparison:.2f}s")
    print("REAL /comparisons response JSON:")
    print(json.dumps(body, indent=2, ensure_ascii=False))

    # frozen response contract, all fields present
    for field in ("id", "patient_id", "previous_report_id", "current_report_id", "facts", "narrative", "created_at"):
        assert field in body, f"missing frozen contract field: {field}"

    assert body["patient_id"] == patient_id
    assert body["previous_report_id"] == previous_report_id
    assert body["current_report_id"] == current_report_id

    facts = body["facts"]
    for field in (
        "previous_report_id", "current_report_id",
        "resolved_findings", "persistent_findings", "new_findings", "days_between_studies",
    ):
        assert field in facts

    # --- independently recompute the expected deterministic facts from the
    # ACTUAL real report text, using the same taxonomy_matching helpers
    # DeterministicComparator itself uses, rather than hardcoding expected
    # findings (which would be meaningless against real, non-deterministic
    # LLM output) ---
    taxonomy_classes = load_taxonomy_classes()
    previous_text = f"{previous_content['findings']} {previous_content['impression']}".lower()
    current_text = f"{current_content['findings']} {current_content['impression']}".lower()
    previous_classes = extract_mentioned_classes(previous_text, taxonomy_classes)
    current_classes = extract_mentioned_classes(current_text, taxonomy_classes)

    expected_resolved = previous_classes - current_classes
    expected_persistent = previous_classes & current_classes
    expected_new = current_classes - previous_classes
    expected_days = (date.fromisoformat(current_report_date) - date.fromisoformat(previous_report_date)).days

    assert set(facts["resolved_findings"]) == expected_resolved
    assert set(facts["persistent_findings"]) == expected_persistent
    assert set(facts["new_findings"]) == expected_new
    assert facts["days_between_studies"] == expected_days

    # narrative: structural check ONLY, never exact wording (non-determinism
    # discipline, same as every real-LLM integration test since Phase 7)
    assert isinstance(body["narrative"], str)
    assert len(body["narrative"].strip()) > 0

    # a real ComparisonRecord row was persisted, matching the response exactly
    db = SessionLocal()
    try:
        comparison_id = uuid.UUID(body["id"])
        record = db.query(ComparisonRecord).filter(ComparisonRecord.id == comparison_id).one()
        assert str(record.patient_id) == patient_id
        assert str(record.previous_report_id) == previous_report_id
        assert str(record.current_report_id) == current_report_id
        assert record.deterministic_facts["resolved_findings"] == facts["resolved_findings"]
        assert record.deterministic_facts["persistent_findings"] == facts["persistent_findings"]
        assert record.deterministic_facts["new_findings"] == facts["new_findings"]
        assert record.deterministic_facts["days_between_studies"] == facts["days_between_studies"]
        assert record.llm_narrative == body["narrative"]
    finally:
        db.close()

    print("\n--- REAL PERSISTED COMPARISON FACTS ---")
    print(json.dumps(facts, indent=2, ensure_ascii=False))
    print("\n--- REAL PERSISTED LLM NARRATIVE ---")
    print(body["narrative"])
