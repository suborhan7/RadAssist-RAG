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
"""
from __future__ import annotations

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
from app.api.schemas import HealthResponse, RetrievedCaseResponse, RetrieveResponse, VotedLabelResponse
from app.core.config import settings
from app.domain.entities import Doctor, RetrievedCase, VotedLabel
from app.models.retrieval_session import RetrievalSession
from app.models.retrieved_evidence import RetrievedEvidence

router = APIRouter()


@contextmanager
def _saved_upload(file: UploadFile):
    """Request I/O plumbing, not business logic: persists the multipart
    upload to a temp path so ImageValidator/BiomedCLIPAdapter (both
    file-path based) can consume it, and guarantees cleanup regardless of
    success or failure. No decision is made about the file's content here
    -- that's ImageValidator's job, inside RetrievalService.retrieve()."""
    suffix = os.path.splitext(file.filename or "")[1] or ".png"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(file.file.read())
        tmp.close()
        yield tmp.name
    finally:
        os.remove(tmp.name)


def _build_response(
    session_id: uuid.UUID,
    retrieval_time_ms: int,
    retrieved_cases: list[RetrievedCase],
    voted_labels: list[VotedLabel],
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
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness only -- no DB/Chroma reachability check (a documented
    future improvement, not required now)."""
    return HealthResponse(status="ok")


@router.post("/retrieve", response_model=RetrieveResponse)
def retrieve(
    request: Request,
    file: UploadFile = File(...),
    top_k: int = Form(5),
    min_similarity: float = Form(0.0),
    patient_id: str | None = Form(None),
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

    with _saved_upload(file) as temp_path:
        start = time.perf_counter()
        try:
            retrieved_cases = retrieval_service.retrieve(temp_path, top_k, min_similarity)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        voted_labels = label_voting_service.vote(retrieved_cases)
        retrieval_time_ms = int((time.perf_counter() - start) * 1000)

        # Mask BEFORE the temp upload is deleted (_saved_upload's `finally`
        # block removes it the moment this `with` exits) -- the persisted
        # copy is the ONLY one that survives the request, and it must never
        # be the raw upload (see this module's docstring).
        suffix = os.path.splitext(file.filename or "")[1] or ".png"
        persisted_dir = Path(settings.UPLOADED_IMAGES_DIR)
        persisted_dir.mkdir(parents=True, exist_ok=True)
        persisted_path = persisted_dir / f"{session_id}{suffix}"
        phi_masker.detect_and_mask(Path(temp_path), persisted_path)

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

    return _build_response(session_id, retrieval_time_ms, retrieved_cases, voted_labels)


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