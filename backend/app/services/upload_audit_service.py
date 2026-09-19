"""
app/services/upload_audit_service.py
====================================================================
Writes the DR-2 audit row for a rejected upload -- decision record DR-2 of
docs/methodology/input_admission_projection_gate_architecture_v1.1_FROZEN.md.

A third service, not a fourth responsibility bolted onto one of the other
two. §1 and §10 require ImageAdmissionService and ModalityGateService to
stay separate from each other and out of PrivacyService/EmbeddingService;
recording an audit row is neither admission nor gating, and both of those
services raise from paths that must stay free of a database session (the
gate is constructed once at start-up and holds no per-request state).
Keeping the write here is what lets ONE audit path serve rejections from
BOTH controls, which is what makes DR-2's "stage of rejection" field
meaningful.

The PHI contract of this module
-------------------------------
`record()` cannot be given a file name. There is no parameter for one, the
model has no column for one, and the two exception families it consumes
(`InputAdmissionError`, `NotAChestRadiographError`) are raised by services
that were never handed one either. DR-2's Warning -- "the system must not
write the file name to the audit log, to the application log, or to an
error message" -- therefore holds by construction along this whole path,
not by remembering to strip a field.

Nothing here logs. A `logger.warning("rejected upload %s", filename)` is
exactly the leak DR-2 names, and the safest way not to write one is for
this module to have no logger at all.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.upload_rejection import UploadRejectionLog


class UploadAuditService:
    """Implements DR-2's metadata-only rejection record."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def record(
        self,
        *,
        doctor_id: str,
        reason_code: str,
        stage: str,
        raw_sha256: str,
        file_size_bytes: int,
        declared_extension: str,
        modality_score: float | None = None,
    ) -> UploadRejectionLog:
        """Writes exactly one row (T8) and commits it.

        Keyword-only: `reason_code`/`stage` and `raw_sha256`/
        `declared_extension` are same-typed neighbours, and a positional
        swap would produce a well-formed audit row describing the wrong
        rejection -- the failure mode an audit table exists to prevent.

        Committed here rather than left to the caller because this write
        must survive the request that is, by definition, about to fail:
        the caller's very next statement raises the HTTPException for the
        rejection, and a row left uncommitted in that session would be
        rolled back with it, leaving no proof the gate operated (DR-2's
        stated reason for the reason-code field).

        `modality_score` defaults to None for the admission-stage
        rejections that never reached the embedder -- DR-2's "Modality
        score, IF CALCULATED". None means not calculated, never zero.
        """
        row = UploadRejectionLog(
            doctor_id=uuid.UUID(doctor_id),
            reason_code=reason_code,
            stage=stage,
            raw_sha256=raw_sha256,
            file_size_bytes=file_size_bytes,
            declared_extension=declared_extension,
            modality_score=modality_score,
        )
        self._db.add(row)
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        return row
