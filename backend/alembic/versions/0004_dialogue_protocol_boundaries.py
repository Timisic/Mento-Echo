"""dialogue protocol boundaries

Revision ID: 0004_dialogue_protocol
Revises: 0003_admin_export
Create Date: 2026-05-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_dialogue_protocol"
down_revision = "0003_admin_export"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("experiment_sessions", sa.Column("dialogue_finish_decision", sa.String(length=64), nullable=True))
    op.add_column(
        "experiment_sessions", sa.Column("dialogue_finish_decision_turn_count", sa.Integer(), nullable=True)
    )
    op.add_column("experiment_sessions", sa.Column("dialogue_continue_until_turn_count", sa.Integer(), nullable=True))
    op.add_column(
        "experiment_sessions",
        sa.Column("dialogue_forced_finish_reason", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("experiment_sessions", "dialogue_forced_finish_reason")
    op.drop_column("experiment_sessions", "dialogue_continue_until_turn_count")
    op.drop_column("experiment_sessions", "dialogue_finish_decision_turn_count")
    op.drop_column("experiment_sessions", "dialogue_finish_decision")
