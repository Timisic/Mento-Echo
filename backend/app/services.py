from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.ai_provider import (
    PROMPTLESS_DIALOGUE_MODE,
    AIProviderError,
    AIProviderResult,
    create_ai_provider,
    sanitize_error_message,
)
from app.config import Settings, get_settings
from app.models import (
    AuditLog,
    BehaviorEvent,
    ChatMessage,
    ExperimentSession,
    Participant,
    QuestionnaireResponse,
    QuestionnaireScore,
)
from app.questionnaire_config import (
    QUESTIONNAIRE_VERSION,
    SCALE_PROFILES,
    Phase,
    QuestionnaireItem,
    get_items,
    score_rules_for_phase,
)
from app.schemas import SessionResponse, StatusRow

VALID_GROUPS = {"pilot", "experiment", "control"}
GROUPED_STUDY_GROUPS = {"experiment", "control"}
SELF_CODE_SUFFIX_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
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


def elapsed_seconds_since(timestamp: datetime) -> int:
    return elapsed_seconds_between(timestamp, now_utc())


def elapsed_seconds_between(start: datetime, end: datetime) -> int:
    start = as_utc(start)
    end = as_utc(end)
    return max(0, int((end - start).total_seconds()))


def as_utc(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)


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
            if group is not None and group not in GROUPED_STUDY_GROUPS:
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
            Participant(participant_code=code, assigned_group=group, registration_source="imported")
            for _, code, group in normalized_rows
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

    @staticmethod
    def self_register(db: Session) -> tuple[Participant, ExperimentSession]:
        settings = get_settings()
        if not settings.self_registration_enabled:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Participant self-registration is disabled")
        participant = ParticipantRegistryService._create_self_generated_participant(db)
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
            event_type="participant_self_registered",
            participant=participant,
            session=session,
            stage="entry",
            metadata={"registration_source": participant.registration_source},
        )
        log_behavior(
            db,
            event_type="experiment_session_created",
            participant=participant,
            session=session,
            stage="entry",
        )
        db.commit()
        db.refresh(participant)
        db.refresh(session)
        return participant, session

    @staticmethod
    def _create_self_generated_participant(db: Session) -> Participant:
        prefix = re.sub(r"[^A-Za-z0-9]", "", get_settings().participant_code_prefix.upper()) or "P"
        for _ in range(20):
            next_number = ParticipantRegistryService._next_self_code_number(db, prefix=prefix)
            suffix = "".join(random.choice(SELF_CODE_SUFFIX_ALPHABET) for _ in range(2))
            code = f"{prefix}{next_number:03d}-{suffix}"
            if db.scalar(select(Participant.id).where(Participant.participant_code == code)):
                continue
            participant = Participant(
                participant_code=code,
                assigned_group=None,
                registration_source="self_generated",
            )
            db.add(participant)
            db.flush()
            return participant
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Could not generate a unique participant code")

    @staticmethod
    def _next_self_code_number(db: Session, *, prefix: str) -> int:
        max_number = ParticipantRegistryService._max_self_code_number_from_participants(db, prefix=prefix)
        max_number = max(
            max_number,
            ParticipantRegistryService._max_self_code_number_from_cleanup_audits(db, prefix=prefix),
        )
        return max_number + 1

    @staticmethod
    def _max_self_code_number_from_participants(db: Session, *, prefix: str) -> int:
        pattern = re.compile(rf"^{re.escape(prefix)}(\d+)-[A-Z0-9]+$")
        max_number = 0
        codes = db.scalars(
            select(Participant.participant_code).where(Participant.participant_code.like(f"{prefix}%-%"))
        )
        for code in codes:
            match = pattern.match(code)
            if match:
                max_number = max(max_number, int(match.group(1)))
        return max_number

    @staticmethod
    def _max_self_code_number_from_cleanup_audits(db: Session, *, prefix: str) -> int:
        max_number = 0
        metadata_rows = db.scalars(
            select(AuditLog.audit_metadata).where(AuditLog.action == "participant_cleanup_under_six_turns")
        )
        for metadata in metadata_rows:
            if not isinstance(metadata, dict):
                continue
            by_prefix = metadata.get("self_registration_high_watermark_by_prefix")
            if not isinstance(by_prefix, dict):
                continue
            value = by_prefix.get(prefix)
            try:
                max_number = max(max_number, int(value))
            except (TypeError, ValueError):
                continue
        return max_number


class ExperimentSessionService:
    TOPIC_EXCLUSION_REASON = "topic_validity_off_track_ratio_gt_30pct"

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

    @staticmethod
    def mark_exclusion(
        db: Session,
        *,
        session: ExperimentSession,
        participant: Participant,
        admin_id: str,
        excluded: bool,
        reason: str,
    ) -> ExperimentSession:
        clean_reason = reason.strip()
        if not clean_reason:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="reason is required")
        timestamp = now_utc()
        session.excluded = excluded
        session.exclusion_reason = clean_reason if excluded else None
        session.excluded_at = timestamp if excluded else None
        if excluded:
            session.status = "excluded"
        elif session.status == "excluded":
            session.status = "reset_required"
        session.updated_at = timestamp
        action = "session_excluded" if excluded else "session_exclusion_cleared"
        log_audit(
            db,
            admin_id=admin_id,
            action=action,
            target_type="experiment_session",
            target_id=session.id,
            reason=clean_reason,
            metadata={"participant_code": participant.participant_code},
        )
        log_behavior(
            db,
            event_type=action,
            participant=participant,
            session=session,
            stage=session.status,
            metadata={"reason": clean_reason},
        )
        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def record_topic_validity(
        db: Session,
        *,
        session: ExperimentSession,
        participant: Participant,
        admin_id: str,
        off_track_ratio: float,
        notes: str | None = None,
    ) -> ExperimentSession:
        timestamp = now_utc()
        off_topic_excluded = off_track_ratio > 0.30
        session.topic_off_track_ratio = off_track_ratio
        session.topic_validity_status = "off_topic_excluded" if off_topic_excluded else "valid"
        session.topic_validity_notes = notes.strip() if notes and notes.strip() else None
        session.topic_validity_coded_at = timestamp
        if off_topic_excluded:
            session.excluded = True
            session.exclusion_reason = ExperimentSessionService.TOPIC_EXCLUSION_REASON
            session.excluded_at = timestamp
            session.status = "excluded"
        elif session.exclusion_reason == ExperimentSessionService.TOPIC_EXCLUSION_REASON:
            session.excluded = False
            session.exclusion_reason = None
            session.excluded_at = None
            session.status = "completed" if session.completed_at else "reset_required"
        session.updated_at = timestamp
        log_audit(
            db,
            admin_id=admin_id,
            action="topic_validity_coded",
            target_type="experiment_session",
            target_id=session.id,
            reason=session.topic_validity_status,
            metadata={
                "participant_code": participant.participant_code,
                "off_track_ratio": off_track_ratio,
                "exclusion_threshold": "> 0.30",
            },
        )
        log_behavior(
            db,
            event_type="topic_validity_coded",
            participant=participant,
            session=session,
            stage=session.status,
            metadata={
                "off_track_ratio": off_track_ratio,
                "topic_validity_status": session.topic_validity_status,
                "exclusion_threshold": "> 0.30",
            },
        )
        db.commit()
        db.refresh(session)
        return session


class GroupAssignmentService:
    @staticmethod
    def ensure_assignment(db: Session, *, session: ExperimentSession) -> ExperimentSession:
        if session.assignment_locked:
            return session
        participant = db.get(Participant, session.participant_id)
        if participant is None:
            raise ValueError("Cannot assign group without participant")
        settings = get_settings()
        if settings.study_mode == "pilot_single":
            group = "pilot"
            source = "pilot_single"
        elif participant.assigned_group in GROUPED_STUDY_GROUPS:
            group = participant.assigned_group
            source = "imported"
        else:
            group = random.choice(sorted(GROUPED_STUDY_GROUPS))
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


class QuestionnaireService:
    @staticmethod
    def get_definition(phase: Phase) -> tuple[QuestionnaireItem, ...]:
        return get_items(phase)

    @staticmethod
    def active_responses(db: Session, *, session_id: str, phase: Phase) -> list[QuestionnaireResponse]:
        return list(
            db.scalars(
                select(QuestionnaireResponse).where(
                    QuestionnaireResponse.experiment_session_id == session_id,
                    QuestionnaireResponse.phase == phase,
                    QuestionnaireResponse.superseded_at.is_(None),
                )
            )
        )

    @staticmethod
    def submit(
        db: Session,
        *,
        session: ExperimentSession,
        participant: Participant,
        phase: Phase,
        responses: dict[str, object],
    ) -> tuple[list[QuestionnaireResponse], list[QuestionnaireScore]]:
        QuestionnaireService._assert_phase_available(session, phase)
        if QuestionnaireService.active_responses(db, session_id=session.id, phase=phase):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{phase}-survey is already submitted and locked",
            )
        items = get_items(phase)
        item_keys = {item.item_key for item in items}
        missing = sorted(key for key in item_keys if key not in responses)
        extra = sorted(key for key in responses if key not in item_keys)
        if missing or extra:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"missing": missing, "extra": extra},
            )
        submitted_at = now_utc()
        stored: list[QuestionnaireResponse] = []
        for item in items:
            response_value, response_text = QuestionnaireService._normalize_response(item, responses[item.item_key])
            row = QuestionnaireResponse(
                experiment_session_id=session.id,
                participant_code=participant.participant_code,
                phase=phase,
                questionnaire_version=QUESTIONNAIRE_VERSION,
                item_key=item.item_key,
                item_text=item.item_text,
                item_type=item.item_type,
                scale=item.scale,
                instrument=item.instrument,
                dimension=item.dimension,
                response_value=response_value,
                response_text=response_text,
                reverse_scored=item.reverse_scored,
                attention_check=item.attention_check,
                locked=True,
                submitted_at=submitted_at,
            )
            db.add(row)
            stored.append(row)
        db.flush()
        scores = QuestionnaireService._compute_scores(
            db, session=session, participant=participant, phase=phase, responses=stored
        )
        if phase == "pre":
            ExperimentSessionService.transition(db, session=session, next_status="pre_survey_submitted")
            GroupAssignmentService.ensure_assignment(db, session=session)
        else:
            ExperimentSessionService.transition(db, session=session, next_status="completed")
        log_behavior(
            db,
            event_type=f"{phase}_survey_submitted",
            participant=participant,
            session=session,
            stage=phase,
            metadata={"questionnaire_version": QUESTIONNAIRE_VERSION},
        )
        db.commit()
        for row in stored:
            db.refresh(row)
        for score in scores:
            db.refresh(score)
        db.refresh(session)
        return stored, scores

    @staticmethod
    def reset_phase(
        db: Session,
        *,
        session: ExperimentSession,
        participant: Participant,
        phase: Phase,
        admin_id: str,
        reason: str,
    ) -> None:
        if not reason.strip():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="reason is required")
        timestamp = now_utc()
        for row in QuestionnaireService.active_responses(db, session_id=session.id, phase=phase):
            row.locked = False
            row.superseded_at = timestamp
        for score in db.scalars(
            select(QuestionnaireScore).where(
                QuestionnaireScore.experiment_session_id == session.id,
                QuestionnaireScore.phase == phase,
                QuestionnaireScore.superseded_at.is_(None),
            )
        ):
            score.superseded_at = timestamp
        if phase == "pre":
            session.status = "not_started"
            session.pre_survey_submitted_at = None
            session.chat_started_at = None
            session.chat_completed_at = None
            session.post_survey_submitted_at = None
            session.completed_at = None
        else:
            session.status = "chat_completed"
            session.post_survey_submitted_at = None
            session.completed_at = None
        log_audit(
            db,
            admin_id=admin_id,
            action=f"{phase}_survey_reset",
            target_type="experiment_session",
            target_id=session.id,
            reason=reason,
            metadata={"participant_code": participant.participant_code},
        )
        log_behavior(
            db,
            event_type="admin_stage_reset",
            participant=participant,
            session=session,
            stage=phase,
            metadata={"phase": phase, "reason": reason.strip()},
        )
        db.commit()

    @staticmethod
    def _assert_phase_available(session: ExperimentSession, phase: Phase) -> None:
        if phase == "pre":
            if session.status not in {"not_started", "reset_required"}:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pre-survey is not available")
        elif phase == "post":
            if session.status != "chat_completed":
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Post-survey is available only after dialogue completion")

    @staticmethod
    def _normalize_response(item: QuestionnaireItem, raw: object) -> tuple[int | None, str | None]:
        scale = SCALE_PROFILES[item.scale]
        if scale.value_type == "integer":
            try:
                value = int(raw)
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{item.item_key} must be an integer") from exc
            assert scale.min_value is not None and scale.max_value is not None
            if value < scale.min_value or value > scale.max_value:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{item.item_key} must be between {scale.min_value} and {scale.max_value}")
            return value, str(value)
        text = str(raw).strip()
        if text not in scale.options:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{item.item_key} must be one of {', '.join(scale.options)}")
        return None, text

    @staticmethod
    def _compute_scores(
        db: Session,
        *,
        session: ExperimentSession,
        participant: Participant,
        phase: Phase,
        responses: list[QuestionnaireResponse],
    ) -> list[QuestionnaireScore]:
        by_key = {row.item_key: row for row in responses}
        attention_items = [item for item in get_items(phase) if item.attention_check]
        attention_passed = (
            all(
                by_key[item.item_key].response_value == item.attention_check_expected_value
                for item in attention_items
            )
            if attention_items
            else None
        )
        scores: list[QuestionnaireScore] = []
        for rule in score_rules_for_phase(phase):
            values = [
                by_key[key].response_value
                for key in rule.item_keys
                if by_key.get(key) is not None and by_key[key].response_value is not None
            ]
            missing_items = [key for key in rule.item_keys if by_key.get(key) is None or by_key[key].response_value is None]
            if not values:
                score_value = None
            elif rule.aggregation == "sum":
                score_value = float(sum(values))
            else:
                score_value = round(sum(values) / len(values), 6)
            score = QuestionnaireScore(
                experiment_session_id=session.id,
                participant_code=participant.participant_code,
                phase=phase,
                questionnaire_version=QUESTIONNAIRE_VERSION,
                instrument=rule.instrument,
                dimension=rule.dimension,
                score=score_value,
                valid_items=len(values),
                missing_items=missing_items,
                attention_check_passed=attention_passed,
            )
            db.add(score)
            scores.append(score)
        if attention_items:
            attention_score = QuestionnaireScore(
                experiment_session_id=session.id,
                participant_code=participant.participant_code,
                phase=phase,
                questionnaire_version=QUESTIONNAIRE_VERSION,
                instrument="attention_check",
                dimension=f"{phase}_attention",
                score=1.0 if attention_passed else 0.0,
                valid_items=len(attention_items),
                missing_items=[],
                attention_check_passed=attention_passed,
            )
            db.add(attention_score)
            scores.append(attention_score)
        return scores


class DialogueService:
    MIN_PARTICIPANT_TURNS = 6
    MIN_ELAPSED_SECONDS = 10 * 60
    MAX_PARTICIPANT_TURNS = 12
    MAX_ELAPSED_SECONDS = 60 * 60
    ACTIVE_ELAPSED_MAX_GAP_SECONDS = 45
    CONTINUE_RELATED_MIN_EXTRA_TURNS = 2
    CONTINUE_RELATED_MAX_EXTRA_TURNS = 4
    REMINDER_TURN_INTERVAL = 4
    REMINDER_TEXT = "请继续围绕专业选择与未来方向交流。"
    _NON_SUBSTANTIVE_TURNS = {
        "嗯",
        "嗯嗯",
        "好的",
        "好",
        "行",
        "可以",
        "继续",
        "继续吧",
        "你说吧",
        "说吧",
        "ok",
        "okay",
        "yes",
        "no",
    }

    @staticmethod
    def start_or_get(db: Session, *, session: ExperimentSession, participant: Participant) -> list[ChatMessage]:
        DialogueService._assert_dialogue_available(session)
        if session.chat_started_at is None:
            ExperimentSessionService.transition(db, session=session, next_status="chat_in_progress")
            log_behavior(
                db,
                event_type="dialogue_started",
                participant=participant,
                session=session,
                stage="chat_in_progress",
                metadata={"group": session.group},
            )
            db.commit()
            db.refresh(session)
        DialogueService.update_progress(db, session=session)
        return DialogueService.messages(db, session_id=session.id)

    @staticmethod
    def messages(db: Session, *, session_id: str) -> list[ChatMessage]:
        return list(
            db.scalars(
                select(ChatMessage)
                .where(ChatMessage.experiment_session_id == session_id)
                .order_by(ChatMessage.message_index)
            )
        )

    @staticmethod
    def send_message(
        db: Session,
        *,
        session: ExperimentSession,
        participant: Participant,
        content: str,
    ) -> ChatMessage:
        DialogueService._assert_dialogue_available(session)
        if session.status == "chat_completed":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Dialogue is already completed")
        if session.chat_started_at is None:
            DialogueService.start_or_get(db, session=session, participant=participant)
        if not content.strip():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="message content is required")
        messages = DialogueService.messages(db, session_id=session.id)
        if messages and messages[-1].role == "participant":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="AI response is still pending")
        progress_before = DialogueService.update_progress(db, session=session)
        if progress_before["forced_to_finish"]:
            db.commit()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Dialogue has reached the ending limit")
        next_index = DialogueService._next_index(db, session_id=session.id)
        participant_message = ChatMessage(
            experiment_session_id=session.id,
            participant_code=participant.participant_code,
            message_index=next_index,
            role="participant",
            content=content.strip(),
        )
        db.add(participant_message)
        log_behavior(
            db,
            event_type="participant_message_saved",
            participant=participant,
            session=session,
            stage=session.status,
            metadata={"message_index": next_index},
        )
        DialogueService.update_progress(db, session=session)
        db.commit()
        db.refresh(participant_message)
        db.refresh(session)
        return participant_message

    @staticmethod
    def generate_assistant_response(
        db: Session,
        *,
        session_id: str,
        participant_message_id: str,
    ) -> ChatMessage | None:
        participant_message = db.get(ChatMessage, participant_message_id)
        if participant_message is None or participant_message.role != "participant":
            return None
        session = db.get(ExperimentSession, session_id)
        if session is None:
            return None
        participant = db.get(Participant, session.participant_id)
        if participant is None:
            return None

        assistant_index = participant_message.message_index + 1
        existing = db.scalar(
            select(ChatMessage).where(
                ChatMessage.experiment_session_id == session.id,
                ChatMessage.message_index == assistant_index,
            )
        )
        if existing is not None:
            return existing

        history = DialogueService._provider_history(
            db,
            session_id=session.id,
            through_index=participant_message.message_index,
        )
        settings = get_settings()
        try:
            result, primary_error = DialogueService._generate_with_fallback(
                settings=settings,
                system_prompt="",
                history=history,
                provider_thread_id=session.dialogue_model_thread_id,
            )
            if result.provider_thread_id:
                session.dialogue_model_thread_id = result.provider_thread_id
            if result.provider_turn_id:
                session.dialogue_model_turn_id = result.provider_turn_id
            generation_params = {"prompt_mode": PROMPTLESS_DIALOGUE_MODE, **dict(result.generation_params)}
            if primary_error is not None:
                generation_params["fallback_triggered"] = True
                generation_params["primary_error_code"] = primary_error.code
                generation_params["primary_error_message_sanitized"] = primary_error.message
                generation_params["fallback_from_provider"] = settings.ai_provider_name
                generation_params["fallback_reason"] = primary_error.code
            if result.provider_thread_id:
                generation_params["provider_thread_id"] = result.provider_thread_id
            if result.provider_turn_id:
                generation_params["provider_turn_id"] = result.provider_turn_id
            assistant_message = ChatMessage(
                experiment_session_id=session.id,
                participant_code=participant.participant_code,
                message_index=assistant_index,
                role="assistant",
                content=result.content,
                provider_name=result.provider_name,
                model_name=result.model_name,
                system_prompt_version=None,
                generation_params=generation_params,
                request_started_at=result.request_started_at,
                response_completed_at=result.response_completed_at,
                duration_ms=result.duration_ms,
                retry_count=result.retry_count,
            )
            if primary_error is not None:
                log_behavior(
                    db,
                    event_type="ai_fallback_used",
                    participant=participant,
                    session=session,
                    stage=session.status,
                    metadata={
                        "primary_provider_name": settings.ai_provider_name,
                        "primary_model_name": settings.ai_model_name,
                        "fallback_provider_name": result.provider_name,
                        "fallback_model_name": result.model_name,
                        "prompt_mode": PROMPTLESS_DIALOGUE_MODE,
                        "primary_error_code": primary_error.code,
                        "primary_error_message_sanitized": primary_error.message,
                    },
                )
        except AIProviderError as exc:
            assistant_message = DialogueService._failure_assistant_message(
                session=session,
                participant=participant,
                assistant_index=assistant_index,
                settings=settings,
                error_code=exc.code,
                error_message=exc.message,
            )
            DialogueService._log_ai_failure(db, session=session, participant=participant, message=assistant_message)
        except Exception as exc:
            assistant_message = DialogueService._failure_assistant_message(
                session=session,
                participant=participant,
                assistant_index=assistant_index,
                settings=settings,
                error_code="ai_generation_failed",
                error_message=sanitize_error_message(str(exc)),
            )
            DialogueService._log_ai_failure(db, session=session, participant=participant, message=assistant_message)
        db.add(assistant_message)
        log_behavior(
            db,
            event_type="ai_response_saved",
            participant=participant,
            session=session,
            stage=session.status,
            metadata={
                "message_index": assistant_index,
                "provider_name": assistant_message.provider_name,
                "model_name": assistant_message.model_name,
                "prompt_mode": PROMPTLESS_DIALOGUE_MODE,
                "error_code": assistant_message.error_code,
            },
        )
        DialogueService.update_progress(db, session=session)
        db.commit()
        db.refresh(assistant_message)
        db.refresh(session)
        return assistant_message

    @staticmethod
    def _failure_assistant_message(
        *,
        session: ExperimentSession,
        participant: Participant,
        assistant_index: int,
        settings: Settings,
        error_code: str,
        error_message: str,
    ) -> ChatMessage:
        timestamp = now_utc()
        return ChatMessage(
            experiment_session_id=session.id,
            participant_code=participant.participant_code,
            message_index=assistant_index,
            role="assistant",
            content="AI 回复暂时生成失败，请稍后重试或联系研究者。",
            provider_name=settings.ai_provider_name,
            model_name=settings.ai_model_name,
            system_prompt_version=None,
            generation_params={"prompt_mode": PROMPTLESS_DIALOGUE_MODE},
            request_started_at=timestamp,
            response_completed_at=timestamp,
            duration_ms=0,
            retry_count=0,
            error_code=error_code,
            error_message_sanitized=error_message,
        )

    @staticmethod
    def _log_ai_failure(
        db: Session,
        *,
        session: ExperimentSession,
        participant: Participant,
        message: ChatMessage,
    ) -> None:
        log_behavior(
            db,
            event_type="ai_call_failed",
            participant=participant,
            session=session,
            stage=session.status,
            metadata={
                "provider_name": message.provider_name,
                "model_name": message.model_name,
                "prompt_mode": PROMPTLESS_DIALOGUE_MODE,
                "retry_count": 0,
                "error_code": message.error_code,
                "error_message_sanitized": message.error_message_sanitized,
            },
        )

    @staticmethod
    def update_progress(db: Session, *, session: ExperimentSession) -> dict[str, object]:
        participant_messages = list(
            db.scalars(
                select(ChatMessage)
                .where(ChatMessage.experiment_session_id == session.id, ChatMessage.role == "participant")
                .order_by(ChatMessage.message_index)
            )
        )
        participant_turns = sum(
            1 for message in participant_messages if DialogueService.is_effective_participant_turn(message.content)
        )
        elapsed = DialogueService._active_elapsed_seconds(session)
        session.participant_turn_count = int(participant_turns)
        session.dialogue_elapsed_seconds = elapsed

        met_min_turns = participant_turns >= DialogueService.MIN_PARTICIPANT_TURNS
        met_min_duration = elapsed >= DialogueService.MIN_ELAPSED_SECONDS
        forced_finish_reason = DialogueService._forced_finish_reason(session, participant_turns, elapsed)
        session.dialogue_forced_finish_reason = forced_finish_reason

        finish_prompt_visible = DialogueService._finish_prompt_visible(
            session,
            participant_turns=participant_turns,
            met_min_turns=met_min_turns,
            met_min_duration=met_min_duration,
            forced_finish_reason=forced_finish_reason,
        )
        eligible = finish_prompt_visible or forced_finish_reason is not None
        if eligible and session.status == "chat_in_progress":
            session.status = "chat_eligible_to_finish"
            log_behavior(
                db,
                event_type="completion_eligibility_reached",
                session=session,
                participant_code=session.participant.participant_code if session.participant else None,
                stage="chat_eligible_to_finish",
                metadata={"participant_turn_count": participant_turns, "dialogue_elapsed_seconds": elapsed},
            )
        elif not eligible and session.status == "chat_eligible_to_finish":
            session.status = "chat_in_progress"
        reminder_due = participant_turns > 0 and participant_turns % DialogueService.REMINDER_TURN_INTERVAL == 0
        return {
            "participant_turn_count": int(participant_turns),
            "dialogue_elapsed_seconds": elapsed,
            "met_min_turns": met_min_turns,
            "met_min_duration": met_min_duration,
            "eligible_to_finish": eligible,
            "finish_prompt_visible": finish_prompt_visible,
            "forced_to_finish": forced_finish_reason is not None,
            "forced_finish_reason": forced_finish_reason,
            "finish_decision": session.dialogue_finish_decision,
            "continue_until_turn_count": session.dialogue_continue_until_turn_count,
            "reminder_due": reminder_due,
            "reminder_text": DialogueService.REMINDER_TEXT,
        }

    @staticmethod
    def finish(db: Session, *, session: ExperimentSession, participant: Participant, decision: str) -> None:
        DialogueService._assert_dialogue_available(session)
        messages = DialogueService.messages(db, session_id=session.id)
        if messages and messages[-1].role == "participant":
            db.commit()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="AI response is still pending")
        progress = DialogueService.update_progress(db, session=session)
        if session.status == "chat_completed":
            db.commit()
            db.refresh(session)
            return
        if decision == "early_stop":
            DialogueService._complete_dialogue(
                db, session=session, participant=participant, metadata={**progress, "decision": decision}
            )
            return
        if progress["forced_to_finish"]:
            DialogueService._complete_dialogue(
                db, session=session, participant=participant, metadata={**progress, "decision": decision}
            )
            return
        if not progress["finish_prompt_visible"]:
            db.commit()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Dialogue is not eligible to finish")
        if decision == "can_end":
            DialogueService._complete_dialogue(
                db, session=session, participant=participant, metadata={**progress, "decision": decision}
            )
            return
        if session.dialogue_finish_decision is not None:
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Dialogue continuation branch already selected",
            )
        if decision == "continue_related":
            current_turns = int(progress["participant_turn_count"])
            session.dialogue_finish_decision = decision
            session.dialogue_finish_decision_turn_count = current_turns
            session.dialogue_continue_until_turn_count = min(
                DialogueService.MAX_PARTICIPANT_TURNS,
                current_turns + DialogueService.CONTINUE_RELATED_MAX_EXTRA_TURNS,
            )
            session.status = "chat_in_progress"
            log_behavior(
                db,
                event_type="dialogue_finish_branch_selected",
                participant=participant,
                session=session,
                stage=session.status,
                metadata={**progress, "decision": decision},
            )
        elif decision == "not_core":
            session.dialogue_finish_decision = decision
            session.dialogue_finish_decision_turn_count = int(progress["participant_turn_count"])
            session.dialogue_continue_until_turn_count = DialogueService.MAX_PARTICIPANT_TURNS
            session.status = "chat_in_progress"
            log_behavior(
                db,
                event_type="dialogue_finish_branch_selected",
                participant=participant,
                session=session,
                stage=session.status,
                metadata={**progress, "decision": decision},
            )
        else:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown finish decision")
        db.commit()
        db.refresh(session)

    @staticmethod
    def _assert_dialogue_available(session: ExperimentSession) -> None:
        if not session.assignment_locked or session.group is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Group Assignment is required before dialogue")
        if session.status not in {"pre_survey_submitted", "chat_in_progress", "chat_eligible_to_finish", "chat_completed"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="AI Dialogue is available only after pre-survey submission")

    @staticmethod
    def _next_index(db: Session, *, session_id: str) -> int:
        current = db.scalar(
            select(func.max(ChatMessage.message_index)).where(ChatMessage.experiment_session_id == session_id)
        )
        return int(current or 0) + 1

    @staticmethod
    def _provider_history(db: Session, *, session_id: str, through_index: int | None = None) -> list[dict[str, str]]:
        history = []
        query = select(ChatMessage).where(ChatMessage.experiment_session_id == session_id)
        if through_index is not None:
            query = query.where(ChatMessage.message_index <= through_index)
        query = query.order_by(ChatMessage.message_index)
        for message in db.scalars(query):
            if message.role == "participant":
                history.append({"role": "user", "content": message.content})
            elif message.role == "assistant" and message.content.strip() and not message.error_code:
                history.append({"role": "assistant", "content": message.content})
        return history

    @staticmethod
    def _generate_with_fallback(
        *,
        settings: Settings,
        system_prompt: str,
        history: list[dict[str, str]],
        provider_thread_id: str | None,
    ) -> tuple[AIProviderResult, AIProviderError | None]:
        started = time.perf_counter()
        try:
            return (
                create_ai_provider(settings).generate(
                    system_prompt=system_prompt,
                    messages=history,
                    provider_thread_id=provider_thread_id,
                ),
                None,
            )
        except AIProviderError as primary_error:
            elapsed = time.perf_counter() - started
            remaining_timeout = settings.ai_response_sla_seconds - elapsed
            if remaining_timeout <= 0:
                raise
            fallback_deadline = started + settings.ai_response_sla_seconds
            fallback_settings = DialogueService._fallback_settings(
                settings,
                timeout_seconds=min(settings.ai_fallback_timeout_seconds, remaining_timeout),
            )
            if fallback_settings is None:
                raise
            try:
                return (
                    DialogueService._generate_with_retry(
                        settings=fallback_settings,
                        system_prompt=system_prompt,
                        history=history,
                        provider_thread_id=None,
                        max_attempts=settings.ai_fallback_max_attempts,
                        deadline=fallback_deadline,
                    ),
                    primary_error,
                )
            except AIProviderError as fallback_error:
                raise AIProviderError(
                    "ai_fallback_failed",
                    (
                        f"primary {primary_error.code}: {primary_error.message}; "
                        f"fallback {fallback_error.code}: {fallback_error.message}"
                    ),
                ) from fallback_error

    @staticmethod
    def _generate_with_retry(
        *,
        settings: Settings,
        system_prompt: str,
        history: list[dict[str, str]],
        provider_thread_id: str | None,
        max_attempts: int,
        deadline: float | None = None,
    ) -> AIProviderResult:
        attempts = max(1, max_attempts)
        retry_errors: list[dict[str, object]] = []
        for attempt in range(1, attempts + 1):
            attempt_settings = settings
            if deadline is not None:
                remaining_timeout = deadline - time.perf_counter()
                if remaining_timeout <= 0:
                    raise AIProviderError("provider_timeout", "Fallback retry budget exhausted")
                attempt_settings = settings.model_copy(
                    update={"ai_timeout_seconds": min(settings.ai_timeout_seconds, remaining_timeout)}
                )
            try:
                result = create_ai_provider(attempt_settings).generate(
                    system_prompt=system_prompt,
                    messages=history,
                    provider_thread_id=provider_thread_id,
                )
            except AIProviderError as exc:
                retry_errors.append(
                    {
                        "attempt": attempt,
                        "code": exc.code,
                        "message_sanitized": exc.message,
                    }
                )
                retryable = DialogueService._is_retryable_provider_error(exc)
                if attempt >= attempts or not retryable:
                    raise AIProviderError(
                        exc.code,
                        f"{exc.message}; attempts={attempt}; retryable={retryable}",
                    ) from exc
                continue
            if retry_errors:
                return AIProviderResult(
                    content=result.content,
                    provider_name=result.provider_name,
                    model_name=result.model_name,
                    generation_params={
                        **dict(result.generation_params),
                        "retry_errors": retry_errors,
                    },
                    request_started_at=result.request_started_at,
                    response_completed_at=result.response_completed_at,
                    duration_ms=result.duration_ms,
                    retry_count=result.retry_count + len(retry_errors),
                    error_code=result.error_code,
                    error_message_sanitized=result.error_message_sanitized,
                    provider_thread_id=result.provider_thread_id,
                    provider_turn_id=result.provider_turn_id,
                )
            return result
        raise AIProviderError("provider_error", "Provider retry loop exhausted without a result")

    @staticmethod
    def _is_retryable_provider_error(error: AIProviderError) -> bool:
        return error.code in {"provider_timeout", "provider_error", "codex_timeout"}

    @staticmethod
    def _fallback_settings(settings: Settings, *, timeout_seconds: float | None = None) -> Settings | None:
        if not settings.ai_fallback_enabled:
            return None
        provider_name = settings.ai_fallback_provider_name.strip()
        if not provider_name:
            return None
        api_key = settings.ai_fallback_api_key or settings.ai_api_key
        if provider_name not in {"mock", "codex"} and not api_key:
            return None
        return Settings(
            AI_PROVIDER_NAME=provider_name,
            AI_BASE_URL=settings.ai_fallback_base_url,
            AI_API_KEY=api_key,
            AI_MODEL_NAME=settings.ai_fallback_model_name,
            AI_TEMPERATURE=settings.ai_fallback_temperature,
            AI_MAX_TOKENS=settings.ai_fallback_max_tokens,
            AI_TIMEOUT_SECONDS=timeout_seconds or settings.ai_fallback_timeout_seconds,
            AI_RESPONSE_SLA_SECONDS=settings.ai_response_sla_seconds,
            AI_FALLBACK_MAX_ATTEMPTS=settings.ai_fallback_max_attempts,
            CODEX_COMMAND=settings.codex_command,
            CODEX_APPROVAL_POLICY=settings.codex_approval_policy,
            CODEX_SANDBOX=settings.codex_sandbox,
            CODEX_REASONING_EFFORT=settings.codex_reasoning_effort,
            CODEX_READ_TIMEOUT_SECONDS=settings.codex_read_timeout_seconds,
            CODEX_TURN_TIMEOUT_SECONDS=min(
                settings.codex_turn_timeout_seconds,
                timeout_seconds or settings.ai_response_sla_seconds,
            ),
            CODEX_CWD=settings.codex_cwd,
        )

    @staticmethod
    def normalize_turn_content(content: str) -> str:
        normalized = content.strip().lower()
        normalized = re.sub(r"[\s，。！？、,.!?;；:：\"'“”‘’（）()【】\[\]…\-]+", "", normalized)
        return normalized

    @staticmethod
    def is_effective_participant_turn(content: str) -> bool:
        normalized = DialogueService.normalize_turn_content(content)
        if not normalized:
            return False
        if normalized in DialogueService._NON_SUBSTANTIVE_TURNS:
            return False
        if len(normalized) <= 1:
            return False
        return bool(re.search(r"[\w\u4e00-\u9fff]", normalized))

    @staticmethod
    def _forced_finish_reason(session: ExperimentSession, participant_turns: int, elapsed: int) -> str | None:
        if participant_turns >= DialogueService.MAX_PARTICIPANT_TURNS:
            return "max_turns"
        if (
            session.dialogue_finish_decision == "continue_related"
            and session.dialogue_continue_until_turn_count is not None
            and participant_turns >= session.dialogue_continue_until_turn_count
        ):
            return "continue_related_limit"
        return None

    @staticmethod
    def _active_elapsed_seconds(session: ExperimentSession) -> int:
        if session.chat_started_at is None:
            return 0
        timestamp = now_utc()
        elapsed = max(0, int(session.dialogue_elapsed_seconds or 0))
        chat_started_at = as_utc(session.chat_started_at)
        last_seen = as_utc(session.last_seen_at or session.chat_started_at)
        if last_seen < chat_started_at:
            last_seen = chat_started_at
        gap = elapsed_seconds_between(last_seen, timestamp)
        if gap <= DialogueService.ACTIVE_ELAPSED_MAX_GAP_SECONDS:
            elapsed += gap
        session.last_seen_at = timestamp
        return elapsed

    @staticmethod
    def _finish_prompt_visible(
        session: ExperimentSession,
        *,
        participant_turns: int,
        met_min_turns: bool,
        met_min_duration: bool,
        forced_finish_reason: str | None,
    ) -> bool:
        if forced_finish_reason is not None:
            return True
        if session.dialogue_finish_decision == "continue_related":
            branch_start = session.dialogue_finish_decision_turn_count or participant_turns
            return participant_turns >= branch_start + DialogueService.CONTINUE_RELATED_MIN_EXTRA_TURNS
        if session.dialogue_finish_decision == "not_core":
            return False
        return met_min_turns and met_min_duration

    @staticmethod
    def _complete_dialogue(
        db: Session,
        *,
        session: ExperimentSession,
        participant: Participant,
        metadata: dict[str, object],
    ) -> None:
        if session.status in {"chat_in_progress", "chat_eligible_to_finish"}:
            if session.status == "chat_in_progress":
                session.status = "chat_eligible_to_finish"
            ExperimentSessionService.transition(db, session=session, next_status="chat_completed")
            log_behavior(
                db,
                event_type="dialogue_completed",
                participant=participant,
                session=session,
                stage="chat_completed",
                metadata=metadata,
            )
        db.commit()
        db.refresh(session)


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
            pre_survey_submitted=False,
            post_survey_submitted=False,
            participant_turn_count=0,
            dialogue_elapsed_seconds=0,
            dialogue_elapsed_minutes=0.0,
            met_min_turns=False,
            met_min_duration=False,
            dialogue_completion_eligible=False,
            dialogue_completed=False,
            completed=False,
            excluded=False,
            exclusion_reason=None,
            topic_off_track_ratio=None,
            topic_off_track_gt_30pct=None,
            topic_validity_status="not_ready",
            topic_validity_notes=None,
            topic_validity_coded_at=None,
            resume_count=0,
            last_seen_at=None,
        )
    met_min_turns = session.participant_turn_count >= DialogueService.MIN_PARTICIPANT_TURNS
    met_min_duration = session.dialogue_elapsed_seconds >= DialogueService.MIN_ELAPSED_SECONDS
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
        pre_survey_submitted=session.pre_survey_submitted_at is not None,
        post_survey_submitted=session.post_survey_submitted_at is not None,
        participant_turn_count=session.participant_turn_count,
        dialogue_elapsed_seconds=session.dialogue_elapsed_seconds,
        dialogue_elapsed_minutes=round(session.dialogue_elapsed_seconds / 60, 2),
        met_min_turns=met_min_turns,
        met_min_duration=met_min_duration,
        dialogue_completion_eligible=met_min_turns and met_min_duration,
        dialogue_completed=session.chat_completed_at is not None
        or session.status in {"chat_completed", "completed"},
        completed=session.completed_at is not None or session.status == "completed",
        excluded=session.excluded or session.status == "excluded",
        exclusion_reason=session.exclusion_reason,
        topic_off_track_ratio=session.topic_off_track_ratio,
        topic_off_track_gt_30pct=(
            session.topic_off_track_ratio > 0.30
            if session.topic_off_track_ratio is not None
            else None
        ),
        topic_validity_status=session.topic_validity_status,
        topic_validity_notes=session.topic_validity_notes,
        topic_validity_coded_at=session.topic_validity_coded_at,
        resume_count=session.resume_count,
        last_seen_at=session.last_seen_at,
    )
