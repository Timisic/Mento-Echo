from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.db import database_health, get_session
from app.ai_provider import prompt_for_group
from app.models import AuditLog, BehaviorEvent, ChatMessage, ExperimentSession, Participant, QuestionnaireScore
from app.questionnaire_config import QUESTIONNAIRE_VERSION, SCALE_PROFILES
from app.schemas import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminStatusResponse,
    AssignmentResponse,
    AuditLogResponse,
    BehaviorEventResponse,
    ChatMessageResponse,
    DialogueProgressResponse,
    DialogueStateResponse,
    FinishDialogueResponse,
    ParticipantEntryRequest,
    ParticipantEntryResponse,
    ParticipantImportRequest,
    ParticipantImportResponse,
    QuestionnaireDefinitionResponse,
    QuestionnaireItemResponse,
    QuestionnaireScoreResponse,
    QuestionnaireSubmitRequest,
    QuestionnaireSubmitResponse,
    ResetQuestionnaireRequest,
    ScaleProfileResponse,
    SendMessageRequest,
    SendMessageResponse,
    TransitionRequest,
)
from app.services import (
    DialogueService,
    ExperimentSessionService,
    GroupAssignmentService,
    ParticipantRegistryService,
    QuestionnaireService,
    log_audit,
    to_session_response,
    to_status_row,
)

settings = get_settings()
app = FastAPI(title="Mentor Echo API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_admin(authorization: str | None = Header(default=None)) -> str:
    expected = f"Bearer {get_settings().admin_token}"
    if authorization != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin token required")
    return get_settings().admin_username


@app.get("/api/health/live")
def live_health() -> dict[str, str]:
    return {"app": "ok"}


@app.get("/api/health")
def health() -> dict[str, object]:
    return {"app": "ok", "database": database_health()}


@app.post("/api/admin/login", response_model=AdminLoginResponse)
def admin_login(payload: AdminLoginRequest, db: Session = Depends(get_session)) -> AdminLoginResponse:
    settings = get_settings()
    if payload.username != settings.admin_username or payload.password != settings.admin_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    log_audit(
        db,
        admin_id=settings.admin_username,
        action="admin_login",
        target_type="admin",
        target_id=settings.admin_username,
    )
    db.commit()
    return AdminLoginResponse(token=settings.admin_token)


@app.post("/api/admin/participants/import", response_model=ParticipantImportResponse)
def import_participants(
    payload: ParticipantImportRequest,
    admin_id: str = Depends(require_admin),
    db: Session = Depends(get_session),
) -> ParticipantImportResponse:
    participants = ParticipantRegistryService.import_participants(
        db,
        admin_id=admin_id,
        rows=[row.model_dump() for row in payload.participants],
    )
    return ParticipantImportResponse(
        imported_count=len(participants),
        participant_codes=[participant.participant_code for participant in participants],
    )


@app.get("/api/admin/status", response_model=AdminStatusResponse)
def admin_status(
    _: str = Depends(require_admin),
    db: Session = Depends(get_session),
) -> AdminStatusResponse:
    participants = db.scalars(
        select(Participant)
        .options(selectinload(Participant.experiment_session))
        .order_by(Participant.participant_code)
    ).all()
    return AdminStatusResponse(participants=[to_status_row(participant) for participant in participants])


@app.post("/api/admin/sessions/{session_id}/transition")
def transition_session(
    session_id: str,
    payload: TransitionRequest,
    admin_id: str = Depends(require_admin),
    db: Session = Depends(get_session),
) -> dict[str, object]:
    session = db.get(ExperimentSession, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment Session not found")
    try:
        ExperimentSessionService.transition(db, session=session, next_status=payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    log_audit(
        db,
        admin_id=admin_id,
        action="session_transition",
        target_type="experiment_session",
        target_id=session.id,
        reason=payload.reason,
        metadata={"status": payload.status},
    )
    db.commit()
    return {"experiment_session_id": session.id, "status": session.status}


@app.get("/api/admin/audit-logs", response_model=list[AuditLogResponse])
def audit_logs(
    _: str = Depends(require_admin), db: Session = Depends(get_session)
) -> list[AuditLogResponse]:
    logs = db.scalars(select(AuditLog).order_by(AuditLog.created_at)).all()
    return [
        AuditLogResponse(
            id=log.id,
            admin_id=log.admin_id,
            action=log.action,
            target_type=log.target_type,
            target_id=log.target_id,
            reason=log.reason,
            metadata=log.audit_metadata,
            created_at=log.created_at,
        )
        for log in logs
    ]


@app.get("/api/admin/behavior-events", response_model=list[BehaviorEventResponse])
def behavior_events(
    _: str = Depends(require_admin), db: Session = Depends(get_session)
) -> list[BehaviorEventResponse]:
    events = db.scalars(select(BehaviorEvent).order_by(BehaviorEvent.created_at)).all()
    return [
        BehaviorEventResponse(
            id=event.id,
            event_type=event.event_type,
            participant_code=event.participant_code,
            stage=event.stage,
            metadata=event.event_metadata,
            created_at=event.created_at,
        )
        for event in events
    ]


@app.post("/api/participant/entry", response_model=ParticipantEntryResponse)
def participant_entry(
    payload: ParticipantEntryRequest, db: Session = Depends(get_session)
) -> ParticipantEntryResponse:
    participant, session, created = ExperimentSessionService.enter_participant_code(
        db, participant_code=payload.participant_code
    )
    return ParticipantEntryResponse(
        accepted=True,
        message="Experiment Session created." if created else "Experiment Session resumed.",
        session=to_session_response(participant, session),
    )


@app.post("/api/participant/sessions/{session_id}/assignment", response_model=AssignmentResponse)
def create_or_get_assignment(session_id: str, db: Session = Depends(get_session)) -> AssignmentResponse:
    session = db.get(ExperimentSession, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment Session not found")
    session = GroupAssignmentService.ensure_assignment(db, session=session)
    participant = db.get(Participant, session.participant_id)
    assert participant is not None
    return AssignmentResponse(
        experiment_session_id=session.id,
        participant_code=participant.participant_code,
        group=session.group,
        assignment_source=session.assignment_source,
        assignment_locked=session.assignment_locked,
    )


def _get_session_and_participant(db: Session, session_id: str) -> tuple[ExperimentSession, Participant]:
    session = db.get(ExperimentSession, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment Session not found")
    participant = db.get(Participant, session.participant_id)
    if participant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")
    return session, participant


def _scale_response(scale_key: str) -> ScaleProfileResponse:
    scale = SCALE_PROFILES[scale_key]
    return ScaleProfileResponse(
        key=scale.key,
        value_type=scale.value_type,
        min_value=scale.min_value,
        max_value=scale.max_value,
        labels=scale.labels,
        options=list(scale.options),
    )


def _score_response(score: QuestionnaireScore) -> QuestionnaireScoreResponse:
    return QuestionnaireScoreResponse(
        instrument=score.instrument,
        dimension=score.dimension,
        score=score.score,
        valid_items=score.valid_items,
        missing_items=list(score.missing_items),
        attention_check_passed=score.attention_check_passed,
    )


def _chat_message_response(message: ChatMessage) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=message.id,
        message_index=message.message_index,
        role=message.role,
        content=message.content,
        provider_name=message.provider_name,
        model_name=message.model_name,
        system_prompt_version=message.system_prompt_version,
        generation_params=message.generation_params,
        duration_ms=message.duration_ms,
        retry_count=message.retry_count,
        error_code=message.error_code,
        error_message_sanitized=message.error_message_sanitized,
        created_at=message.created_at,
    )


def _progress_response(progress: dict[str, object]) -> DialogueProgressResponse:
    return DialogueProgressResponse(
        participant_turn_count=int(progress["participant_turn_count"]),
        dialogue_elapsed_seconds=int(progress["dialogue_elapsed_seconds"]),
        met_min_turns=bool(progress["met_min_turns"]),
        met_min_duration=bool(progress["met_min_duration"]),
        eligible_to_finish=bool(progress["eligible_to_finish"]),
        required_participant_turns=DialogueService.MIN_PARTICIPANT_TURNS,
        required_elapsed_seconds=DialogueService.MIN_ELAPSED_SECONDS,
    )


@app.get("/api/participant/sessions/{session_id}/questionnaires/{phase}", response_model=QuestionnaireDefinitionResponse)
def questionnaire_definition(session_id: str, phase: str, db: Session = Depends(get_session)) -> QuestionnaireDefinitionResponse:
    if phase not in {"pre", "post"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown questionnaire phase")
    session, _participant = _get_session_and_participant(db, session_id)
    if phase == "post" and session.status != "chat_completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Post-survey is available only after dialogue completion")
    if phase == "pre" and session.status not in {"not_started", "reset_required"} and not QuestionnaireService.active_responses(db, session_id=session.id, phase="pre"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pre-survey is not available")
    items = QuestionnaireService.get_definition(phase)  # type: ignore[arg-type]
    locked = bool(QuestionnaireService.active_responses(db, session_id=session.id, phase=phase))  # type: ignore[arg-type]
    used_scales = {item.scale for item in items}
    return QuestionnaireDefinitionResponse(
        questionnaire_version=QUESTIONNAIRE_VERSION,
        phase=phase,  # type: ignore[arg-type]
        locked=locked,
        items=[
            QuestionnaireItemResponse(
                phase=item.phase,
                order=item.order,
                item_key=item.item_key,
                item_text=item.item_text,
                item_type=item.item_type,
                scale=item.scale,
                instrument=item.instrument,
                dimension=item.dimension,
                reverse_scored=item.reverse_scored,
                required=item.required,
                attention_check=item.attention_check,
            )
            for item in items
        ],
        scales={scale_key: _scale_response(scale_key) for scale_key in sorted(used_scales)},
    )


@app.post("/api/participant/sessions/{session_id}/questionnaires/{phase}/submit", response_model=QuestionnaireSubmitResponse)
def submit_questionnaire(
    session_id: str,
    phase: str,
    payload: QuestionnaireSubmitRequest,
    db: Session = Depends(get_session),
) -> QuestionnaireSubmitResponse:
    if phase not in {"pre", "post"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown questionnaire phase")
    session, participant = _get_session_and_participant(db, session_id)
    responses, scores = QuestionnaireService.submit(
        db,
        session=session,
        participant=participant,
        phase=phase,  # type: ignore[arg-type]
        responses=payload.responses,
    )
    return QuestionnaireSubmitResponse(
        phase=phase,  # type: ignore[arg-type]
        questionnaire_version=QUESTIONNAIRE_VERSION,
        locked=True,
        response_count=len(responses),
        scores=[_score_response(score) for score in scores],
        session=to_session_response(participant, session),
    )


@app.post("/api/admin/sessions/{session_id}/questionnaires/{phase}/reset")
def reset_questionnaire(
    session_id: str,
    phase: str,
    payload: ResetQuestionnaireRequest,
    admin_id: str = Depends(require_admin),
    db: Session = Depends(get_session),
) -> dict[str, object]:
    if phase not in {"pre", "post"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown questionnaire phase")
    session, participant = _get_session_and_participant(db, session_id)
    QuestionnaireService.reset_phase(
        db,
        session=session,
        participant=participant,
        phase=phase,  # type: ignore[arg-type]
        admin_id=admin_id,
        reason=payload.reason,
    )
    return {"experiment_session_id": session.id, "phase": phase, "reset": True}


@app.get("/api/participant/sessions/{session_id}/dialogue", response_model=DialogueStateResponse)
def get_dialogue(session_id: str, db: Session = Depends(get_session)) -> DialogueStateResponse:
    session, participant = _get_session_and_participant(db, session_id)
    messages = DialogueService.start_or_get(db, session=session, participant=participant)
    progress = DialogueService.update_progress(db, session=session)
    db.commit()
    prompt = prompt_for_group(session.group or "")
    return DialogueStateResponse(
        experiment_session_id=session.id,
        participant_code=participant.participant_code,
        group=session.group,  # type: ignore[arg-type]
        system_prompt_version=prompt.version,
        status=session.status,
        progress=_progress_response(progress),
        messages=[_chat_message_response(message) for message in messages],
    )


@app.post("/api/participant/sessions/{session_id}/dialogue/messages", response_model=SendMessageResponse)
def send_dialogue_message(
    session_id: str,
    payload: SendMessageRequest,
    db: Session = Depends(get_session),
) -> SendMessageResponse:
    session, participant = _get_session_and_participant(db, session_id)
    participant_message, assistant_message = DialogueService.send_message(
        db, session=session, participant=participant, content=payload.content
    )
    progress = DialogueService.update_progress(db, session=session)
    db.commit()
    return SendMessageResponse(
        participant_message=_chat_message_response(participant_message),
        assistant_message=_chat_message_response(assistant_message),
        progress=_progress_response(progress),
        status=session.status,
    )


@app.post("/api/participant/sessions/{session_id}/dialogue/finish", response_model=FinishDialogueResponse)
def finish_dialogue(session_id: str, db: Session = Depends(get_session)) -> FinishDialogueResponse:
    session, participant = _get_session_and_participant(db, session_id)
    DialogueService.finish(db, session=session, participant=participant)
    progress = DialogueService.update_progress(db, session=session)
    db.commit()
    return FinishDialogueResponse(status=session.status, progress=_progress_response(progress))
