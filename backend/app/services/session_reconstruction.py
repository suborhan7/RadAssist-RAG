"""
app/services/session_reconstruction.py
====================================================================
Shared helper: reconstructs a persisted RetrievalSession's evidence
(retrieved cases + voted labels) from its session_id. Extracted from
ReportGenerationService.generate() (Phase 8) so ReportGenerationService
and the new QuestionnaireService (Phase 9) call the exact same
reconstruction logic rather than maintaining two, potentially-drifting
copies -- same "one shared implementation" discipline as Phase 8 Step 2's
reuse of map_chroma_results and Phase 9 Step 3's reuse of the taxonomy
loader.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.domain.entities import RetrievedCase, VotedLabel
from app.domain.interfaces import ILabelVoter, IVectorStore
from app.models.retrieval_session import RetrievalSession
from app.models.retrieved_evidence import RetrievedEvidence
from app.services.exceptions import SessionNotFoundError


def reconstruct_session_evidence(
    db: Session,
    vector_store: IVectorStore,
    label_voting_service: ILabelVoter,
    session_id: str,
) -> tuple[RetrievalSession, list[RetrievedCase], list[VotedLabel]]:
    """Returns (retrieval_session, retrieved_cases, voted_labels) for a
    real, persisted session_id. Raises SessionNotFoundError for either a
    malformed UUID string or a genuinely missing session -- same
    exception, same two failure modes, established in Phase 8 Step 6.
    """
    # RetrievalSession.id / RetrievedEvidence.session_id are Uuid-typed
    # columns -- SQLAlchemy's Uuid type expects an actual uuid.UUID object
    # bound as a query parameter, not a plain str (a bare str comparison
    # raises deep inside the DBAPI param processor, not a clean "not
    # found" -- the real bug caught and fixed in Phase 8 Step 6).
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise SessionNotFoundError(f"session_id is not a valid UUID: {session_id!r}") from None

    retrieval_session = db.query(RetrievalSession).filter(RetrievalSession.id == session_uuid).one_or_none()
    if retrieval_session is None:
        raise SessionNotFoundError(f"no RetrievalSession found for session_id={session_id}")

    evidence_rows = (
        db.query(RetrievedEvidence)
        .filter(RetrievedEvidence.session_id == session_uuid)
        .order_by(RetrievedEvidence.rank)
        .all()
    )
    study_uids = [row.study_uid for row in evidence_rows]

    retrieved_cases = vector_store.get_by_ids(study_uids)
    voted_labels = label_voting_service.vote(retrieved_cases)

    return retrieval_session, retrieved_cases, voted_labels
