"""admin exclusion and export readiness fields

Revision ID: 0003_admin_export
Revises: 0002_questionnaire_dialogue
Create Date: 2026-05-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_admin_export"
down_revision = "0002_questionnaire_dialogue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "experiment_sessions",
        sa.Column("excluded", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("experiment_sessions", sa.Column("exclusion_reason", sa.Text(), nullable=True))
    op.add_column("experiment_sessions", sa.Column("excluded_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("experiment_sessions", "excluded", server_default=None)


def downgrade() -> None:
    op.drop_column("experiment_sessions", "excluded_at")
    op.drop_column("experiment_sessions", "exclusion_reason")
    op.drop_column("experiment_sessions", "excluded")
