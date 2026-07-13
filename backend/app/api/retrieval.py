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
"""
from __future__ import annotations

import os
import tempfile
import time
import uuid
from contextlib import contextmanager

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.api.schemas import HealthResponse, RetrievedCaseResponse, RetrieveResponse, VotedLabelResponse
from app.core.config import settings
from app.domain.entities import RetrievedCase, VotedLabel
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
    db: Session = Depends(get_db),
) -> RetrieveResponse:
    """retrieval_time_ms covers only RetrievalService.retrieve() +
    LabelVotingService.vote() -- the ML pipeline itself. It excludes the
    upload file-save I/O (before) and DB persistence (after)."""
    retrieval_service = request.app.state.retrieval_service
    label_voting_service = request.app.state.label_voting_service

    with _saved_upload(file) as temp_path:
        start = time.perf_counter()
        try:
            retrieved_cases = retrieval_service.retrieve(temp_path, top_k, min_similarity)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        voted_labels = label_voting_service.vote(retrieved_cases)
        retrieval_time_ms = int((time.perf_counter() - start) * 1000)

    session_id = uuid.uuid4()
    db.add(
        RetrievalSession(
            id=session_id,
            query_image_path=file.filename or temp_path,
            top_k=top_k,
            min_similarity=min_similarity,
            num_results=len(retrieved_cases),
            retrieval_time_ms=retrieval_time_ms,
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