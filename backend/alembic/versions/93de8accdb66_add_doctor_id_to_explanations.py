"""add doctor_id to explanations

Revision ID: 93de8accdb66
Revises: 689ad1cf33f4
Create Date: 2026-07-17 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '93de8accdb66'
down_revision: Union[str, Sequence[str], None] = '689ad1cf33f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('explanations', sa.Column('doctor_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_explanations_doctor_id'), 'explanations', ['doctor_id'], unique=False)
    with op.batch_alter_table('explanations', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_explanations_doctor_id_doctors', 'doctors', ['doctor_id'], ['id']
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('explanations', schema=None) as batch_op:
        batch_op.drop_constraint('fk_explanations_doctor_id_doctors', type_='foreignkey')
    op.drop_index(op.f('ix_explanations_doctor_id'), table_name='explanations')
    op.drop_column('explanations', 'doctor_id')
