from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
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
    excluded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    exclusion_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    excluded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    topic_off_track_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    topic_validity_status: Mapped[str] = mapped_column(
        String(32), default="pending_manual_coding", nullable=False
    )
    topic_validity_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic_validity_coded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    participant_turn_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dialogue_elapsed_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dialogue_finish_decision: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dialogue_finish_decision_turn_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dialogue_continue_until_turn_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dialogue_forced_finish_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resume_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False
    )

    participant: Mapped[Participant] = relationship(back_populates="experiment_session")


class QuestionnaireResponse(Base):
    __tablename__ = "questionnaire_responses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    experiment_session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("experiment_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    participant_code: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    phase: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    questionnaire_version: Mapped[str] = mapped_column(String(128), nullable=False)
    item_key: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    item_text: Mapped[str] = mapped_column(Text, nullable=False)
    item_type: Mapped[str] = mapped_column(String(64), nullable=False)
    scale: Mapped[str] = mapped_column(String(64), nullable=False)
    instrument: Mapped[str] = mapped_column(String(128), nullable=False)
    dimension: Mapped[str] = mapped_column(String(128), nullable=False)
    response_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    reverse_scored: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attention_check: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    locked: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class QuestionnaireScore(Base):
    __tablename__ = "questionnaire_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    experiment_session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("experiment_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    participant_code: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    phase: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    questionnaire_version: Mapped[str] = mapped_column(String(128), nullable=False)
    instrument: Mapped[str] = mapped_column(String(128), nullable=False)
    dimension: Mapped[str] = mapped_column(String(128), nullable=False)
    score: Mapped[float | None] = mapped_column(nullable=True)
    valid_items: Mapped[int] = mapped_column(Integer, nullable=False)
    missing_items: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    attention_check_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    experiment_session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("experiment_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    participant_code: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    message_index: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    provider_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    system_prompt_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    generation_params: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    request_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    response_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message_sanitized: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)


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
