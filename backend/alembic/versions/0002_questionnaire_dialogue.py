"""versioned questionnaire and AI dialogue

Revision ID: 0002_questionnaire_dialogue
Revises: 0001_foundation
Create Date: 2026-05-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_questionnaire_dialogue"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "questionnaire_responses",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("experiment_session_id", sa.String(length=36), nullable=False),
        sa.Column("participant_code", sa.String(length=128), nullable=False),
        sa.Column("phase", sa.String(length=16), nullable=False),
        sa.Column("questionnaire_version", sa.String(length=128), nullable=False),
        sa.Column("item_key", sa.String(length=128), nullable=False),
        sa.Column("item_text", sa.Text(), nullable=False),
        sa.Column("item_type", sa.String(length=64), nullable=False),
        sa.Column("scale", sa.String(length=64), nullable=False),
        sa.Column("instrument", sa.String(length=128), nullable=False),
        sa.Column("dimension", sa.String(length=128), nullable=False),
        sa.Column("response_value", sa.Integer(), nullable=True),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("reverse_scored", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("attention_check", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["experiment_session_id"], ["experiment_sessions.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_questionnaire_responses_session_phase", "questionnaire_responses", ["experiment_session_id", "phase"])
    op.create_index("ix_questionnaire_responses_participant_code", "questionnaire_responses", ["participant_code"])
    op.create_index("ix_questionnaire_responses_item_key", "questionnaire_responses", ["item_key"])

    op.create_table(
        "questionnaire_scores",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("experiment_session_id", sa.String(length=36), nullable=False),
        sa.Column("participant_code", sa.String(length=128), nullable=False),
        sa.Column("phase", sa.String(length=16), nullable=False),
        sa.Column("questionnaire_version", sa.String(length=128), nullable=False),
        sa.Column("instrument", sa.String(length=128), nullable=False),
        sa.Column("dimension", sa.String(length=128), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("valid_items", sa.Integer(), nullable=False),
        sa.Column("missing_items", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("attention_check_passed", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["experiment_session_id"], ["experiment_sessions.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_questionnaire_scores_session_phase", "questionnaire_scores", ["experiment_session_id", "phase"])
    op.create_index("ix_questionnaire_scores_participant_code", "questionnaire_scores", ["participant_code"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("experiment_session_id", sa.String(length=36), nullable=False),
        sa.Column("participant_code", sa.String(length=128), nullable=False),
        sa.Column("message_index", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("provider_name", sa.String(length=128), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("system_prompt_version", sa.String(length=128), nullable=True),
        sa.Column("generation_params", sa.JSON(), nullable=True),
        sa.Column("request_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message_sanitized", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["experiment_session_id"], ["experiment_sessions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("experiment_session_id", "message_index", name="uq_chat_messages_session_index"),
    )
    op.create_index("ix_chat_messages_experiment_session_id", "chat_messages", ["experiment_session_id"])
    op.create_index("ix_chat_messages_participant_code", "chat_messages", ["participant_code"])


def downgrade() -> None:
    op.drop_index("ix_chat_messages_participant_code", table_name="chat_messages")
    op.drop_index("ix_chat_messages_experiment_session_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_questionnaire_scores_participant_code", table_name="questionnaire_scores")
    op.drop_index("ix_questionnaire_scores_session_phase", table_name="questionnaire_scores")
    op.drop_table("questionnaire_scores")
    op.drop_index("ix_questionnaire_responses_item_key", table_name="questionnaire_responses")
    op.drop_index("ix_questionnaire_responses_participant_code", table_name="questionnaire_responses")
    op.drop_index("ix_questionnaire_responses_session_phase", table_name="questionnaire_responses")
    op.drop_table("questionnaire_responses")
