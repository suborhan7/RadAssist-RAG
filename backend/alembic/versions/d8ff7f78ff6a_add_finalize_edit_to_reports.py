"""add finalize/edit to reports

Revision ID: d8ff7f78ff6a
Revises: 4da4e9df3c23
Create Date: 2026-07-17 00:00:04.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8ff7f78ff6a'
down_revision: Union[str, Sequence[str], None] = '4da4e9df3c23'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Rename ai_content -> ai_draft_content. ai_content already IS the
    # immutable AI draft (nothing has ever updated it post-insert) -- this
    # names it correctly rather than adding a duplicate column. SQLite
    # RENAME COLUMN needs batch mode in this Alembic setup, same as every
    # other constraint-adjacent SQLite operation in this project.
    with op.batch_alter_table('reports', schema=None) as batch_op:
        batch_op.alter_column('ai_content', new_column_name='ai_draft_content')

    # 2. Add final_content nullable first (plain ADD COLUMN -- no FK, no
    # NOT NULL yet, since existing rows need a backfill value before this
    # can be enforced).
    op.add_column('reports', sa.Column('final_content', sa.JSON(), nullable=True))

    # 3. Backfill: final_content = ai_draft_content for every existing row.
    # Both columns are TEXT-backed JSON in SQLite, so a direct column-to-
    # column copy is a safe, exact byte-for-byte copy -- no need to parse
    # and re-serialize.
    op.execute("UPDATE reports SET final_content = ai_draft_content")

    # 4. Now enforce NOT NULL on final_content (batch mode needed for a
    # constraint change in SQLite, same as every other constraint-altering
    # step in this project).
    with op.batch_alter_table('reports', schema=None) as batch_op:
        batch_op.alter_column('final_content', nullable=False)

    # 5. finalized_at -- nullable, plain ADD COLUMN.
    op.add_column('reports', sa.Column('finalized_at', sa.DateTime(), nullable=True))

    # 6. finalized_by -- nullable FK to doctors.id. Add the column first,
    # then the FK constraint in batch mode (SQLite has no ALTER TABLE ADD
    # CONSTRAINT -- confirmed empirically in Phase 13a/15/16, same pattern
    # reused here).
    op.add_column('reports', sa.Column('finalized_by', sa.Uuid(), nullable=True))
    with op.batch_alter_table('reports', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_reports_finalized_by_doctors', 'doctors', ['finalized_by'], ['id']
        )

    # 7. report_audit_log -- brand-new table, plain create_table, no batch
    # mode needed (same reasoning as every other new table in this
    # project: nothing pre-exists to alter). Append-only by convention
    # (enforced at the service layer, not a DB constraint) -- INSERT only,
    # no UPDATE, no DELETE, ever.
    op.create_table(
        'report_audit_log',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('report_id', sa.Uuid(), nullable=False),
        sa.Column('doctor_id', sa.Uuid(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['report_id'], ['reports.id']),
        sa.ForeignKeyConstraint(['doctor_id'], ['doctors.id']),
    )
    op.create_index(op.f('ix_report_audit_log_report_id'), 'report_audit_log', ['report_id'])
    op.create_index(op.f('ix_report_audit_log_doctor_id'), 'report_audit_log', ['doctor_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_report_audit_log_doctor_id'), table_name='report_audit_log')
    op.drop_index(op.f('ix_report_audit_log_report_id'), table_name='report_audit_log')
    op.drop_table('report_audit_log')

    with op.batch_alter_table('reports', schema=None) as batch_op:
        batch_op.drop_constraint('fk_reports_finalized_by_doctors', type_='foreignkey')
    op.drop_column('reports', 'finalized_by')
    op.drop_column('reports', 'finalized_at')

    with op.batch_alter_table('reports', schema=None) as batch_op:
        batch_op.alter_column('final_content', nullable=True)
    op.drop_column('reports', 'final_content')

    with op.batch_alter_table('reports', schema=None) as batch_op:
        batch_op.alter_column('ai_draft_content', new_column_name='ai_content')
