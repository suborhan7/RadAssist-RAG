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
from dataclasses import replace

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

    # get_by_ids() is an ID fetch, not a ranked search, so it has no distance to
    # report and stamps similarity = 1.0 on every case (see its own docstring).
    # That sentinel is correct at its own layer and wrong the moment anything
    # downstream treats it as a measurement -- and three things do:
    #
    #   * LabelVotingService.vote() sums similarity into vote_weight, so every
    #     weight collapsed to the plain case count (3 cases -> "3.00"), and that
    #     number is printed into the LLM prompt (prompt_builder.py's
    #     "- Vote weight: {:.2f}" line).
    #   * ContextBuilder sorts by (-similarity, source_uid). With every
    #     similarity identical the sort degenerated to alphabetical source_uid,
    #     so the evidence order in the prompt -- and top_retrieved_case -- was
    #     uid order, not similarity order.
    #   * The report UI renders similarity as a percentage, showing 100.0% on
    #     every retrieved case.
    #
    # The real numbers were never lost: RetrievedEvidence.similarity persists
    # each case's score from the original ranked query. They were simply read
    # for their study_uid and then discarded. This restores them.
    #
    # Keyed by uid rather than zipped positionally: get_by_ids() documents that
    # it reorders to match the requested order, but it can also return fewer
    # results if a uid is missing from the collection, and a positional zip
    # would then silently pair the wrong score with the wrong case.
    persisted_similarity = {row.study_uid: row.similarity for row in evidence_rows}
    retrieved_cases = [
        replace(case, similarity=persisted_similarity[case.source_uid])
        if case.source_uid in persisted_similarity
        else case
        for case in vector_store.get_by_ids(study_uids)
    ]
    voted_labels = label_voting_service.vote(retrieved_cases)

    return retrieval_session, retrieved_cases, voted_labels
