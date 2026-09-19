"""add voted_labels and agreement to reports (S7)

Revision ID: c3d81b6a4f27
Revises: a1f4c72b9e30
Create Date: 2026-08-18 02:00:00.000000

Requirement S7 of docs/methodology/input_admission_projection_gate_
architecture_v1.1_FROZEN.md §7.3, and decision D4.

Why this migration exists
-------------------------
D4 requires `voted_labels` and `agreement` to be stored at generation
time, for the same reason S5 requires the retrieval support category and
the top-1 similarity to be: the evidence state must not change after the
report exists.

Version 1.0 of the architecture assumed a "D4 migration" already existed.
It did not, and no `voted_labels` or `agreement` column was ever created.
Migration a1f4c72b9e30 (17 August 2026) stored `retrieval_support` and
`top1_similarity` only, which left the evidence snapshot half written --
§7.3's Warning states the consequence plainly: the disclaimer reads two
signals, only one was stored, so nobody could show which disclaimer a
doctor signed, and the state *appeared* reproducible without being so.

S7 says to write a NEW gated migration and not to modify a1f4c72b9e30
because it is applied. a1f4c72b9e30 is untouched; this revision chains
off it.

Column choices
--------------
`voted_labels` is JSON, not a scalar: LabelVotingService returns the full
descending-sorted list of VotedLabel(label, vote_weight, agreement) for
every label present across the retrieved cases, and the disclaimer, the
validator and the frontend all read different parts of it. Storing only
the top label would leave the same half-written snapshot one level down.

`agreement` is a separate Float even though it is derivable from
`voted_labels[0]`. D4 names both, they are queried differently (one is a
filterable scalar, one is a document), and the frontend's known
re-derivation defect is exactly what happens when a consumer has to dig a
number out of a nested structure itself.

Both nullable with NO backfill, following the precedent of a1f4c72b9e30
and 528c741665ee: NULL means "this report predates the evidence
snapshot, its real vote is genuinely unknown". It does not mean "no
labels were voted", and no read path may treat it as an empty vote.
There is no honest value to backfill -- recomputing a vote for an old
report would query today's index, which is not what that report was
generated from.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d81b6a4f27"
down_revision: Union[str, Sequence[str], None] = "a1f4c72b9e30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("reports") as batch_op:
        batch_op.add_column(sa.Column("voted_labels", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("agreement", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("reports") as batch_op:
        batch_op.drop_column("agreement")
        batch_op.drop_column("voted_labels")
