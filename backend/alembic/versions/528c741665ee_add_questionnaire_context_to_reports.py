"""add questionnaire context to reports

Revision ID: 528c741665ee
Revises: d8ff7f78ff6a
Create Date: 2026-07-18 12:41:04.793106

Phase 19 Decision 4's resolution: questionnaire_answers/clinical_notes
were only ever request-body parameters passed transiently into
ReportGenerationService.generate() -- never persisted anywhere -- so an
existing report's original generation context could not be fully
reconstructed. Both are nullable, deliberately with NO backfill: NULL on
every pre-existing row is the semantically correct value here (it means
"this report predates context capture, the real answer is genuinely
unknown"), not a placeholder to be filled in. This is different in kind
from Phase 17's final_content backfill, where a real equivalent value
existed and had to be computed. Going forward, ReportGenerationService.generate()
always writes a real value -- an empty dict or empty string is a real,
known "nothing was provided" answer, distinct from NULL's "we don't know".
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '528c741665ee'
down_revision: Union[str, Sequence[str], None] = 'd8ff7f78ff6a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('reports', sa.Column('questionnaire_answers', sa.JSON(), nullable=True))
    op.add_column('reports', sa.Column('clinical_notes', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('reports', 'clinical_notes')
    op.drop_column('reports', 'questionnaire_answers')
