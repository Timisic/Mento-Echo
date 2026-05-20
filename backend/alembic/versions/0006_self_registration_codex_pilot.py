"""self registration codex pilot

Revision ID: 0006_self_reg_codex_pilot
Revises: 0005_dialogue_protocol
Create Date: 2026-05-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_self_reg_codex_pilot"
down_revision = "0005_dialogue_protocol"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "participants",
        sa.Column("registration_source", sa.String(length=32), nullable=False, server_default="imported"),
    )
    op.add_column("experiment_sessions", sa.Column("dialogue_model_thread_id", sa.String(length=128), nullable=True))
    op.add_column("experiment_sessions", sa.Column("dialogue_model_turn_id", sa.String(length=128), nullable=True))
    op.alter_column("participants", "registration_source", server_default=None)


def downgrade() -> None:
    op.drop_column("experiment_sessions", "dialogue_model_turn_id")
    op.drop_column("experiment_sessions", "dialogue_model_thread_id")
    op.drop_column("participants", "registration_source")
