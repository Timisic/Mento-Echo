from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ExperimentGroup = Literal["experiment", "control"]
AssignmentSource = Literal["imported", "randomized"]
DialogueFinishDecision = Literal["can_end", "continue_related", "not_core", "early_stop"]
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
    pre_survey_submitted: bool
    post_survey_submitted: bool
    participant_turn_count: int
    dialogue_elapsed_seconds: int
    dialogue_elapsed_minutes: float
    met_min_turns: bool
    met_min_duration: bool
    dialogue_completion_eligible: bool
    dialogue_completed: bool
    completed: bool
    excluded: bool
    exclusion_reason: str | None
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


class ScaleProfileResponse(BaseModel):
    key: str
    value_type: str
    min_value: int | None
    max_value: int | None
    labels: dict[str, str] | None
    options: list[str]


class QuestionnaireItemResponse(BaseModel):
    phase: Literal["pre", "post"]
    order: int
    item_key: str
    item_text: str
    item_type: str
    scale: str
    instrument: str
    dimension: str
    reverse_scored: bool
    required: bool
    attention_check: bool


class QuestionnaireDefinitionResponse(BaseModel):
    questionnaire_version: str
    phase: Literal["pre", "post"]
    locked: bool
    items: list[QuestionnaireItemResponse]
    scales: dict[str, ScaleProfileResponse]


class QuestionnaireSubmitRequest(BaseModel):
    responses: dict[str, int | str]


class QuestionnaireScoreResponse(BaseModel):
    instrument: str
    dimension: str
    score: float | None
    valid_items: int
    missing_items: list[str]
    attention_check_passed: bool | None


class QuestionnaireSubmitResponse(BaseModel):
    phase: Literal["pre", "post"]
    questionnaire_version: str
    locked: bool
    response_count: int
    scores: list[QuestionnaireScoreResponse]
    session: SessionResponse


class ResetQuestionnaireRequest(BaseModel):
    reason: str = Field(min_length=1)


class ExcludeSessionRequest(BaseModel):
    excluded: bool = True
    reason: str = Field(min_length=1)


class ExcludeSessionResponse(BaseModel):
    experiment_session_id: str
    status: SessionStatus
    excluded: bool
    exclusion_reason: str | None


class ChatMessageResponse(BaseModel):
    id: str
    message_index: int
    role: str
    content: str
    provider_name: str | None
    model_name: str | None
    system_prompt_version: str | None
    generation_params: dict[str, object] | None
    duration_ms: int | None
    retry_count: int | None
    error_code: str | None
    error_message_sanitized: str | None
    created_at: datetime


class DialogueProgressResponse(BaseModel):
    participant_turn_count: int
    dialogue_elapsed_seconds: int
    met_min_turns: bool
    met_min_duration: bool
    eligible_to_finish: bool
    required_participant_turns: int
    required_elapsed_seconds: int
    max_participant_turns: int
    max_elapsed_seconds: int
    finish_prompt_visible: bool
    forced_to_finish: bool
    forced_finish_reason: str | None
    finish_decision: str | None
    continue_until_turn_count: int | None
    reminder_due: bool
    reminder_text: str


class DialogueStateResponse(BaseModel):
    experiment_session_id: str
    participant_code: str
    group: ExperimentGroup
    system_prompt_version: str
    status: SessionStatus
    progress: DialogueProgressResponse
    messages: list[ChatMessageResponse]


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1)


class SendMessageResponse(BaseModel):
    participant_message: ChatMessageResponse
    assistant_message: ChatMessageResponse
    progress: DialogueProgressResponse
    status: SessionStatus


class FinishDialogueRequest(BaseModel):
    decision: DialogueFinishDecision = "can_end"


class FinishDialogueResponse(BaseModel):
    status: SessionStatus
    progress: DialogueProgressResponse
