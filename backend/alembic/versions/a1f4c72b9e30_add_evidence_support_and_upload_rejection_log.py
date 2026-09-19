"""add evidence support signal to reports and the upload rejection audit log

Revision ID: a1f4c72b9e30
Revises: 528c741665ee
Create Date: 2026-08-17 20:10:00.000000

Input Admission and Modality Gate (docs/methodology/input_admission_
modality_gate_architecture_v1.0_FROZEN.md). Two changes, one migration:

  1. §7.3 S5 -- reports.retrieval_support / reports.top1_similarity
  2. DR-2    -- the upload_rejection_log table

Why a NEW migration rather than an edit to the D4 migration (S6 vs S7)
----------------------------------------------------------------------
§7.3 gives two mutually exclusive instructions and this repository
satisfies the precondition of neither, which is worth recording here
rather than resolving silently:

  S6: "If the D4 migration is not applied, add these two fields to the
       D4 migration."
  S7: "If the D4 migration is applied, write a new gated migration. Do
       not modify an applied migration."

Both presume a D4 migration exists. There is none. S5's own Note says
"Decision D4 already stores voted_labels and agreement at generation
time" -- in this codebase it does not: `reports` has no voted_labels or
agreement column, no migration under alembic/versions/ mentions either,
and `agreement` is recomputed on read from the retrieved cases every
time. So the branch S6 selects has no target to edit.

S7's rule is the one that survives the missing precondition, because its
REASON survives it: every migration in this repository's history is
applied (`alembic current` reports 528c741665ee, which is head), so
whatever this change is folded into would be an applied migration. A new
gated revision is therefore the only option that does not modify one.

Both new report columns are nullable with NO backfill, following the
precedent 528c741665ee set for questionnaire_answers/clinical_notes:
NULL means "this report predates the evidence support signal, its real
support state is genuinely unknown". It does not mean BELOW_FLOOR. There
is no honest value to backfill -- recomputing the category for an old
report would need that report's original top-1 similarity re-judged
against today's RETRIEVAL_FLOOR, and RETRIEVAL_FLOOR is a Gate B output
that did not exist when those reports were written.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1f4c72b9e30"
down_revision: Union[str, Sequence[str], None] = "528c741665ee"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- §7.3 S5 -----------------------------------------------------
    with op.batch_alter_table("reports") as batch_op:
        batch_op.add_column(sa.Column("retrieval_support", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("top1_similarity", sa.Float(), nullable=True))

    # --- DR-2 ---------------------------------------------------------
    # The column list is DR-2's "Record these fields" table exactly. There
    # is deliberately no column for the original file name, the image
    # bytes, the masked image, or EXIF metadata -- DR-2's "Do not record
    # these fields" table, whose stated reason for the file name is that
    # it "frequently contains a patient name".
    op.create_table(
        "upload_rejection_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("doctor_id", sa.Uuid(), nullable=False),
        sa.Column("reason_code", sa.String(), nullable=False),
        sa.Column("stage", sa.String(), nullable=False),
        # Nullable per DR-2's "Modality score, IF CALCULATED": an upload
        # rejected at admission never reached the embedder.
        sa.Column("modality_score", sa.Float(), nullable=True),
        sa.Column("raw_sha256", sa.String(), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("declared_extension", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    # Indexed because both are lookup keys for the questions this table
    # exists to answer: "what has this doctor been rejected for" and
    # DR-2's own "finds repeated attempts" (the same file, re-uploaded).
    op.create_index(op.f("ix_upload_rejection_log_doctor_id"), "upload_rejection_log", ["doctor_id"])
    op.create_index(op.f("ix_upload_rejection_log_raw_sha256"), "upload_rejection_log", ["raw_sha256"])


def downgrade() -> None:
    op.drop_index(op.f("ix_upload_rejection_log_raw_sha256"), table_name="upload_rejection_log")
    op.drop_index(op.f("ix_upload_rejection_log_doctor_id"), table_name="upload_rejection_log")
    op.drop_table("upload_rejection_log")

    with op.batch_alter_table("reports") as batch_op:
        batch_op.drop_column("top1_similarity")
        batch_op.drop_column("retrieval_support")
