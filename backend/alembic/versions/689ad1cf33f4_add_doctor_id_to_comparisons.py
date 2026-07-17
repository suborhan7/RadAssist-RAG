"""add doctor_id to comparisons

Revision ID: 689ad1cf33f4
Revises: 11971c2c9396
Create Date: 2026-07-17 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '689ad1cf33f4'
down_revision: Union[str, Sequence[str], None] = '11971c2c9396'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('comparisons', sa.Column('doctor_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_comparisons_doctor_id'), 'comparisons', ['doctor_id'], unique=False)
    with op.batch_alter_table('comparisons', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_comparisons_doctor_id_doctors', 'doctors', ['doctor_id'], ['id']
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('comparisons', schema=None) as batch_op:
        batch_op.drop_constraint('fk_comparisons_doctor_id_doctors', type_='foreignkey')
    op.drop_index(op.f('ix_comparisons_doctor_id'), table_name='comparisons')
    op.drop_column('comparisons', 'doctor_id')
