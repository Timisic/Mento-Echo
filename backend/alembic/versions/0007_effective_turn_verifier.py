"""effective turn verifier metadata

Revision ID: 0007_effective_turn_verifier
Revises: 0006_self_reg_codex_pilot
Create Date: 2026-05-25
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007_effective_turn_verifier"
down_revision = "0006_self_reg_codex_pilot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("effective_turn_label", sa.Integer(), nullable=True))
    op.add_column("chat_messages", sa.Column("effective_turn_source", sa.String(length=64), nullable=True))
    op.add_column("chat_messages", sa.Column("effective_turn_excluded_reason", sa.String(length=128), nullable=True))
    op.add_column("chat_messages", sa.Column("effective_turn_verifier_provider", sa.String(length=128), nullable=True))
    op.add_column("chat_messages", sa.Column("effective_turn_verifier_model", sa.String(length=128), nullable=True))
    op.add_column("chat_messages", sa.Column("effective_turn_verifier_prompt_version", sa.String(length=128), nullable=True))
    op.add_column("chat_messages", sa.Column("effective_turn_verifier_response", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_messages", "effective_turn_verifier_response")
    op.drop_column("chat_messages", "effective_turn_verifier_prompt_version")
    op.drop_column("chat_messages", "effective_turn_verifier_model")
    op.drop_column("chat_messages", "effective_turn_verifier_provider")
    op.drop_column("chat_messages", "effective_turn_excluded_reason")
    op.drop_column("chat_messages", "effective_turn_source")
    op.drop_column("chat_messages", "effective_turn_label")
