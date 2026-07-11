"""
Integration test for the Step 9 database layer: real SQLite engine (the
same one Settings/database/base.py configure by default), real table
creation, real inserts, real relationship queries, real FK constraint
enforcement. Not wired into RetrievalService yet -- that's Step 11.

Tables are dropped at teardown so repeated runs don't accumulate rows in
backend/dev.db.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.database.base import Base, SessionLocal, engine
from app.models.retrieval_session import RetrievalSession
from app.models.retrieved_evidence import RetrievedEvidence


@pytest.fixture()
def db_session():
    Base.metadata.create_all(engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def test_insert_and_query_relationship_both_directions(db_session):
    retrieval_session = RetrievalSession(
        query_image_path="ml/datasets/masked/1000_IM-0003-1001.dcm.png",
        top_k=5,
        min_similarity=0.0,
        num_results=2,
        retrieval_time_ms=124,
    )
    db_session.add(retrieval_session)
    db_session.commit()
    db_session.refresh(retrieval_session)

    evidence_1 = RetrievedEvidence(
        session_id=retrieval_session.id, study_uid="2", rank=1, similarity=0.95
    )
    evidence_2 = RetrievedEvidence(
        session_id=retrieval_session.id, study_uid="328", rank=2, similarity=0.87
    )
    db_session.add_all([evidence_1, evidence_2])
    db_session.commit()

    # forward direction: session -> evidence
    fetched_session = db_session.get(RetrievalSession, retrieval_session.id)
    assert fetched_session is not None
    assert fetched_session.created_at is not None
    assert {e.study_uid for e in fetched_session.evidence} == {"2", "328"}

    # reverse direction: evidence -> session
    fetched_evidence = db_session.get(RetrievedEvidence, evidence_1.id)
    assert fetched_evidence.session.id == retrieval_session.id
    assert fetched_evidence.session.query_image_path == retrieval_session.query_image_path


def test_foreign_key_constraint_rejects_unknown_session_id(db_session):
    orphan_evidence = RetrievedEvidence(
        session_id=uuid.uuid4(),  # no matching retrieval_sessions row
        study_uid="9999",
        rank=1,
        similarity=0.5,
    )
    db_session.add(orphan_evidence)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
