from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ExperimentGroup = Literal["experiment", "control"]
AssignmentSource = Literal["imported", "randomized"]
SessionStatus = Literal[
    "not_started",
    "pre_survey_submitted",
    "chat_in_progress",
    "chat_eligible_to_finish",
    "chat_completed",
    "completed",
    "reset_required",
    "excluded",
]


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    token: str
    token_type: str = "bearer"


class ParticipantImportRow(BaseModel):
    participant_code: str = Field(min_length=1)
    assigned_group: str | None = None


class ParticipantImportRequest(BaseModel):
    participants: list[ParticipantImportRow] = Field(min_length=1)


class ParticipantImportError(BaseModel):
    row: int
    participant_code: str | None = None
    message: str


class ParticipantImportResponse(BaseModel):
    imported_count: int
    participant_codes: list[str]


class ParticipantEntryRequest(BaseModel):
    participant_code: str = Field(min_length=1)


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    experiment_session_id: str
    participant_code: str
    status: SessionStatus
    group: ExperimentGroup | None
    assignment_source: AssignmentSource | None
    assignment_locked: bool
    resume_count: int
    last_seen_at: datetime | None
    started_at: datetime
    completed_at: datetime | None


class ParticipantEntryResponse(BaseModel):
    accepted: bool
    message: str
    session: SessionResponse


class AssignmentResponse(BaseModel):
    experiment_session_id: str
    participant_code: str
    group: ExperimentGroup
    assignment_source: AssignmentSource
    assignment_locked: bool


class StatusRow(BaseModel):
    participant_code: str
    assigned_group_imported: ExperimentGroup | None
    experiment_session_id: str | None
    status: SessionStatus
    group: ExperimentGroup | None
    assignment_source: AssignmentSource | None
    assignment_locked: bool
    started_at: datetime | None
    pre_survey_submitted_at: datetime | None
    chat_started_at: datetime | None
    chat_completed_at: datetime | None
    post_survey_submitted_at: datetime | None
    completed_at: datetime | None
    participant_turn_count: int
    dialogue_elapsed_seconds: int
    resume_count: int
    last_seen_at: datetime | None


class AdminStatusResponse(BaseModel):
    participants: list[StatusRow]


class TransitionRequest(BaseModel):
    status: SessionStatus
    reason: str | None = None


class AuditLogResponse(BaseModel):
    id: str
    admin_id: str
    action: str
    target_type: str | None
    target_id: str | None
    reason: str | None
    metadata: dict[str, object]
    created_at: datetime


class BehaviorEventResponse(BaseModel):
    id: str
    event_type: str
    participant_code: str | None
    stage: str | None
    metadata: dict[str, object]
    created_at: datetime
