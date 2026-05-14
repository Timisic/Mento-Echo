from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def uuid_str() -> str:
    return str(uuid.uuid4())


def now_utc() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    participant_code: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    assigned_group: Mapped[str | None] = mapped_column(String(32), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)

    experiment_session: Mapped[ExperimentSession | None] = relationship(
        back_populates="participant", uselist=False, cascade="all, delete-orphan"
    )


class ExperimentSession(Base):
    __tablename__ = "experiment_sessions"
    __table_args__ = (UniqueConstraint("participant_id", name="uq_experiment_sessions_participant_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    participant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("participants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(64), default="not_started", index=True, nullable=False)
    group: Mapped[str | None] = mapped_column(String(32), nullable=True)
    assignment_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    assignment_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    pre_survey_submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    chat_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    chat_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    post_survey_submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    participant_turn_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dialogue_elapsed_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resume_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False
    )

    participant: Mapped[Participant] = relationship(back_populates="experiment_session")


class BehaviorEvent(Base):
    __tablename__ = "behavior_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    event_type: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    participant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("participants.id", ondelete="SET NULL"), nullable=True
    )
    experiment_session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("experiment_sessions.id", ondelete="SET NULL"), nullable=True
    )
    participant_code: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    admin_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    audit_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
