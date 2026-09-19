"""
app/models/upload_rejection.py
====================================================================
upload_rejection_log: one row per rejected upload -- decision record DR-2
of docs/methodology/input_admission_projection_gate_architecture_v1.1_
FROZEN.md ("The system records rejected uploads. It records metadata
only.").

The column list below is DR-2's "Record these fields" table, and nothing
else. What is ABSENT is as much a requirement as what is present -- DR-2's
"Do not record these fields" table forbids all four of:

  * the image bytes  -- the image can contain Protected Health Information
  * the ORIGINAL FILE NAME -- "a file name frequently contains a patient
    name", DR-2's own example being `Abdur_Rahman_CXR_2026.jpg`
  * the masked image -- neither version of the image is kept
  * EXIF metadata -- can contain Protected Health Information

There is deliberately no `filename` column for a later change to start
populating, and UploadAuditService (app/services/upload_audit_service.py)
is never handed a file name to write into one. §10's closing Rule and
DR-2's Warning extend the same prohibition to error messages and
application log lines, which is enforced at those sites rather than here.

`declared_extension` is not the file name: it is the extension alone
(".png"), which DR-2 lists under "Record these fields" for diagnosis.
Splitting the extension off at the API boundary and passing only that
onward is what lets the whole admission and audit path be structurally
incapable of seeing a name.

Append-only by convention and enforced at the service layer, same trust
model as report_audit_log (Phase 17) -- see that module for why this
codebase relies on every write going through the service layer rather
than on a DB-level immutability constraint.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class UploadRejectionLog(Base):
    __tablename__ = "upload_rejection_log"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    # DR-2 "Timestamp (UTC) -- audit sequence". server_default=func.now()
    # matches every other timestamp column in this schema.
    at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    # DR-2 "Doctor identifier -- accountability". Not nullable: every route
    # that can reject an upload is behind get_current_doctor, so an
    # unattributable rejection would mean the auth dependency was bypassed,
    # which should fail loudly rather than write an anonymous audit row.
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("doctors.id"), nullable=False, index=True
    )

    # DR-2 "Rejection reason code -- proof that the gate operated".
    reason_code: Mapped[str] = mapped_column(String, nullable=False)

    # DR-2 "Stage of rejection -- shows which control operated". Kept
    # separate from reason_code rather than folded into it: DR-2 lists them
    # as two fields answering two questions, and "which control fired"
    # (admission format / admission size / admission decode / modality
    # gate) is the axis the calibration in §11.2 groups by.
    stage: Mapped[str] = mapped_column(String, nullable=False)

    # DR-2 "Modality score, if calculated -- evidence for the calibration".
    # Nullable exactly because of "if calculated": an upload rejected at
    # A1-A11 never reached the embedder, so no score exists. NULL here
    # means "not calculated", never "calculated as zero".
    modality_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # DR-2 "SHA-256 of the raw bytes -- finds repeated attempts". Over the
    # RAW upload, not the normalized PNG: a file rejected before decode has
    # no normalized form, and repeated attempts must hash identically.
    raw_sha256: Mapped[str] = mapped_column(String, nullable=False, index=True)

    # DR-2 "File size in bytes -- diagnosis".
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    # DR-2 "Declared extension -- diagnosis". The extension only. See this
    # module's docstring.
    declared_extension: Mapped[str] = mapped_column(String, nullable=False)
