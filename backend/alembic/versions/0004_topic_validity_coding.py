"""topic validity manual coding fields

Revision ID: 0004_topic_validity
Revises: 0003_admin_export
Create Date: 2026-05-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_topic_validity"
down_revision = "0003_admin_export"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "experiment_sessions",
        sa.Column("topic_off_track_ratio", sa.Float(), nullable=True),
    )
    op.add_column(
        "experiment_sessions",
        sa.Column(
            "topic_validity_status",
            sa.String(length=32),
            nullable=False,
            server_default="pending_manual_coding",
        ),
    )
    op.add_column("experiment_sessions", sa.Column("topic_validity_notes", sa.Text(), nullable=True))
    op.add_column(
        "experiment_sessions",
        sa.Column("topic_validity_coded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column("experiment_sessions", "topic_validity_status", server_default=None)


def downgrade() -> None:
    op.drop_column("experiment_sessions", "topic_validity_coded_at")
    op.drop_column("experiment_sessions", "topic_validity_notes")
    op.drop_column("experiment_sessions", "topic_validity_status")
    op.drop_column("experiment_sessions", "topic_off_track_ratio")
