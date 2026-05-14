from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.db import database_health, get_session
from app.models import AuditLog, BehaviorEvent, ExperimentSession, Participant
from app.schemas import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminStatusResponse,
    AssignmentResponse,
    AuditLogResponse,
    BehaviorEventResponse,
    ParticipantEntryRequest,
    ParticipantEntryResponse,
    ParticipantImportRequest,
    ParticipantImportResponse,
    TransitionRequest,
)
from app.services import (
    ExperimentSessionService,
    GroupAssignmentService,
    ParticipantRegistryService,
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
