from __future__ import annotations

import hmac
import logging
import threading
import time
from collections import defaultdict, deque

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.ai_provider import AIProviderError
from app.config import get_settings
from app.db import database_health, get_session
from app.export_service import build_export_zip
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
    ExcludeSessionRequest,
    ExcludeSessionResponse,
    FinishDialogueRequest,
    FinishDialogueResponse,
    ParticipantEntryRequest,
    ParticipantEntryResponse,
    ParticipantImportRequest,
    ParticipantImportResponse,
    ParticipantSelfRegisterResponse,
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
    TopicValidityCodingRequest,
    TopicValidityCodingResponse,
)
from app.services import (
    DialogueService,
    ExperimentSessionService,
    GroupAssignmentService,
    ParticipantRegistryService,
    QuestionnaireService,
    log_audit,
    log_behavior,
    to_session_response,
    to_status_row,
)

logger = logging.getLogger(__name__)
settings = get_settings()
app = FastAPI(title="Mentor Echo API", version="0.1.0")


class InMemoryWindowLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, *, limit: int, window_seconds: float, now: float | None = None) -> int | None:
        if limit <= 0 or window_seconds <= 0:
            return None
        now = time.monotonic() if now is None else now
        cutoff = now - window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                retry_after = max(1, int(events[0] + window_seconds - now) + 1)
                return retry_after
            events.append(now)
        return None

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


class AdminLoginFailureTracker:
    def __init__(self) -> None:
        self._failures: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def retry_after(self, key: str, *, max_attempts: int, lockout_seconds: float) -> int | None:
        if max_attempts <= 0 or lockout_seconds <= 0:
            return None
        now = time.monotonic()
        with self._lock:
            count, locked_until = self._failures.get(key, (0, 0.0))
            if count >= max_attempts and locked_until > now:
                return max(1, int(locked_until - now) + 1)
            if locked_until <= now and count >= max_attempts:
                self._failures.pop(key, None)
        return None

    def record_failure(self, key: str, *, max_attempts: int, lockout_seconds: float) -> None:
        if max_attempts <= 0 or lockout_seconds <= 0:
            return
        now = time.monotonic()
        with self._lock:
            count, locked_until = self._failures.get(key, (0, 0.0))
            if locked_until <= now and count >= max_attempts:
                count = 0
            count += 1
            locked_until = now + lockout_seconds if count >= max_attempts else 0.0
            self._failures[key] = (count, locked_until)

    def record_success(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._failures.clear()


_RATE_LIMITER = InMemoryWindowLimiter()
_ADMIN_LOGIN_FAILURES = AdminLoginFailureTracker()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def preserve_cors_headers_for_api_errors(request: Request, call_next):
    security_response = _security_preflight_response(request)
    if security_response is not None:
        _apply_cors_headers(request, security_response)
        _apply_security_headers(security_response)
        return security_response
    response = await call_next(request)
    _apply_cors_headers(request, response)
    _apply_security_headers(response)
    return response


@app.exception_handler(HTTPException)
@app.exception_handler(StarletteHTTPException)
async def http_exception_with_cors(request: Request, exc: HTTPException) -> JSONResponse:
    response = JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )
    _apply_cors_headers(request, response)
    return response


@app.exception_handler(Exception)
async def unhandled_exception_with_cors(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled API exception", exc_info=exc)
    response = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )
    _apply_cors_headers(request, response)
    return response


def _apply_cors_headers(request: Request, response: Response) -> None:
    origin = request.headers.get("origin")
    if origin and _cors_origin_allowed(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"


def _cors_origin_allowed(origin: str) -> bool:
    origins = get_settings().cors_origin_list
    return "*" in origins or origin in origins


def _apply_security_headers(response: Response) -> None:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cache-Control", "no-store")


def _security_preflight_response(request: Request) -> JSONResponse | None:
    settings = get_settings()
    if not _host_allowed(request.headers.get("host", ""), settings.allowed_host_list):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Invalid Host header"},
        )

    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            body_bytes = int(content_length)
        except ValueError:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Invalid Content-Length header"},
            )
        if settings.max_request_body_bytes > 0 and body_bytes > settings.max_request_body_bytes:
            return JSONResponse(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                content={"detail": "Request body too large"},
            )

    retry_after = _rate_limit_retry_after(request)
    if retry_after is not None:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Too many requests"},
            headers={"Retry-After": str(retry_after)},
        )
    return None


def _host_allowed(host_header: str, allowed_hosts: list[str]) -> bool:
    if not allowed_hosts or "*" in allowed_hosts:
        return True
    host = host_header.strip().lower()
    if not host:
        return False
    host_without_port = host
    if host.startswith("[") and "]" in host:
        host_without_port = host[1 : host.index("]")]
    elif host.count(":") == 1:
        host_without_port = host.rsplit(":", 1)[0]
    normalized_allowed = {allowed.lower() for allowed in allowed_hosts}
    return host in normalized_allowed or host_without_port in normalized_allowed


def _client_ip(request: Request) -> str:
    settings = get_settings()
    if settings.trust_proxy_headers:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",", 1)[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
    if request.client is None:
        return "unknown"
    return request.client.host


def _rate_limit_retry_after(request: Request) -> int | None:
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return None
    category, limit = _rate_limit_category_and_limit(request.url.path, settings)
    key = f"{category}:{_client_ip(request)}"
    return _RATE_LIMITER.check(key, limit=limit, window_seconds=settings.rate_limit_window_seconds)


def _rate_limit_category_and_limit(path: str, settings) -> tuple[str, int]:
    if path == "/api/admin/login":
        return "admin-login", settings.rate_limit_admin_login_per_minute
    if path.startswith("/api/admin"):
        return "admin", settings.rate_limit_admin_per_minute
    if path.startswith("/api/participant/sessions/") and path.endswith("/dialogue/messages"):
        return "chat", settings.rate_limit_chat_per_minute
    if path.startswith("/api/participant"):
        return "participant", settings.rate_limit_participant_per_minute
    return "general", settings.rate_limit_general_per_minute


def _admin_login_key(request: Request, username: str) -> str:
    return f"{_client_ip(request)}:{username.strip().lower()}"


def require_admin(authorization: str | None = Header(default=None)) -> str:
    expected = f"Bearer {get_settings().admin_token}"
    if authorization is None or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin token required")
    return get_settings().admin_username


@app.get("/api/health/live")
def live_health() -> dict[str, str]:
    return {"app": "ok"}


@app.get("/api/health")
def health() -> dict[str, object]:
    return {"app": "ok", "database": database_health()}


@app.post("/api/admin/login", response_model=AdminLoginResponse)
def admin_login(
    payload: AdminLoginRequest, request: Request, db: Session = Depends(get_session)
) -> AdminLoginResponse:
    settings = get_settings()
    login_key = _admin_login_key(request, payload.username)
    retry_after = _ADMIN_LOGIN_FAILURES.retry_after(
        login_key,
        max_attempts=settings.admin_login_lockout_attempts,
        lockout_seconds=settings.admin_login_lockout_seconds,
    )
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts",
            headers={"Retry-After": str(retry_after)},
        )
    valid_username = hmac.compare_digest(payload.username, settings.admin_username)
    valid_password = hmac.compare_digest(payload.password, settings.admin_password)
    if not (valid_username and valid_password):
        _ADMIN_LOGIN_FAILURES.record_failure(
            login_key,
            max_attempts=settings.admin_login_lockout_attempts,
            lockout_seconds=settings.admin_login_lockout_seconds,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    _ADMIN_LOGIN_FAILURES.record_success(login_key)
    log_audit(
        db,
        admin_id=settings.admin_username,
        action="admin_login",
        target_type="admin",
        target_id=settings.admin_username,
    )
    db.commit()
    return AdminLoginResponse(token=settings.admin_token)


@app.get("/api/admin/ai-provider/health")
def ai_provider_health(_: str = Depends(require_admin)) -> JSONResponse:
    settings = get_settings()
    try:
        result, primary_error = DialogueService._generate_with_fallback(
            settings=settings,
            system_prompt="",
            history=[{"role": "user", "content": "请只回复：ok"}],
            provider_thread_id=None,
        )
    except AIProviderError as exc:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "ok": False,
                "provider_name": settings.ai_provider_name,
                "model_name": settings.ai_model_name,
                "error_code": exc.code,
                "error_message_sanitized": exc.message,
            },
        )
    return JSONResponse(
        content={
            "ok": True,
            "provider_name": result.provider_name,
            "model_name": result.model_name,
            "duration_ms": result.duration_ms,
            "fallback_triggered": primary_error is not None,
            "primary_error_code": primary_error.code if primary_error else None,
        }
    )


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


@app.post("/api/admin/sessions/{session_id}/exclusion", response_model=ExcludeSessionResponse)
def exclude_session(
    session_id: str,
    payload: ExcludeSessionRequest,
    admin_id: str = Depends(require_admin),
    db: Session = Depends(get_session),
) -> ExcludeSessionResponse:
    session, participant = _get_session_and_participant(db, session_id)
    updated = ExperimentSessionService.mark_exclusion(
        db,
        session=session,
        participant=participant,
        admin_id=admin_id,
        excluded=payload.excluded,
        reason=payload.reason,
    )
    return ExcludeSessionResponse(
        experiment_session_id=updated.id,
        status=updated.status,
        excluded=updated.excluded,
        exclusion_reason=updated.exclusion_reason,
    )


@app.post(
    "/api/admin/sessions/{session_id}/topic-validity",
    response_model=TopicValidityCodingResponse,
)
def record_topic_validity(
    session_id: str,
    payload: TopicValidityCodingRequest,
    admin_id: str = Depends(require_admin),
    db: Session = Depends(get_session),
) -> TopicValidityCodingResponse:
    session, participant = _get_session_and_participant(db, session_id)
    updated = ExperimentSessionService.record_topic_validity(
        db,
        session=session,
        participant=participant,
        admin_id=admin_id,
        off_track_ratio=payload.off_track_ratio,
        notes=payload.notes,
    )
    assert updated.topic_validity_coded_at is not None
    return TopicValidityCodingResponse(
        experiment_session_id=updated.id,
        topic_off_track_ratio=updated.topic_off_track_ratio or 0.0,
        topic_off_track_gt_30pct=bool(
            updated.topic_off_track_ratio is not None and updated.topic_off_track_ratio > 0.30
        ),
        topic_validity_status=updated.topic_validity_status,  # type: ignore[arg-type]
        topic_validity_notes=updated.topic_validity_notes,
        topic_validity_coded_at=updated.topic_validity_coded_at,
        excluded=updated.excluded,
        exclusion_reason=updated.exclusion_reason,
    )


@app.post("/api/admin/export")
def export_package(
    admin_id: str = Depends(require_admin),
    db: Session = Depends(get_session),
) -> Response:
    log_audit(
        db,
        admin_id=admin_id,
        action="data_export_requested",
        target_type="export_package",
    )
    log_behavior(
        db,
        event_type="data_export_requested",
        stage="export",
        metadata={"admin_id": admin_id},
    )
    db.flush()
    log_audit(
        db,
        admin_id=admin_id,
        action="data_export_completed",
        target_type="export_package",
    )
    log_behavior(
        db,
        event_type="data_export_completed",
        stage="export",
        metadata={"admin_id": admin_id},
    )
    db.flush()
    content, filename = build_export_zip(db, admin_id=admin_id)
    db.commit()
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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


@app.post("/api/participant/self-register", response_model=ParticipantSelfRegisterResponse)
def participant_self_register(db: Session = Depends(get_session)) -> ParticipantSelfRegisterResponse:
    participant, session = ParticipantRegistryService.self_register(db)
    return ParticipantSelfRegisterResponse(
        participant_code=participant.participant_code,
        message="Participant code generated. Save it before continuing.",
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
        provider_name=None,
        model_name=None,
        system_prompt_version=None,
        generation_params=None,
        duration_ms=None,
        retry_count=None,
        error_code=None,
        error_message_sanitized=None,
        created_at=message.created_at,
    )


def _generate_assistant_message_background(session_id: str, participant_message_id: str) -> None:
    session_generator = get_session()
    db = next(session_generator)
    try:
        DialogueService.generate_assistant_response(
            db,
            session_id=session_id,
            participant_message_id=participant_message_id,
        )
    except Exception:
        logger.exception("Failed to generate assistant response in background")
    finally:
        session_generator.close()


def _progress_response(progress: dict[str, object]) -> DialogueProgressResponse:
    return DialogueProgressResponse(
        participant_turn_count=int(progress["participant_turn_count"]),
        dialogue_elapsed_seconds=int(progress["dialogue_elapsed_seconds"]),
        met_min_turns=bool(progress["met_min_turns"]),
        met_min_duration=bool(progress["met_min_duration"]),
        eligible_to_finish=bool(progress["eligible_to_finish"]),
        required_participant_turns=DialogueService.MIN_PARTICIPANT_TURNS,
        required_elapsed_seconds=DialogueService.MIN_ELAPSED_SECONDS,
        max_participant_turns=DialogueService.MAX_PARTICIPANT_TURNS,
        max_elapsed_seconds=DialogueService.MAX_ELAPSED_SECONDS,
        finish_prompt_visible=bool(progress["finish_prompt_visible"]),
        forced_to_finish=bool(progress["forced_to_finish"]),
        forced_finish_reason=progress["forced_finish_reason"],  # type: ignore[arg-type]
        finish_decision=progress["finish_decision"],  # type: ignore[arg-type]
        continue_until_turn_count=progress["continue_until_turn_count"],  # type: ignore[arg-type]
        reminder_due=bool(progress["reminder_due"]),
        reminder_text=str(progress["reminder_text"]),
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
    progress = DialogueService.progress_snapshot(db, session=session)
    return DialogueStateResponse(
        experiment_session_id=session.id,
        participant_code=participant.participant_code,
        group=session.group,  # type: ignore[arg-type]
        system_prompt_version=None,
        status=session.status,
        initial_message_suggestion=DialogueService.initial_message_suggestion(db, session=session),
        progress=_progress_response(progress),
        messages=[_chat_message_response(message) for message in messages],
    )


@app.post("/api/participant/sessions/{session_id}/dialogue/messages", response_model=SendMessageResponse)
def send_dialogue_message(
    session_id: str,
    payload: SendMessageRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
) -> SendMessageResponse:
    session, participant = _get_session_and_participant(db, session_id)
    participant_message = DialogueService.send_message(
        db, session=session, participant=participant, content=payload.content
    )
    background_tasks.add_task(_generate_assistant_message_background, session.id, participant_message.id)
    progress = DialogueService.update_progress(db, session=session)
    db.commit()
    return SendMessageResponse(
        participant_message=_chat_message_response(participant_message),
        assistant_message=None,
        progress=_progress_response(progress),
        status=session.status,
    )


@app.post("/api/participant/sessions/{session_id}/dialogue/finish", response_model=FinishDialogueResponse)
def finish_dialogue(
    session_id: str,
    payload: FinishDialogueRequest | None = None,
    db: Session = Depends(get_session),
) -> FinishDialogueResponse:
    session, participant = _get_session_and_participant(db, session_id)
    decision = payload.decision if payload else "can_end"
    DialogueService.finish(db, session=session, participant=participant, decision=decision)
    progress = DialogueService.update_progress(db, session=session)
    db.commit()
    return FinishDialogueResponse(status=session.status, progress=_progress_response(progress))
