from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.ai_provider import AIProviderError, OpenAICompatibleProvider, prompt_for_group
from app.config import get_settings
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
        attention_passed = all(
            by_key[item.item_key].response_value == item.attention_check_expected_value
            for item in attention_items
        )
        scores: list[QuestionnaireScore] = []
        for rule in score_rules_for_phase(phase):
            values = [
                by_key[key].response_value
                for key in rule.item_keys
                if by_key.get(key) is not None and by_key[key].response_value is not None
            ]
            missing_items = [key for key in rule.item_keys if by_key.get(key) is None or by_key[key].response_value is None]
            score_value = round(sum(values) / len(values), 6) if values else None
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
    MIN_PARTICIPANT_TURNS = 10
    MIN_ELAPSED_SECONDS = 15 * 60

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
    ) -> tuple[ChatMessage, ChatMessage]:
        DialogueService._assert_dialogue_available(session)
        if session.chat_started_at is None:
            DialogueService.start_or_get(db, session=session, participant=participant)
        if not content.strip():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="message content is required")
        next_index = DialogueService._next_index(db, session_id=session.id)
        participant_message = ChatMessage(
            experiment_session_id=session.id,
            participant_code=participant.participant_code,
            message_index=next_index,
            role="participant",
            content=content.strip(),
        )
        db.add(participant_message)
        db.flush()
        history = DialogueService._provider_history(db, session_id=session.id)
        prompt = prompt_for_group(session.group or "")
        provider = OpenAICompatibleProvider(get_settings())
        try:
            result = provider.generate(system_prompt=prompt.system_prompt, messages=history)
            assistant_message = ChatMessage(
                experiment_session_id=session.id,
                participant_code=participant.participant_code,
                message_index=next_index + 1,
                role="assistant",
                content=result.content,
                provider_name=result.provider_name,
                model_name=result.model_name,
                system_prompt_version=prompt.version,
                generation_params=result.generation_params,
                request_started_at=result.request_started_at,
                response_completed_at=result.response_completed_at,
                duration_ms=result.duration_ms,
                retry_count=result.retry_count,
            )
        except AIProviderError as exc:
            timestamp = now_utc()
            assistant_message = ChatMessage(
                experiment_session_id=session.id,
                participant_code=participant.participant_code,
                message_index=next_index + 1,
                role="assistant",
                content="",
                provider_name=get_settings().ai_provider_name,
                model_name=get_settings().ai_model_name,
                system_prompt_version=prompt.version,
                generation_params={},
                request_started_at=timestamp,
                response_completed_at=timestamp,
                duration_ms=0,
                retry_count=0,
                error_code=exc.code,
                error_message_sanitized=exc.message,
            )
            db.add(assistant_message)
            db.commit()
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI provider call failed") from exc
        db.add(assistant_message)
        log_behavior(
            db,
            event_type="participant_message_saved",
            participant=participant,
            session=session,
            stage=session.status,
            metadata={"message_index": next_index},
        )
        log_behavior(
            db,
            event_type="ai_response_saved",
            participant=participant,
            session=session,
            stage=session.status,
            metadata={
                "message_index": next_index + 1,
                "provider_name": assistant_message.provider_name,
                "model_name": assistant_message.model_name,
                "system_prompt_version": assistant_message.system_prompt_version,
            },
        )
        DialogueService.update_progress(db, session=session)
        db.commit()
        db.refresh(participant_message)
        db.refresh(assistant_message)
        db.refresh(session)
        return participant_message, assistant_message

    @staticmethod
    def update_progress(db: Session, *, session: ExperimentSession) -> dict[str, object]:
        participant_turns = db.scalar(
            select(func.count()).select_from(ChatMessage).where(
                ChatMessage.experiment_session_id == session.id,
                ChatMessage.role == "participant",
            )
        ) or 0
        elapsed = 0
        if session.chat_started_at is not None:
            elapsed = max(0, int((now_utc() - session.chat_started_at).total_seconds()))
        session.participant_turn_count = int(participant_turns)
        session.dialogue_elapsed_seconds = elapsed
        eligible = participant_turns >= DialogueService.MIN_PARTICIPANT_TURNS and elapsed >= DialogueService.MIN_ELAPSED_SECONDS
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
        return {
            "participant_turn_count": int(participant_turns),
            "dialogue_elapsed_seconds": elapsed,
            "met_min_turns": participant_turns >= DialogueService.MIN_PARTICIPANT_TURNS,
            "met_min_duration": elapsed >= DialogueService.MIN_ELAPSED_SECONDS,
            "eligible_to_finish": eligible,
        }

    @staticmethod
    def finish(db: Session, *, session: ExperimentSession, participant: Participant) -> None:
        progress = DialogueService.update_progress(db, session=session)
        if not progress["eligible_to_finish"]:
            db.commit()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Dialogue is not eligible to finish")
        if session.status == "chat_eligible_to_finish":
            ExperimentSessionService.transition(db, session=session, next_status="chat_completed")
            log_behavior(
                db,
                event_type="dialogue_completed",
                participant=participant,
                session=session,
                stage="chat_completed",
                metadata=progress,
            )
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
    def _provider_history(db: Session, *, session_id: str) -> list[dict[str, str]]:
        history = []
        for message in DialogueService.messages(db, session_id=session_id):
            if message.role == "participant":
                history.append({"role": "user", "content": message.content})
            elif message.role == "assistant" and not message.error_code:
                history.append({"role": "assistant", "content": message.content})
        return history


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
