"""
Importing this package registers all ORM models on the shared Base's
mapper registry -- required for the string-based relationship() targets
in retrieval_session.py / retrieved_evidence.py to resolve correctly.
"""
from app.models.comparison import ComparisonRecord
from app.models.doctor import DoctorRecord
from app.models.explanation import Explanation
from app.models.patient import PatientRecord
from app.models.report import ReportRecord
from app.models.report_audit_log import ReportAuditLog
from app.models.retrieval_session import RetrievalSession
from app.models.retrieved_evidence import RetrievedEvidence

__all__ = [
    "ComparisonRecord",
    "DoctorRecord",
    "Explanation",
    "PatientRecord",
    "ReportAuditLog",
    "ReportRecord",
    "RetrievalSession",
    "RetrievedEvidence",
]
