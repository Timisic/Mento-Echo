"""foundation participant registry session assignment

Revision ID: 0001_foundation
Revises:
Create Date: 2026-05-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "participants",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("participant_code", sa.String(length=128), nullable=False),
        sa.Column("assigned_group", sa.String(length=32), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("participant_code", name="uq_participants_participant_code"),
    )
    op.create_index("ix_participants_participant_code", "participants", ["participant_code"])

    op.create_table(
        "experiment_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("participant_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("group", sa.String(length=32), nullable=True),
        sa.Column("assignment_source", sa.String(length=32), nullable=True),
        sa.Column("assignment_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pre_survey_submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("chat_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("chat_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("post_survey_submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("participant_turn_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dialogue_elapsed_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resume_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["participant_id"], ["participants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("participant_id", name="uq_experiment_sessions_participant_id"),
    )
    op.create_index("ix_experiment_sessions_participant_id", "experiment_sessions", ["participant_id"])
    op.create_index("ix_experiment_sessions_status", "experiment_sessions", ["status"])

    op.create_table(
        "behavior_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("participant_id", sa.String(length=36), nullable=True),
        sa.Column("experiment_session_id", sa.String(length=36), nullable=True),
        sa.Column("participant_code", sa.String(length=128), nullable=True),
        sa.Column("stage", sa.String(length=64), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["participant_id"], ["participants.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["experiment_session_id"], ["experiment_sessions.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_behavior_events_event_type", "behavior_events", ["event_type"])
    op.create_index("ix_behavior_events_participant_code", "behavior_events", ["participant_code"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("admin_id", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.String(length=128), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_behavior_events_participant_code", table_name="behavior_events")
    op.drop_index("ix_behavior_events_event_type", table_name="behavior_events")
    op.drop_table("behavior_events")
    op.drop_index("ix_experiment_sessions_status", table_name="experiment_sessions")
    op.drop_index("ix_experiment_sessions_participant_id", table_name="experiment_sessions")
    op.drop_table("experiment_sessions")
    op.drop_index("ix_participants_participant_code", table_name="participants")
    op.drop_table("participants")
