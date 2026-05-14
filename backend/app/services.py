from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import AuditLog, BehaviorEvent, ExperimentSession, Participant
from app.schemas import SessionResponse, StatusRow

VALID_GROUPS = {"experiment", "control"}
CANONICAL_STATUSES = {
    "not_started",
    "pre_survey_submitted",
    "chat_in_progress",
    "chat_eligible_to_finish",
    "chat_completed",
    "completed",
    "reset_required",
    "excluded",
}
ALLOWED_TRANSITIONS = {
    "not_started": {"pre_survey_submitted", "reset_required", "excluded"},
    "pre_survey_submitted": {"chat_in_progress", "reset_required", "excluded"},
    "chat_in_progress": {"chat_eligible_to_finish", "reset_required", "excluded"},
    "chat_eligible_to_finish": {"chat_completed", "reset_required", "excluded"},
    "chat_completed": {"completed", "reset_required", "excluded"},
    "completed": {"reset_required", "excluded"},
    "reset_required": {"not_started", "excluded"},
    "excluded": set(),
}


def now_utc() -> datetime:
    return datetime.now(UTC)


def normalize_participant_code(raw: str) -> str:
    return " ".join(raw.strip().upper().split())


def normalize_group(raw: str | None) -> str | None:
    if raw is None:
        return None
    normalized = raw.strip().lower()
    return normalized or None


def log_audit(
    db: Session,
    *,
    admin_id: str,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    reason: str | None = None,
    metadata: dict[str, object] | None = None,
) -> AuditLog:
    audit = AuditLog(
        admin_id=admin_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        reason=reason,
        audit_metadata=metadata or {},
    )
    db.add(audit)
    return audit


def log_behavior(
    db: Session,
    *,
    event_type: str,
    participant: Participant | None = None,
    session: ExperimentSession | None = None,
    participant_code: str | None = None,
    stage: str | None = None,
    metadata: dict[str, object] | None = None,
) -> BehaviorEvent:
    event = BehaviorEvent(
        event_type=event_type,
        participant_id=participant.id if participant else None,
        experiment_session_id=session.id if session else None,
        participant_code=participant_code or (participant.participant_code if participant else None),
        stage=stage,
        event_metadata=metadata or {},
    )
    db.add(event)
    return event


@dataclass(frozen=True)
class ImportValidationError:
    row: int
    participant_code: str | None
    message: str


class ParticipantRegistryService:
    @staticmethod
    def import_participants(
        db: Session,
        *,
        admin_id: str,
        rows: list[dict[str, str | None]],
    ) -> list[Participant]:
        errors: list[ImportValidationError] = []
        normalized_rows: list[tuple[int, str, str | None]] = []
        seen: set[str] = set()

        for index, row in enumerate(rows, start=1):
            code = normalize_participant_code(str(row.get("participant_code") or ""))
            group = normalize_group(row.get("assigned_group"))
            if not code:
                errors.append(ImportValidationError(index, None, "participant_code is required"))
                continue
            if code in seen:
                errors.append(ImportValidationError(index, code, "duplicate participant_code in import"))
                continue
            if group is not None and group not in VALID_GROUPS:
                errors.append(
                    ImportValidationError(index, code, "assigned_group must be experiment, control, or blank")
                )
                continue
            seen.add(code)
            normalized_rows.append((index, code, group))

        if normalized_rows:
            existing = set(
                db.scalars(
                    select(Participant.participant_code).where(
                        Participant.participant_code.in_([code for _, code, _ in normalized_rows])
                    )
                )
            )
            for index, code, _ in normalized_rows:
                if code in existing:
                    errors.append(ImportValidationError(index, code, "participant_code already exists"))

        if errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errors": [error.__dict__ for error in errors]},
            )

        participants = [
            Participant(participant_code=code, assigned_group=group) for _, code, group in normalized_rows
        ]
        db.add_all(participants)
        log_audit(
            db,
            admin_id=admin_id,
            action="participant_import",
            target_type="participant_batch",
            target_id=None,
            metadata={"participant_codes": [p.participant_code for p in participants], "count": len(participants)},
        )
        db.commit()
        for participant in participants:
            db.refresh(participant)
        return participants


class ExperimentSessionService:
    @staticmethod
    def enter_participant_code(db: Session, *, participant_code: str) -> tuple[Participant, ExperimentSession, bool]:
        normalized_code = normalize_participant_code(participant_code)
        participant = db.scalar(
            select(Participant)
            .where(Participant.participant_code == normalized_code)
            .options(selectinload(Participant.experiment_session))
        )
        if participant is None:
            log_behavior(
                db,
                event_type="participant_code_rejected",
                participant_code=normalized_code,
                stage="entry",
                metadata={"reason": "unknown_code"},
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Participant code not recognized. Please contact the researcher.",
            )

        log_behavior(
            db,
            event_type="participant_code_accepted",
            participant=participant,
            stage="entry",
        )
        session = participant.experiment_session
        created = session is None
        if session is None:
            session = ExperimentSession(
                participant_id=participant.id,
                status="not_started",
                started_at=now_utc(),
                last_seen_at=now_utc(),
            )
            db.add(session)
            db.flush()
            log_behavior(
                db,
                event_type="experiment_session_created",
                participant=participant,
                session=session,
                stage="entry",
            )
        else:
            session.last_seen_at = now_utc()
            if session.status != "completed":
                session.resume_count += 1
                log_behavior(
                    db,
                    event_type="experiment_session_resumed",
                    participant=participant,
                    session=session,
                    stage=session.status,
                    metadata={"resume_count": session.resume_count},
                )
            else:
                log_behavior(
                    db,
                    event_type="completed_session_reentered",
                    participant=participant,
                    session=session,
                    stage=session.status,
                )
        db.commit()
        db.refresh(participant)
        db.refresh(session)
        return participant, session, created

    @staticmethod
    def transition(db: Session, *, session: ExperimentSession, next_status: str) -> ExperimentSession:
        if next_status not in CANONICAL_STATUSES:
            raise ValueError(f"Unknown session status: {next_status}")
        if next_status == session.status:
            return session
        allowed = ALLOWED_TRANSITIONS[session.status]
        if next_status not in allowed:
            raise ValueError(f"Invalid transition from {session.status} to {next_status}")
        timestamp = now_utc()
        session.status = next_status
        session.updated_at = timestamp
        if next_status == "pre_survey_submitted":
            session.pre_survey_submitted_at = timestamp
        elif next_status == "chat_in_progress":
            session.chat_started_at = timestamp
        elif next_status == "chat_completed":
            session.chat_completed_at = timestamp
        elif next_status == "completed":
            session.post_survey_submitted_at = session.post_survey_submitted_at or timestamp
            session.completed_at = timestamp
        return session


class GroupAssignmentService:
    @staticmethod
    def ensure_assignment(db: Session, *, session: ExperimentSession) -> ExperimentSession:
        if session.assignment_locked:
            return session
        participant = db.get(Participant, session.participant_id)
        if participant is None:
            raise ValueError("Cannot assign group without participant")
        if participant.assigned_group in VALID_GROUPS:
            group = participant.assigned_group
            source = "imported"
        else:
            group = random.choice(sorted(VALID_GROUPS))
            source = "randomized"
        session.group = group
        session.assignment_source = source
        session.assignment_locked = True
        session.updated_at = now_utc()
        log_behavior(
            db,
            event_type="group_assignment_created",
            participant=participant,
            session=session,
            stage=session.status,
            metadata={"group": group, "assignment_source": source},
        )
        db.commit()
        db.refresh(session)
        return session


def to_session_response(participant: Participant, session: ExperimentSession) -> SessionResponse:
    return SessionResponse(
        experiment_session_id=session.id,
        participant_code=participant.participant_code,
        status=session.status,
        group=session.group,
        assignment_source=session.assignment_source,
        assignment_locked=session.assignment_locked,
        resume_count=session.resume_count,
        last_seen_at=session.last_seen_at,
        started_at=session.started_at,
        completed_at=session.completed_at,
    )


def to_status_row(participant: Participant) -> StatusRow:
    session = participant.experiment_session
    if session is None:
        return StatusRow(
            participant_code=participant.participant_code,
            assigned_group_imported=participant.assigned_group,
            experiment_session_id=None,
            status="not_started",
            group=None,
            assignment_source=None,
            assignment_locked=False,
            started_at=None,
            pre_survey_submitted_at=None,
            chat_started_at=None,
            chat_completed_at=None,
            post_survey_submitted_at=None,
            completed_at=None,
            participant_turn_count=0,
            dialogue_elapsed_seconds=0,
            resume_count=0,
            last_seen_at=None,
        )
    return StatusRow(
        participant_code=participant.participant_code,
        assigned_group_imported=participant.assigned_group,
        experiment_session_id=session.id,
        status=session.status,
        group=session.group,
        assignment_source=session.assignment_source,
        assignment_locked=session.assignment_locked,
        started_at=session.started_at,
        pre_survey_submitted_at=session.pre_survey_submitted_at,
        chat_started_at=session.chat_started_at,
        chat_completed_at=session.chat_completed_at,
        post_survey_submitted_at=session.post_survey_submitted_at,
        completed_at=session.completed_at,
        participant_turn_count=session.participant_turn_count,
        dialogue_elapsed_seconds=session.dialogue_elapsed_seconds,
        resume_count=session.resume_count,
        last_seen_at=session.last_seen_at,
    )
