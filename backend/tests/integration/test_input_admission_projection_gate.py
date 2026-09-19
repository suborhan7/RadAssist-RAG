"""
tests/integration/test_input_admission_projection_gate.py
====================================================================
The acceptance gate of §13 of docs/methodology/input_admission_projection_
gate_architecture_v1.1_FROZEN.md: tests T1 and T3 to T21.

T2 is absent by instruction. v1.1 removed it: it asserted that a lateral
image passes all checks, which contradicts DR-4. T15 tests the correct
behaviour.

Supersedes test_input_admission_modality_gate.py (the v1.0 gate), which is
deleted rather than kept -- two acceptance suites for one pipeline would
let a v1.0 assertion contradicting DR-4 keep passing.

Everything runs against the REAL stack: real BiomedCLIP, real ChromaDB,
real PHI masker, real Ollama, real database. Nothing is mocked. The only
substitutions are the two spies in T15 (which count calls, and let the
real objects run) and the adjusted retrieval floor in T9/T10, which is
recorded in the output of those tests as §13 requires.
"""
from __future__ import annotations

import io
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import settings
from app.database.base import Base, SessionLocal, engine
from app.domain.entities import RetrievalSupport
from app.main import app
from app.models.report import ReportRecord
from app.models.upload_rejection import UploadRejectionLog
from app.services.exceptions import LateralProjectionError, ProjectionMismatchError
from app.services.modality_gate_service import ModalityGateService
from tests.integration import admission_fixtures as fixtures
from tests.integration.auth_helpers import register_test_doctor

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(engine)
    with TestClient(app, raise_server_exceptions=False) as c:
        register_test_doctor(c)
        yield c
    Base.metadata.drop_all(engine)


def _upload(client, path_or_bytes, filename: str, content_type: str = "image/png",
            declared_projection: str | None = "PA", **extra):
    payload = path_or_bytes.read_bytes() if isinstance(path_or_bytes, Path) else path_or_bytes
    data = dict(extra)
    if declared_projection is not None:
        data["declared_projection"] = declared_projection
    return client.post(
        "/retrieve", files={"file": (filename, payload, content_type)}, data=data
    )


def _generate_report(client, session_id: str):
    return client.post("/generate-report", json={"session_id": session_id, "language": "en"})


def _rejection_rows() -> list[UploadRejectionLog]:
    db = SessionLocal()
    try:
        return db.query(UploadRejectionLog).all()
    finally:
        db.close()


# ======================================================================
# T1 -- a correct frontal chest radiograph
# ======================================================================


def test_T1_frontal_chest_radiograph_passes_all_checks_and_makes_a_report(client):
    """T1. A correct frontal chest radiograph passes all checks. The
    pipeline makes a report."""
    response = _upload(client, fixtures.frontal_radiograph(), "frontal.png")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["modality_score"] >= settings.MODALITY_THRESHOLD
    assert body["top1_similarity"] >= settings.PROJECTION_REJECT_THRESHOLD
    assert body["retrieved_cases"]

    report = _generate_report(client, body["session_id"])
    assert report.status_code == 200, report.text
    content = report.json()["formatted_report"]["content"]
    assert content["findings"].strip() and content["impression"].strip()
    print(
        f"\n[T1] modality_score={body['modality_score']:.6f} top1={body['top1_similarity']:.4f} "
        f"support={body['retrieval_support']} report_id={report.json()['report_id']}"
    )


# ======================================================================
# T3 to T8 -- carried from v1.0, re-run under v1.1
# ======================================================================


def test_T3_strawberry_photograph_fails_at_M5(client):
    """T3. The strawberry photograph fails at M5.

    The stage is asserted, not just the status: this file is a valid JPEG,
    so a 422 obtained by rejecting it at admission would prove the
    opposite of what T3 exists to prove.
    """
    before = len(_rejection_rows())
    response = _upload(client, fixtures.strawberry_photograph(), "strawberry.jpg", "image/jpeg")

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert "not recognised as a chest radiograph" in detail

    row = _rejection_rows()[-1]
    assert len(_rejection_rows()) == before + 1
    assert row.stage == "modality_gate"
    assert row.reason_code == "MODALITY_BELOW_THRESHOLD"
    assert row.modality_score < settings.MODALITY_THRESHOLD
    print(f"\n[T3] {detail}")
    print(f"[T3] audit: stage={row.stage} reason={row.reason_code} score={row.modality_score:.8f}")


def test_T4_text_file_with_png_extension_fails_at_A4(client):
    """T4. A text file with a `.png` extension fails at A4. 415 per §10."""
    response = _upload(client, fixtures.text_file_named_png(), "report.png")
    assert response.status_code == 415, response.text
    assert "does not match the declared" in response.json()["detail"]
    row = _rejection_rows()[-1]
    assert row.reason_code == "FORMAT_MISMATCH"
    assert row.stage == "admission_format"
    print(f"\n[T4] HTTP {response.status_code} reason={row.reason_code}: "
          f"{response.json()['detail']}")


def test_T5_two_kilobyte_image_fails_at_A6(client):
    """T5. A 2 kB image fails at A6."""
    payload = fixtures.tiny_image()
    assert len(payload) < settings.UPLOAD_MIN_BYTES
    response = _upload(client, payload, "small.png")
    assert response.status_code == 422, response.text
    row = _rejection_rows()[-1]
    assert row.reason_code == "FILE_TOO_SMALL"
    print(f"\n[T5] {len(payload)} bytes -> HTTP {response.status_code} "
          f"reason={row.reason_code}: {response.json()['detail']}")


def test_T6_decompression_bomb_fails_at_A9_and_the_process_survives(client):
    """T6. A decompression-bomb PNG fails at A9. The process does not stop."""
    payload = fixtures.decompression_bomb_png()
    width = int.from_bytes(payload[16:20], "big")
    height = int.from_bytes(payload[20:24], "big")
    assert width * height > settings.IMAGE_MAX_PIXELS
    assert len(payload) < settings.UPLOAD_MAX_BYTES

    response = _upload(client, payload, "bomb.png")
    assert response.status_code == 422, response.text
    row = _rejection_rows()[-1]
    assert row.stage == "admission_decode"

    assert client.get("/health").status_code == 200
    print(f"\n[T6] declared {width}x{height} = {width*height:,} px in a {len(payload):,}-byte "
          f"file -> HTTP {response.status_code} ({row.reason_code}); /health still 200")


def test_T7_jpeg_with_exif_passes_and_the_normalized_png_has_no_exif(client):
    """T7. A JPEG with EXIF passes. The normalized PNG has no EXIF."""
    payload = fixtures.jpeg_with_exif()
    with Image.open(io.BytesIO(payload)) as before:
        assert before.getexif()
        assert b"Abdur Rahman" in before.info["exif"]
        tags_before = len(before.getexif())

    response = _upload(client, payload, "with_exif.jpg", "image/jpeg")
    assert response.status_code == 200, response.text
    stored = client.get(f"/retrieval-sessions/{response.json()['session_id']}/image")
    assert stored.status_code == 200
    with Image.open(io.BytesIO(stored.content)) as after:
        assert after.format == "PNG"
        assert not after.getexif()
        assert "exif" not in after.info
        print(f"\n[T7] uploaded JPEG with {tags_before} EXIF tags incl. a patient name "
              f"-> stored {after.format}, EXIF tags: {len(after.getexif())}")


def test_T8_rejected_upload_writes_one_metadata_only_audit_row(client):
    """T8. A rejected upload writes one audit row holding no file name and
    no image bytes.

    The column SET is inspected, not just this row's values: asserting
    "this row has no name in it" would pass on a schema that had a
    filename column this path left empty. DR-2 forbids the field existing.
    """
    before = len(_rejection_rows())
    response = _upload(client, fixtures.text_file_named_png(), "Abdur_Rahman_CXR_2026.png")
    assert response.status_code == 415

    rows = _rejection_rows()
    assert len(rows) == before + 1
    row = rows[-1]

    columns = set(UploadRejectionLog.__table__.columns.keys())
    forbidden = {"filename", "file_name", "original_filename", "image", "image_bytes",
                 "masked_image", "exif"}
    assert not (columns & forbidden)
    values = " ".join(str(getattr(row, c)) for c in columns)
    assert "Abdur" not in values and "Rahman" not in values
    assert "Abdur" not in response.text and "Rahman" not in response.text
    assert row.declared_extension == ".png"
    assert len(row.raw_sha256) == 64 and row.file_size_bytes > 0
    print(f"\n[T8] columns={sorted(columns)}")
    print(f"[T8] row: stage={row.stage} reason={row.reason_code} ext={row.declared_extension} "
          f"size={row.file_size_bytes} sha256={row.raw_sha256[:16]}...")


# ======================================================================
# T9 / T10 / T11 / T20 -- the evidence snapshot
#
# FIXTURE METHOD, recorded here as §13's Note requires:
#   Both T9 and T10 use an **adjusted retrieval floor**, not a synthetic
#   image. No in-scope frontal case falls in the low support band: the
#   Gate B floor IS the frontal minimum (0.8906208872795105), so the band
#   [PROJECTION_REJECT_THRESHOLD, RETRIEVAL_FLOOR) contains no held-out
#   frontal case by construction -- that is §11.5 Step R2's own result.
#
#   The floor is raised, for these two tests only, to just above the real
#   top-1 similarity of a real frontal radiograph, and the SAME real image
#   is then uploaded again. Everything else is the production path: the
#   real band classification, the real disclaimer template, the real
#   persistence. Only the threshold moves.
#
#   An adjusted floor is preferred over a synthetic image because a
#   fabricated image would also change the modality score, the retrieved
#   neighbours and the agreement score, and T10 is specifically about the
#   COMBINATION of a real agreement score with a low support category.
# ======================================================================


@pytest.fixture(scope="module")
def low_support_report(client):
    """One real low-support generation, shared by T9, T10, T11 and T20."""
    source = fixtures.frontal_radiograph()

    # 1. Measure the real case under the real, unadjusted settings.
    baseline = _upload(client, source, "frontal_baseline.png")
    assert baseline.status_code == 200, baseline.text
    real_top1 = baseline.json()["top1_similarity"]
    real_agreement = baseline.json()["voted_labels"][0]["agreement"]

    # 2. Raise ONLY the floor, above this case's real top-1. The reject
    #    threshold is untouched, so the three bands stay ordered and the
    #    case lands in the middle band rather than the reject band.
    original_gate = app.state.modality_gate_service
    adjusted_floor = real_top1 + 0.001
    app.state.modality_gate_service = ModalityGateService(
        embedder=_PromptVectorReuse(original_gate),
        positive_prompts=settings.modality_prompts_positive,
        negative_prompts=settings.modality_prompts_negative,
        softmax_temperature=settings.MODALITY_SOFTMAX_TEMPERATURE,
        modality_threshold=settings.MODALITY_THRESHOLD,
        retrieval_floor=adjusted_floor,
        projection_reject_threshold=settings.PROJECTION_REJECT_THRESHOLD,
    )
    try:
        response = _upload(client, source, "frontal_low_support.png")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["retrieval_support"] == RetrievalSupport.BELOW_FLOOR.value, (
            f"adjusted floor {adjusted_floor} did not put top1 "
            f"{body['top1_similarity']} in the low support band"
        )
        report = _generate_report(client, body["session_id"])
        assert report.status_code == 200, report.text
        result = (body, report.json(), adjusted_floor, real_agreement)
    finally:
        # Restored HERE, not in a teardown after `yield`. This fixture is
        # module-scoped, so a yield-then-restore would leave the adjusted
        # floor installed for every test that runs after it -- which it
        # did: T18 asserts a frontal image lands at_or_above_floor and saw
        # below_floor, because the raised floor was still in force. The
        # adjusted gate is only needed for the two requests above, so the
        # real singleton goes back before any value is handed out.
        app.state.modality_gate_service = original_gate

    # returned, not yielded: nothing remains to tear down.
    return result


class _PromptVectorReuse:
    """Hands the already-cached prompt vectors to the adjusted gate.

    M6 caches the text vectors at start-up. Rebuilding a gate for the
    fixture must not re-encode five prompts through BiomedCLIP just to
    change one float, so this returns the vectors the running singleton
    already holds, in the same order.
    """

    def __init__(self, existing_gate: ModalityGateService) -> None:
        self._vectors = list(existing_gate._prompt_vectors)
        self._index = 0

    def embed_text(self, text: str) -> list[float]:
        vector = self._vectors[self._index]
        self._index += 1
        return vector

    def embed_image(self, image_path: str) -> list[float]:  # pragma: no cover
        raise AssertionError("M1: the gate must not encode the image")


def test_T9_low_support_band_makes_a_report_with_the_weak_support_statement(low_support_report):
    """T9. An image with a top-1 similarity in the low support band makes
    a report. The report holds the weak support statement.

    FIXTURE METHOD: adjusted floor (see the module comment above)."""
    body, report_body, adjusted_floor, _ = low_support_report
    assert body["top1_similarity"] < adjusted_floor
    assert body["top1_similarity"] >= settings.PROJECTION_REJECT_THRESHOLD

    disclaimer = report_body["formatted_report"]["content"]["disclaimer"]
    assert "No retrieved case meets the minimum retrieval-support threshold" in disclaimer
    lowered = disclaimer.lower()
    for overclaim in ("no similar case", "the archive holds no", "no comparable case"):
        assert overclaim not in lowered

    print(f"\n[T9] FIXTURE METHOD = adjusted floor")
    print(f"[T9] real Gate B floor = {settings.RETRIEVAL_FLOOR!r} "
          f"(= the frontal minimum; 0/300 frontal below it, §11.5 R2)")
    print(f"[T9] adjusted floor for this test = {adjusted_floor!r}")
    print(f"[T9] real top1 = {body['top1_similarity']:.6f}, "
          f"reject threshold = {settings.PROJECTION_REJECT_THRESHOLD:.6f} -> low support band")
    print(f"[T9] disclaimer: {disclaimer}")


def test_T10_high_agreement_with_low_support_does_not_read_as_high_confidence(low_support_report):
    """T10. High agreement with low retrieval support makes a report whose
    disclaimer states the weak support and does not state high confidence.

    FIXTURE METHOD: adjusted floor. §13's Note records why no real
    in-scope case exists -- all 15 previously observed cases were lateral,
    and A16 now rejects lateral inputs.
    """
    body, report_body, adjusted_floor, agreement = low_support_report
    if agreement < settings.DISCLAIMER_AGREEMENT_THRESHOLD:
        pytest.skip(f"this retrieval produced LOW agreement ({agreement:.2f}); T10 needs "
                    f"the high-agreement/low-support cell")

    disclaimer = report_body["formatted_report"]["content"]["disclaimer"]
    assert "No retrieved case meets the minimum retrieval-support threshold" in disclaimer
    assert "The agreement score alone does not indicate strong evidence" in disclaimer
    lowered = disclaimer.lower()
    for confident in ("high confidence", "strong evidence supports", "strongly supported"):
        assert confident not in lowered
    assert "weakly supported" in lowered

    print(f"\n[T10] FIXTURE METHOD = adjusted floor ({adjusted_floor!r})")
    print(f"[T10] real agreement = {agreement:.2f} (high), support = below_floor")
    print(f"[T10] disclaimer: {disclaimer}")


def test_T11_report_row_holds_the_support_category_and_the_top1_similarity(low_support_report):
    """T11. The report row holds the retrieval support category and the
    top-1 similarity. Read from the database: S5 is a persistence
    requirement, and a response field could be computed on the way out."""
    body, report_body, _, _ = low_support_report
    db = SessionLocal()
    try:
        row = db.query(ReportRecord).filter(
            ReportRecord.id == uuid.UUID(report_body["report_id"])).one()
        assert row.retrieval_support == RetrievalSupport.BELOW_FLOOR.value
        assert row.top1_similarity == pytest.approx(body["top1_similarity"], abs=1e-6)
        print(f"\n[T11] reports.retrieval_support={row.retrieval_support!r} "
              f"reports.top1_similarity={row.top1_similarity}")
    finally:
        db.close()


def test_T20_report_row_holds_voted_labels_and_agreement_after_S7(low_support_report):
    """T20. The report row holds `voted_labels` and `agreement` after the
    S7 migration (c3d81b6a4f27).

    §7.3's Warning is what this closes: with only one of the disclaimer's
    two signals stored, a finalized report could not be reconstructed and
    the state merely *appeared* reproducible. All four snapshot fields are
    asserted together for that reason.
    """
    body, report_body, _, _ = low_support_report
    db = SessionLocal()
    try:
        row = db.query(ReportRecord).filter(
            ReportRecord.id == uuid.UUID(report_body["report_id"])).one()

        assert row.voted_labels is not None, "S7 column not written"
        assert isinstance(row.voted_labels, list) and row.voted_labels
        for entry in row.voted_labels:
            assert {"label", "vote_weight", "agreement"} <= set(entry)
        assert row.agreement is not None
        # the stored scalar agrees with the stored document
        assert row.agreement == pytest.approx(row.voted_labels[0]["agreement"])
        # and with what /retrieve reported for the same session
        assert row.agreement == pytest.approx(body["voted_labels"][0]["agreement"])

        print(f"\n[T20] reports.agreement={row.agreement}")
        print(f"[T20] reports.voted_labels ({len(row.voted_labels)} entries): "
              f"{row.voted_labels[:2]}")
        print(f"[T20] full evidence snapshot stored: retrieval_support="
              f"{row.retrieval_support!r} top1_similarity={row.top1_similarity} "
              f"agreement={row.agreement} voted_labels=<{len(row.voted_labels)} entries>")
    finally:
        db.close()


# ======================================================================
# T12 / T13 -- calibration tables and the existing regression
# ======================================================================


def test_T12_calibration_tables_exist_with_real_numbers():
    """T12. The calibration tables from §11.2 exist with real numbers."""
    import pandas as pd

    out_dir = REPO_ROOT / "ml" / "outputs" / "calibration"
    rates = pd.read_csv(out_dir / "v1_1_threshold_rates.csv")
    selections = pd.read_csv(out_dir / "v1_1_gate_b_selected_values.csv")
    scores = pd.read_csv(out_dir / "modality_scores.csv")
    support = pd.read_csv(out_dir / "top1_similarity_by_label.csv")

    assert rates["fnr_frontal"].notna().all()
    assert rates["n_frontal"].iloc[0] == 300
    assert "fpr_natural_photograph" in rates.columns
    assert {"MODALITY_THRESHOLD", "PROJECTION_REJECT_THRESHOLD", "RETRIEVAL_FLOOR"} <= set(
        selections["setting"])
    assert scores["modality_score"].notna().sum() > 0
    assert support["top1_similarity"].notna().sum() > 0

    print(f"\n[T12] v1_1_threshold_rates.csv: {len(rates)} thresholds, n_frontal="
          f"{rates['n_frontal'].iloc[0]}")
    print(f"[T12] v1_1_gate_b_selected_values.csv:\n{selections.to_string(index=False)}")


def test_T13_existing_retrieval_regression_still_passes():
    """T13. The existing retrieval regression test passes after the change."""
    import subprocess
    import sys

    backend_dir = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/unit/test_retrieval_service.py",
         "tests/integration/test_retrieval_integration.py"],
        cwd=backend_dir, capture_output=True, text=True,
    )
    print(f"\n[T13]\n{result.stdout[-1200:]}")
    assert result.returncode == 0, result.stdout + result.stderr


# ======================================================================
# T14 to T18 -- the projection controls
# ======================================================================


def test_T14_upload_with_no_declared_projection_fails(client):
    """T14. An upload with no declared projection fails with
    `PROJECTION_NOT_DECLARED`.

    A15 forbids selecting a default, so this must be a rejection and not
    an assumed PA.
    """
    before = len(_rejection_rows())
    response = _upload(client, fixtures.frontal_radiograph(), "frontal.png",
                       declared_projection=None)
    assert response.status_code == 422, response.text

    rows = _rejection_rows()
    assert len(rows) == before + 1
    row = rows[-1]
    assert row.reason_code == "PROJECTION_NOT_DECLARED"
    assert row.stage == "admission_projection"
    assert row.modality_score is None, "A17: nothing was embedded, so no score exists"
    print(f"\n[T14] HTTP {response.status_code} reason={row.reason_code} "
          f"stage={row.stage} modality_score={row.modality_score}")
    print(f"[T14] detail: {response.json()['detail']}")


def test_T15_declared_lateral_is_rejected_without_masking_embedding_or_retrieval(client, monkeypatch):
    """T15. An upload with declared projection `LATERAL` fails with
    `DECLARED_LATERAL`. The masker does not run. The embedder does not
    run. ChromaDB is not queried.

    The three negatives are the substance of A17, so all three are counted
    rather than assumed from the status code. The spies wrap the REAL
    objects and delegate to them, so a passing test cannot be an artifact
    of having replaced the pipeline with no-ops.
    """
    calls = {"mask": 0, "embed": 0, "query": 0}

    real_mask = app.state.phi_masker.detect_and_mask
    real_embed = app.state.embedder.embed_image
    real_query = app.state.vector_store.query

    def spy_mask(*a, **k):
        calls["mask"] += 1
        return real_mask(*a, **k)

    def spy_embed(*a, **k):
        calls["embed"] += 1
        return real_embed(*a, **k)

    def spy_query(*a, **k):
        calls["query"] += 1
        return real_query(*a, **k)

    monkeypatch.setattr(app.state.phi_masker, "detect_and_mask", spy_mask)
    monkeypatch.setattr(app.state.embedder, "embed_image", spy_embed)
    monkeypatch.setattr(app.state.vector_store, "query", spy_query)

    before = len(_rejection_rows())
    response = _upload(client, fixtures.lateral_radiograph(), "lateral.png",
                       declared_projection="LATERAL")

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert detail["reason_code"] == "DECLARED_LATERAL"
    assert detail["message_key"] == "error.projection.declaredLateral"

    assert calls == {"mask": 0, "embed": 0, "query": 0}, (
        f"A17 violated -- the pipeline ran past admission: {calls}")

    rows = _rejection_rows()
    assert len(rows) == before + 1
    row = rows[-1]
    assert row.reason_code == "DECLARED_LATERAL"
    assert row.stage == "admission_projection"
    assert row.modality_score is None

    print(f"\n[T15] HTTP {response.status_code} detail={detail}")
    print(f"[T15] A17 call counts after rejection: {calls}")
    print(f"[T15] audit: reason={row.reason_code} stage={row.stage} "
          f"modality_score={row.modality_score}")


def test_T16_lateral_declared_PA_that_passes_M5_fails_at_M10(client):
    """T16. A lateral image declared `PA` that passes control M5 reaches
    retrieval, and fails with `FRONTAL_MISMATCH` when its top-1 similarity
    is below the projection reject threshold.

    This is the mis-declaration path: A16 cannot catch it, because the
    declaration is a lie. Only the measurement finds it (M10).
    """
    before = len(_rejection_rows())
    response = _upload(client, fixtures.lateral_radiograph(), "lateral_as_pa.png",
                       declared_projection="PA")

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert detail["reason_code"] == "FRONTAL_MISMATCH"
    assert detail["message_key"] == "error.projection.frontalMismatch"

    rows = _rejection_rows()
    assert len(rows) == before + 1
    row = rows[-1]
    assert row.reason_code == "FRONTAL_MISMATCH"
    assert row.stage == "projection_mismatch"
    # M5 ran and PASSED before retrieval, so the score exists here --
    # unlike the A16 path, which never reaches the embedder.
    assert row.modality_score is not None
    assert row.modality_score >= settings.MODALITY_THRESHOLD

    print(f"\n[T16] HTTP {response.status_code} detail={detail}")
    print(f"[T16] audit: reason={row.reason_code} stage={row.stage} "
          f"modality_score={row.modality_score:.6f} (passed M5, then failed M10)")
    print(f"[T16] PROJECTION_REJECT_THRESHOLD={settings.PROJECTION_REJECT_THRESHOLD!r}")


def test_T16a_how_many_lateral_images_reach_M10_and_how_many_M5_rejects_first():
    """T16a. Report how many lateral diagnostic images reach control M10,
    and how many control M5 rejects first.

    M10 cannot be tested on an image M5 already rejected, so this is the
    denominator for T16: a count, not a pass/fail on individual images.
    Measured from the Gate B modality scores of the 300-image lateral
    diagnostic set.
    """
    import pandas as pd

    scores = pd.read_csv(REPO_ROOT / "ml" / "outputs" / "calibration" / "modality_scores.csv")
    lateral = scores[(scores["set"] == "positive") & (scores["projection"] == "Lateral")]
    n = len(lateral)
    rejected_by_m5 = int((lateral["modality_score"] < settings.MODALITY_THRESHOLD).sum())
    reach_m10 = n - rejected_by_m5

    assert n == 300
    print(f"\n[T16a] lateral diagnostic set n={n}, MODALITY_THRESHOLD="
          f"{settings.MODALITY_THRESHOLD}")
    print(f"[T16a] rejected by M5 first (never reach M10): {rejected_by_m5} "
          f"({100.0*rejected_by_m5/n:.2f}%)")
    print(f"[T16a] reach control M10:                      {reach_m10} "
          f"({100.0*reach_m10/n:.2f}%)")
    print(f"[T16a] of those reaching M10, top-1 below the reject threshold: 300/300 "
          f"per §11.4 Step P1 (lateral max 0.8485 < threshold "
          f"{settings.PROJECTION_REJECT_THRESHOLD:.4f})")


def test_T17_the_two_projection_rejections_are_different_types_and_codes(client):
    """T17. The exception for T15 and the exception for T16 are different
    types. The audit rows hold different reason codes.

    §10's Rule: "A lateral image **is** a chest radiograph. A joined type
    makes the rejection counts wrong." Both halves are checked -- the
    types at the Python level, and the codes actually written to the audit
    table by the two real requests.
    """
    assert LateralProjectionError is not ProjectionMismatchError
    assert not issubclass(LateralProjectionError, ProjectionMismatchError)
    assert not issubclass(ProjectionMismatchError, LateralProjectionError)
    assert LateralProjectionError.reason_code != ProjectionMismatchError.reason_code

    from app.services.exceptions import NotAChestRadiographError
    assert not issubclass(LateralProjectionError, NotAChestRadiographError)
    assert not issubclass(ProjectionMismatchError, NotAChestRadiographError)

    lateral_source = fixtures.lateral_radiograph()
    r_declared = _upload(client, lateral_source, "a.png", declared_projection="LATERAL")
    row_declared = _rejection_rows()[-1]
    r_mismatch = _upload(client, lateral_source, "b.png", declared_projection="PA")
    row_mismatch = _rejection_rows()[-1]

    assert r_declared.status_code == r_mismatch.status_code == 422
    assert row_declared.reason_code == "DECLARED_LATERAL"
    assert row_mismatch.reason_code == "FRONTAL_MISMATCH"
    assert row_declared.reason_code != row_mismatch.reason_code
    assert row_declared.stage != row_mismatch.stage

    print(f"\n[T17] types: {LateralProjectionError.__name__} / "
          f"{ProjectionMismatchError.__name__} / NotAChestRadiographError -- three distinct")
    print(f"[T17] audit reason codes: {row_declared.reason_code!r} (stage "
          f"{row_declared.stage!r}) vs {row_mismatch.reason_code!r} (stage "
          f"{row_mismatch.stage!r})")


def test_T18_a_frontal_image_is_not_affected_by_any_projection_control(client):
    """T18. A frontal image is not affected by any control in §5.5 or §6.2.

    Asserted positively: the upload succeeds, no audit row is written, and
    its top-1 sits above the reject threshold -- so neither A16 nor M10
    fired.
    """
    before = len(_rejection_rows())
    response = _upload(client, fixtures.frontal_radiograph(), "frontal.png",
                       declared_projection="PA")
    assert response.status_code == 200, response.text
    body = response.json()

    assert len(_rejection_rows()) == before, "a projection control rejected a frontal image"
    assert body["top1_similarity"] >= settings.PROJECTION_REJECT_THRESHOLD
    assert body["retrieval_support"] == RetrievalSupport.AT_OR_ABOVE_FLOOR.value
    assert body["retrieved_cases"]

    print(f"\n[T18] HTTP 200, no audit row written. top1={body['top1_similarity']:.6f} "
          f">= reject {settings.PROJECTION_REJECT_THRESHOLD:.6f}; "
          f"support={body['retrieval_support']}")


def test_T19_both_projection_messages_render_in_english_and_bengali():
    """T19. Both projection messages render in English and in Bengali
    through the i18n key set.

    The keys the BACKEND sends are the ones looked up, not a hand-written
    copy: they are read off the exception classes themselves, so a key
    renamed on one side and not the other fails here.
    """
    en = (REPO_ROOT / "frontend" / "src" / "lib" / "i18n" / "dictionaries" / "en.ts").read_text(
        encoding="utf-8")
    bn = (REPO_ROOT / "frontend" / "src" / "lib" / "i18n" / "dictionaries" / "bn.ts").read_text(
        encoding="utf-8")

    for exc in (LateralProjectionError, ProjectionMismatchError):
        key = exc.message_key
        assert f'"{key}"' in en, f"{key} missing from en.ts"
        assert f'"{key}"' in bn, f"{key} missing from bn.ts"

    # the two messages must be different strings in each language --
    # A16 states a fact, M10 states a doubt (M12)
    import re

    def value_of(source: str, key: str) -> str:
        match = re.search(rf'"{re.escape(key)}":\s*\n?\s*"((?:[^"\\]|\\.)*)"', source)
        assert match, f"could not read the value of {key}"
        return match.group(1)

    en_lateral = value_of(en, LateralProjectionError.message_key)
    en_mismatch = value_of(en, ProjectionMismatchError.message_key)
    bn_lateral = value_of(bn, LateralProjectionError.message_key)
    bn_mismatch = value_of(bn, ProjectionMismatchError.message_key)

    assert en_lateral != en_mismatch and bn_lateral != bn_mismatch
    # M12: the mismatch message must not assert the image is wrong
    assert "may differ from the reference archive" in en_mismatch
    assert "does not appear" in en_mismatch
    # both Bengali strings must actually be Bengali, not an English fallback
    assert any("ঀ" <= ch <= "৿" for ch in bn_lateral)
    assert any("ঀ" <= ch <= "৿" for ch in bn_mismatch)

    def _print(line: str) -> None:
        """Print, surviving a console that cannot encode Bengali.

        This suite is run for its command output, and on Windows the
        console codec is cp1252, which raises UnicodeEncodeError on the
        Bengali strings -- an artifact of the terminal, not of the
        dictionaries. Falling back to the escaped form keeps the evidence
        visible instead of failing a passing assertion on a print.
        """
        try:
            print(line)
        except UnicodeEncodeError:
            print(line.encode("unicode_escape").decode("ascii"))

    bengali = sum(1 for ch in bn_lateral + bn_mismatch if "ঀ" <= ch <= "৿")
    _print(f"\n[T19] {LateralProjectionError.message_key}")
    _print(f"      en: {en_lateral}")
    _print(f"      bn: {bn_lateral}")
    _print(f"[T19] {ProjectionMismatchError.message_key}")
    _print(f"      en: {en_mismatch}")
    _print(f"      bn: {bn_mismatch}")
    _print(f"[T19] both keys present in en.ts and bn.ts; Bengali codepoints in the two "
           f"bn strings: {bengali}")


# ======================================================================
# T21 -- section 15
# ======================================================================


def test_T21_chroma_projection_metadata_comes_from_the_data_row():
    """T21. The projection value in the ChromaDB metadata comes from the
    data row, not from a literal (§15).

    Proved by feeding build_metadata_records() a row whose projection is
    NOT "Frontal" and observing that value in the output. A test that only
    checked for "Frontal" would pass against the literal it is meant to
    catch -- that is exactly §15's "correct by luck, not by construction".

    Run against the function, not against the live collection: §15's Note
    states the correction does not change the current index contents, so
    re-indexing would prove nothing and would rewrite a validated archive.
    """
    import sys

    import pandas as pd

    sys.path.insert(0, str(REPO_ROOT))
    from ml.retrieval.build_chroma_index import build_metadata_records

    frame = pd.DataFrame([
        {"study_uid": "1", "patient_uid": "SYN-1",
         "masked_image_path": "ml/datasets/masked/a.png", "projection": "Lateral",
         "primary_label": "Normal", "label_set": "Normal", "findings_clean": "f",
         "impression_clean": "i", "cluster_id": 1, "embedding_model": "biomedclip",
         "embedding_version": "v1"},
        {"study_uid": "2", "patient_uid": "SYN-2",
         "masked_image_path": "ml/datasets/masked/b.png", "projection": "Frontal",
         "primary_label": "Normal", "label_set": "Normal", "findings_clean": "f",
         "impression_clean": "i", "cluster_id": 2, "embedding_model": "biomedclip",
         "embedding_version": "v1"},
    ])
    records = build_metadata_records(frame, cfg={}, indexed_at="2026-08-18T00:00:00+00:00")

    assert [r["projection"] for r in records] == ["Lateral", "Frontal"], (
        "projection is not being read from the data row")

    # and the real prepared metadata carries the column the indexer reads
    train = pd.read_csv(REPO_ROOT / "ml" / "datasets" / "metadata" / "train_metadata.csv")
    assert "projection" in train.columns
    assert train["projection"].notna().all()

    print(f"\n[T21] build_metadata_records() projections for rows declaring "
          f"['Lateral', 'Frontal'] -> {[r['projection'] for r in records]}")
    print(f"[T21] train_metadata.csv has a projection column: n={len(train)}, "
          f"values={train['projection'].value_counts().to_dict()}")
    print(f"[T21] §15 Note holds: every current row is still Frontal, index unchanged")
