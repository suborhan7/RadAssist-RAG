"""
app/api/retrieval.py
====================================================================
GET /health, POST /retrieve. Routes are intentionally thin: request
validation (via FastAPI's own parameter typing), calls into the
already-constructed RetrievalService/LabelVotingService (built once at
startup, see app/main.py's lifespan) and the DB session, and response
serialization -- no business/medical logic here. All retrieval,
embedding, similarity, and voting logic lives in the injected services,
which this step does not modify.

Two small pieces of request-handling plumbing (_saved_upload,
_build_response) are factored out as module-level helpers rather than
inlined into the route body, but are flagged in the Step 11 dev log entry
as not cleanly fitting the validate/call-service/serialize-response
three-way split, since they're neither -- see that entry for the full
line-by-line accounting.

Phase 11 addition: an optional `patient_id` form field. This closes a
real gap found while writing Phase 11's closing integration test --
retrieval_sessions.patient_id (Step 2's migration) had no real,
HTTP-reachable way to ever be set: neither this endpoint nor
POST /generate-report accepted a patient_id, so PatientService.get_history()
and ComparisonService had no way to find a real doctor's reports in
production, only in tests that poked the DB directly. Added here (the
point where the RetrievalSession row is actually created) rather than at
POST /generate-report, since that keeps the fix to the endpoint that owns
this column's creation and requires no change to ReportGenerationService.
Purely additive: omitting patient_id preserves the exact prior behavior
(NULL, as it always was for every existing caller).

Phase 12 Step 7 addition: the uploaded query image is now masked (via
PHIMasker, app.state singleton, same shared/ implementation the offline
ml/ pipeline uses) and persisted to settings.UPLOADED_IMAGES_DIR before
the original temp upload is deleted, and query_image_path now stores that
real, stable, servable path -- previously it stored only the original
filename string (never a live reference to anything, since the temp file
was always deleted in _saved_upload's `finally` block). This closes a
real gap found while building the frontend Comparison page: there was
previously no way to redisplay ANY past visit's X-ray at all. The RAW
upload is deliberately never persisted, only the masked copy -- every
image this system stores or serves has gone through PHI masking since
Phase 1, and persisting live uploads was not going to be the first
exception to that. GET /retrieval-sessions/{session_id}/image (below)
serves the persisted masked file.

Input Admission and Modality Gate
---------------------------------
POST /retrieve is where §9 of input_admission_modality_gate_architecture_
v1.0_FROZEN.md lands, because every step of that pipeline up to and
including retrieval happens inside this one endpoint:

    Upload
      -> ImageAdmissionService      (admit)   A1-A13   -> 415 / 413 / 422
      -> PrivacyService             (mask)
      -> EmbeddingService           (embed)
      -> ModalityGateService        (gate)    M1-M6    -> 422, BLOCKS
      -> RetrievalService           (retrieve)
      -> ModalityGateService        (support) M7-M9    -> never blocks

Two changes to previously-working behavior are deliberate and are the
frozen order, not incidental refactoring:

1. The masking step MOVED from after retrieval to before embedding. It
   used to run last, purely so a masked copy could be persisted for the
   Comparison page, while the vector was computed from the RAW upload.
   §3.3 and §9 both put mask before embed. The embedding now comes from
   the masked pixels, which is also the only order under which the vector
   the gate judges is the vector derived from what this system is willing
   to store. Phase 1 measured the embedding impact of masking at mean
   cosine 0.992 (0/50 flagged), so this does not disturb retrieval
   quality.

2. Embedding and querying are no longer one call. The gate has to run
   between them (M1: it takes the existing vector and must not encode the
   image again), so this route embeds explicitly and then calls
   RetrievalService.retrieve_by_vector().

The raw upload bytes are never written to disk at any point (A13). They
are read into memory, admitted, and replaced by ImageAdmissionService's
normalized PNG; only that normalized copy is ever written to a temp path,
and only its masked form survives the request.

The file name is read exactly once, to split off its extension, and the
extension alone travels onward -- see _declared_extension() below.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_doctor, get_db
from app.api.schemas import (
    HealthResponse,
    RetrievedCaseResponse,
    RetrieveResponse,
    ServiceStatusResponse,
    VotedLabelResponse,
)
from app.core.config import settings
from app.domain.entities import Doctor, RetrievalSupport, RetrievedCase, VotedLabel
from app.models.retrieval_session import RetrievalSession
from app.models.retrieved_evidence import RetrievedEvidence
from app.services.exceptions import (
    ImageTooLargeError,
    InputAdmissionError,
    InvalidImageError,
    LateralProjectionError,
    NotAChestRadiographError,
    ProjectionMismatchError,
    UnsupportedImageFormatError,
)
from app.services.service_health_service import ServiceHealthService
from app.services.upload_audit_service import UploadAuditService

router = APIRouter()

# §10's table, as data. Written here rather than as a chain of `except`
# clauses because §10 defines the exception-type -> status mapping as the
# API layer's single responsibility, and a table makes a missing or
# duplicated mapping visible at a glance.
_ADMISSION_STATUS_BY_TYPE: dict[type[InputAdmissionError], int] = {
    UnsupportedImageFormatError: 415,
    ImageTooLargeError: 413,
    InvalidImageError: 422,
}


def _projection_detail(exc: LateralProjectionError | ProjectionMismatchError) -> dict[str, str]:
    """§10.1's response body for the two projection rejections.

    Carries an i18n KEY, never a sentence. §10.1's Rule: "Translate both
    messages through the i18n key set. Do not write English text in the
    response body." The English and Bengali strings live in the frontend
    dictionaries; this layer sends the key and the reason code, so the two
    languages cannot drift from each other through a hardcoded default.

    `reason_code` is included alongside so a client can branch on the
    machine-readable cause without parsing a message, and so the value in
    the response matches the value written to the DR-2 audit row exactly.
    """
    return {"reason_code": exc.reason_code, "message_key": exc.message_key}


def _declared_extension(file: UploadFile) -> str:
    """The ONLY place in the admission path that touches the uploaded file
    name, and it keeps nothing but the extension.

    DR-2's Warning is that a file name frequently contains a patient name
    (`Abdur_Rahman_CXR_2026.jpg`), and §10's Rule forbids it from reaching
    any error message; DR-2 forbids it from reaching the audit log. Both
    hold structurally downstream of this function, because everything
    downstream is given `".jpg"` and never the name it came from.

    An absent or extension-less name yields "", which is not in the
    configured allow-list and is therefore rejected by A1 -- the correct
    outcome, since A3 forbids inferring the format from the name anyway.
    """
    return os.path.splitext(file.filename or "")[1].lower()


@contextmanager
def _saved_upload(file: UploadFile):
    """Request I/O plumbing, not business logic: persists the multipart
    upload to a temp path so ImageValidator/BiomedCLIPAdapter (both
    file-path based) can consume it, and guarantees cleanup regardless of
    success or failure. No decision is made about the file's content here
    -- that's ImageValidator's job, inside RetrievalService.retrieve().

    Retained for the pre-existing callers that still hand a path to
    RetrievalService.retrieve(). POST /retrieve no longer uses it: under
    §9 the bytes that reach disk must be ImageAdmissionService's
    normalized PNG, never the raw upload (A13), so that route uses
    _saved_admitted_png() below instead.
    """
    suffix = os.path.splitext(file.filename or "")[1] or ".png"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(file.file.read())
        tmp.close()
        yield tmp.name
    finally:
        os.remove(tmp.name)


@contextmanager
def _saved_admitted_png(png_bytes: bytes):
    """Writes the NORMALIZED PNG (A12's re-encode) to a temp path so
    PHIMasker and the embedder -- both file-path based -- can consume it,
    and removes it unconditionally afterwards.

    The suffix is always ".png" and never derived from the upload, because
    by this point the bytes really are a PNG regardless of what was
    uploaded: a JPEG has already been decoded and re-encoded. Deriving the
    suffix from the original name here would reintroduce exactly the
    name-dependency A3 exists to remove.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    try:
        tmp.write(png_bytes)
        tmp.close()
        yield tmp.name
    finally:
        os.remove(tmp.name)


def _build_response(
    session_id: uuid.UUID,
    retrieval_time_ms: int,
    retrieved_cases: list[RetrievedCase],
    voted_labels: list[VotedLabel],
    modality_score: float,
    retrieval_support: RetrievalSupport,
    top1_similarity: float | None,
) -> RetrieveResponse:
    """Serializes already-computed results into the frozen response
    contract (development_log.md, Phase 4 "Input/output contracts") plus
    the voted_labels extension. primary_label is labels[0] by convention
    (Step 1 design decision). label_set is currently a degenerate
    single-label value (";".join(labels) == primary_label today) because
    chroma_result_mapper.py's multi-label parsing is a still-open TODO
    from Step 2 -- not something this step can fix without touching that
    frozen file."""
    return RetrieveResponse(
        session_id=str(session_id),
        retrieval_time_ms=retrieval_time_ms,
        embedding_model=settings.CHROMA_EMBEDDING_MODEL,
        embedding_version=settings.CHROMA_EMBEDDING_VERSION,
        collection_name=settings.CHROMA_COLLECTION_NAME,
        retrieved_cases=[
            RetrievedCaseResponse(
                rank=rank,
                similarity=case.similarity,
                study_uid=case.source_uid,
                primary_label=case.labels[0] if case.labels else "",
                label_set=";".join(case.labels),
                cluster_id=case.cluster_id,
                findings=case.findings,
                impression=case.impression,
                image_path=case.image_path,
            )
            for rank, case in enumerate(retrieved_cases, start=1)
        ],
        voted_labels=[
            VotedLabelResponse(label=v.label, vote_weight=v.vote_weight, agreement=v.agreement)
            for v in voted_labels
        ],
        # S8: the BACKEND calculates the retrieval support category and the
        # frontend shows it. S9 forbids the frontend from recomputing the
        # category from the raw similarity scores in retrieved_cases -- so
        # the category is sent as a value, alongside the top-1 similarity
        # it was derived from (for display, not for re-derivation).
        #
        # S9's Note names the precedent being avoided: the frontend already
        # re-calculates the agreement score from the raw retrieved cases,
        # a known defect that can show two different numbers for one
        # report. That pattern is deliberately not repeated here.
        modality_score=modality_score,
        retrieval_support=retrieval_support.value,
        top1_similarity=top1_similarity,
    )


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    """§16.1 (design_specification.md): fulfills this route's own former
    comment ("no DB/Chroma reachability check, a documented future
    improvement") -- real FastAPI/Ollama/ChromaDB/GPU checks via
    ServiceHealthService, backing §8.2's four-service status strip.
    Stays public/unauthenticated exactly as before; `status` (the only
    field prior callers read) is untouched."""
    service = ServiceHealthService(vector_store=request.app.state.vector_store)
    health = service.check_all()
    return HealthResponse(
        status="ok",
        fastapi=ServiceStatusResponse(status=health.fastapi.status, detail=health.fastapi.detail),
        ollama=ServiceStatusResponse(status=health.ollama.status, detail=health.ollama.detail),
        chromadb=ServiceStatusResponse(status=health.chromadb.status, detail=health.chromadb.detail),
        gpu=ServiceStatusResponse(status=health.gpu.status, detail=health.gpu.detail),
    )


@router.post("/retrieve", response_model=RetrieveResponse)
def retrieve(
    request: Request,
    file: UploadFile = File(...),
    top_k: int = Form(5),
    min_similarity: float = Form(0.0),
    patient_id: str | None = Form(None),
    # A14: the request must hold a declared projection. Typed as optional
    # HERE, at the transport layer, and required by ImageAdmissionService
    # instead -- deliberately. A FastAPI-level `Form(...)` would return 422
    # with FastAPI's own validation body, which carries no reason code and
    # writes no DR-2 audit row. A15 is a rejection this system must record
    # like any other, so the field arrives optional and
    # check_declared_projection() rejects it with PROJECTION_NOT_DECLARED.
    declared_projection: str | None = Form(None),
    db: Session = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
) -> RetrieveResponse:
    """retrieval_time_ms covers only RetrievalService.retrieve() +
    LabelVotingService.vote() -- the ML pipeline itself. It excludes the
    upload file-save I/O (before) and DB persistence (after)."""
    retrieval_service = request.app.state.retrieval_service
    label_voting_service = request.app.state.label_voting_service

    # Same "malformed identifier caught at the route boundary" precedent as
    # app/api/patients.py's history endpoint -- 400, not a service-layer
    # exception type, since this is a request-shape problem, not a lookup.
    patient_uuid: uuid.UUID | None = None
    if patient_id is not None:
        try:
            patient_uuid = uuid.UUID(patient_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="patient_id is not a valid UUID.")

    session_id = uuid.uuid4()
    phi_masker = request.app.state.phi_masker
    image_admission_service = request.app.state.image_admission_service
    modality_gate_service = request.app.state.modality_gate_service
    embedder = request.app.state.embedder
    upload_audit_service = UploadAuditService(db)

    # The extension is split off here and the name is dropped on the floor.
    # Nothing below this line -- not the admission service, not the gate,
    # not the audit row, not any HTTPException detail -- ever sees it.
    declared_extension = _declared_extension(file)
    raw_bytes = file.file.read()

    # ---- admit (A1-A13) -------------------------------------------------
    try:
        admitted = image_admission_service.admit(raw_bytes, declared_extension)
    except InputAdmissionError as exc:
        # DR-2: record the rejection with metadata only. The SHA-256 is
        # computed over the raw bytes here rather than read off `admitted`,
        # which does not exist on this path -- a file rejected at A1 or A4
        # was never decoded, so it has no normalized form to hash, and
        # DR-2's "finds repeated attempts" requires the same file to hash
        # the same whether it was rejected early or late.
        upload_audit_service.record(
            doctor_id=current_doctor.id,
            reason_code=exc.reason_code,
            stage=exc.stage,
            raw_sha256=hashlib.sha256(raw_bytes).hexdigest(),
            file_size_bytes=len(raw_bytes),
            declared_extension=declared_extension,
        )
        raise HTTPException(
            status_code=_ADMISSION_STATUS_BY_TYPE[type(exc)], detail=str(exc)
        ) from exc

    # ---- declared projection (A14-A17) ----------------------------------
    # Runs AFTER A1-A13 and BEFORE the mask, per §9's pipeline order. A17:
    # the image is not masked, not embedded, and ChromaDB is not queried on
    # this path -- all three happen further down, inside the `with` block
    # below, which this raise never reaches.
    try:
        image_admission_service.check_declared_projection(declared_projection)
    except LateralProjectionError as exc:
        upload_audit_service.record(
            doctor_id=current_doctor.id,
            reason_code=exc.reason_code,
            stage=exc.stage,
            raw_sha256=admitted.sha256,
            file_size_bytes=admitted.size_bytes,
            declared_extension=admitted.declared_extension,
        )
        # 422 per §10's table. The body carries an i18n key, not English.
        raise HTTPException(status_code=422, detail=_projection_detail(exc)) from exc
    except InputAdmissionError as exc:
        # A15: PROJECTION_NOT_DECLARED, an InvalidImageError per §10's table.
        upload_audit_service.record(
            doctor_id=current_doctor.id,
            reason_code=exc.reason_code,
            stage=exc.stage,
            raw_sha256=admitted.sha256,
            file_size_bytes=admitted.size_bytes,
            declared_extension=admitted.declared_extension,
        )
        raise HTTPException(
            status_code=_ADMISSION_STATUS_BY_TYPE[type(exc)], detail=str(exc)
        ) from exc

    # From here on the raw bytes are done with (A13). Only `admitted.
    # png_bytes` -- pixels, no EXIF, no polyglot payload -- goes forward.
    with _saved_admitted_png(admitted.png_bytes) as normalized_path:
        # ---- mask (PrivacyService) --------------------------------------
        # Now BEFORE the embed, per §3.3 and §9. The masked file is written
        # straight to its permanent home because it is both what gets
        # embedded and what gets served back to the Comparison page later
        # -- one masked artifact, not two copies that could diverge.
        persisted_dir = Path(settings.UPLOADED_IMAGES_DIR)
        persisted_dir.mkdir(parents=True, exist_ok=True)
        persisted_path = persisted_dir / f"{session_id}.png"
        phi_masker.detect_and_mask(Path(normalized_path), persisted_path)

        start = time.perf_counter()

        # ---- embed (EmbeddingService) -----------------------------------
        query_vector = embedder.embed_image(str(persisted_path))

        # ---- gate (M1-M6) -- BLOCKS (DR-1) ------------------------------
        try:
            modality_score = modality_gate_service.gate(query_vector)
        except NotAChestRadiographError as exc:
            # The masked image is removed before returning: DR-2 forbids
            # keeping EITHER version of the image for a rejected upload,
            # and this one only exists because masking has to precede the
            # embedding the gate judges.
            persisted_path.unlink(missing_ok=True)
            upload_audit_service.record(
                doctor_id=current_doctor.id,
                reason_code=exc.reason_code,
                stage=exc.stage,
                raw_sha256=admitted.sha256,
                file_size_bytes=admitted.size_bytes,
                declared_extension=admitted.declared_extension,
                modality_score=exc.modality_score,
            )
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        # ---- retrieve (RetrievalService) --------------------------------
        retrieved_cases = retrieval_service.retrieve_by_vector(query_vector, top_k, min_similarity)
        voted_labels = label_voting_service.vote(retrieved_cases)
        retrieval_time_ms = int((time.perf_counter() - start) * 1000)

    # ---- bands (M7-M12) -------------------------------------------------
    # M7: read the top-1 similarity from the RetrievalService. Taken from
    # retrieved_cases[0], which SimilaritySearchPolicy has already sorted
    # by similarity descending.
    #
    # M8 places it in one of §6.1's three bands. The first band BLOCKS
    # (M10, projection mismatch); the other two only set a category and
    # never block (DR-3). That asymmetry is DR-5: two thresholds, two
    # meanings, and §6.1's Warning forbids collapsing them into one.
    top1_similarity = retrieved_cases[0].similarity if retrieved_cases else None
    try:
        retrieval_support = modality_gate_service.check_projection_band(top1_similarity)
    except ProjectionMismatchError as exc:
        # The masked image is removed before returning, exactly as on the
        # M5 path: DR-2 forbids keeping either version of the image for a
        # rejected upload, and this copy exists only because masking has to
        # precede the embedding that produced this measurement.
        persisted_path.unlink(missing_ok=True)
        upload_audit_service.record(
            doctor_id=current_doctor.id,
            reason_code=exc.reason_code,
            stage=exc.stage,
            raw_sha256=admitted.sha256,
            file_size_bytes=admitted.size_bytes,
            declared_extension=admitted.declared_extension,
            # DR-2's "modality score, if calculated" -- it WAS calculated on
            # this path, since M5 ran and passed before retrieval.
            modality_score=modality_score,
        )
        # M11: reason code FRONTAL_MISMATCH, a distinct exception type, and
        # NOT NotAChestRadiographError. M12: the message asks the doctor to
        # check the projection rather than asserting the image is wrong --
        # see the i18n string behind this key.
        raise HTTPException(status_code=422, detail=_projection_detail(exc)) from exc

    db.add(
        RetrievalSession(
            id=session_id,
            query_image_path=str(persisted_path),
            top_k=top_k,
            min_similarity=min_similarity,
            num_results=len(retrieved_cases),
            retrieval_time_ms=retrieval_time_ms,
            patient_id=patient_uuid,
            doctor_id=uuid.UUID(current_doctor.id),
        )
    )
    db.add_all(
        [
            RetrievedEvidence(
                session_id=session_id, study_uid=case.source_uid, rank=rank, similarity=case.similarity
            )
            for rank, case in enumerate(retrieved_cases, start=1)
        ]
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return _build_response(
        session_id,
        retrieval_time_ms,
        retrieved_cases,
        voted_labels,
        modality_score,
        retrieval_support,
        top1_similarity,
    )


@router.get("/retrieval-sessions/{session_id}/image")
def get_retrieval_session_image(
    session_id: str,
    db: Session = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor),
) -> FileResponse:
    """Serves the MASKED query image persisted by POST /retrieve above.
    Malformed or missing session_id both raise SessionNotFoundError -> 404,
    reusing the exact same single-exception-type precedent
    reconstruct_session_evidence() already established for this identifier
    (Phase 8) -- not the different 400/404 split app/api/patients.py uses
    for a different identifier. A session that exists but predates this
    fix (query_image_path holding only a filename, not a real path) is
    handled as the same 404 the client sees for "no image available" --
    a stale pre-fix session is not a different failure mode a caller needs
    to distinguish from "never had an image."
    """
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"no RetrievalSession found for session_id={session_id}")

    session = db.query(RetrievalSession).filter(RetrievalSession.id == session_uuid).one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail=f"no RetrievalSession found for session_id={session_id}")

    image_path = Path(session.query_image_path)
    if not image_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"no persisted image available for session_id={session_id}",
        )

    return FileResponse(image_path)