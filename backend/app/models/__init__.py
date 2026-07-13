"""
Importing this package registers all ORM models on the shared Base's
mapper registry -- required for the string-based relationship() targets
in retrieval_session.py / retrieved_evidence.py to resolve correctly.
"""
from app.models.explanation import Explanation
from app.models.report import ReportRecord
from app.models.retrieval_session import RetrievalSession
from app.models.retrieved_evidence import RetrievedEvidence

__all__ = ["Explanation", "ReportRecord", "RetrievalSession", "RetrievedEvidence"]
