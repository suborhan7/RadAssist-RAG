"""add profile and workspace defaults to doctors

Revision ID: 4da4e9df3c23
Revises: 93de8accdb66
Create Date: 2026-07-17 00:00:03.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4da4e9df3c23'
down_revision: Union[str, Sequence[str], None] = '93de8accdb66'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # All six additive, nullable, self-only (Phase 16 Settings路Profile):
    # bmdc_number (recorded-as-entered, never verified against any
    # registry) plus five per-doctor workspace defaults. Plain ADD COLUMN
    # -- SQLite supports this natively, no batch mode needed (same
    # precedent as every prior nullable-column addition in this project;
    # no FK, no index, since none of these are ever filtered/joined on).
    op.add_column('doctors', sa.Column('bmdc_number', sa.String(), nullable=True))
    op.add_column('doctors', sa.Column('default_top_k', sa.Integer(), nullable=True))
    op.add_column('doctors', sa.Column('default_language', sa.String(), nullable=True))
    op.add_column('doctors', sa.Column('default_questionnaire_skip', sa.Boolean(), nullable=True))
    op.add_column('doctors', sa.Column('default_rail_state', sa.String(), nullable=True))
    op.add_column('doctors', sa.Column('default_export_format', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('doctors', 'default_export_format')
    op.drop_column('doctors', 'default_rail_state')
    op.drop_column('doctors', 'default_questionnaire_skip')
    op.drop_column('doctors', 'default_language')
    op.drop_column('doctors', 'default_top_k')
    op.drop_column('doctors', 'bmdc_number')
