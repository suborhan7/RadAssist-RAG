"""add doctor_id to retrieval_sessions

Revision ID: 11971c2c9396
Revises: 8550fea2771a
Create Date: 2026-07-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '11971c2c9396'
down_revision: Union[str, Sequence[str], None] = '8550fea2771a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Same two-step pattern as 96e0dd80c317 (patient_id on this same table):
    # add_column/create_index are plain ALTER TABLE ADD COLUMN / CREATE INDEX,
    # which SQLite supports natively -- no batch mode needed for these.
    op.add_column('retrieval_sessions', sa.Column('doctor_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_retrieval_sessions_doctor_id'), 'retrieval_sessions', ['doctor_id'], unique=False)
    # SQLite has no ALTER TABLE ADD CONSTRAINT -- adding a foreign key to an
    # already-existing table requires Alembic's batch mode, same as
    # 96e0dd80c317's patient_id FK. Explicit constraint name (not
    # autogenerate's None) so downgrade can reference it directly.
    with op.batch_alter_table('retrieval_sessions', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_retrieval_sessions_doctor_id_doctors', 'doctors', ['doctor_id'], ['id']
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('retrieval_sessions', schema=None) as batch_op:
        batch_op.drop_constraint('fk_retrieval_sessions_doctor_id_doctors', type_='foreignkey')
    op.drop_index(op.f('ix_retrieval_sessions_doctor_id'), table_name='retrieval_sessions')
    op.drop_column('retrieval_sessions', 'doctor_id')
