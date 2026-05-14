from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_provider import CONTROL_PROMPT_VERSION, EXPERIMENT_PROMPT_VERSION
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
from app.questionnaire_config import QUESTIONNAIRE_VERSION
from app.services import DialogueService


EXPORT_FILES = (
    "README.md",
    "participants.csv",
    "experiment_sessions.csv",
    "questionnaire_responses.csv",
    "questionnaire_scores.csv",
    "analysis_dataset.csv",
    "chat_messages.jsonl",
    "behavior_events.jsonl",
    "audit_logs.csv",
    "ai_call_records.csv",
    "export_manifest.json",
)


def build_export_zip(db: Session, *, admin_id: str) -> tuple[bytes, str]:
    generated_at = datetime.now(UTC)
    export_id = f"mentor-echo-export-{generated_at.strftime('%Y%m%dT%H%M%SZ')}"

    payloads: dict[str, tuple[bytes, int, str]] = {}
    payloads["participants.csv"] = _csv_payload(_participants_rows(db))
    payloads["experiment_sessions.csv"] = _csv_payload(_session_rows(db))
    payloads["questionnaire_responses.csv"] = _csv_payload(_questionnaire_response_rows(db))
    payloads["questionnaire_scores.csv"] = _csv_payload(_questionnaire_score_rows(db))
    payloads["analysis_dataset.csv"] = _csv_payload(_analysis_dataset_rows(db))
    payloads["chat_messages.jsonl"] = _jsonl_payload(_chat_message_rows(db))
    payloads["behavior_events.jsonl"] = _jsonl_payload(_behavior_event_rows(db))
    payloads["audit_logs.csv"] = _csv_payload(_audit_log_rows(db))
    payloads["ai_call_records.csv"] = _csv_payload(_ai_call_rows(db))
    payloads["README.md"] = (
        _readme(export_id=export_id, generated_at=generated_at, admin_id=admin_id).encode("utf-8"),
        1,
        "documentation",
    )

    manifest = _manifest(
        export_id=export_id,
        generated_at=generated_at,
        admin_id=admin_id,
        payloads=payloads,
    )
    payloads["export_manifest.json"] = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"),
        1,
        "manifest",
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename in EXPORT_FILES:
            archive.writestr(f"{export_id}/{filename}", payloads[filename][0])
    return buffer.getvalue(), f"{export_id}.zip"


def _csv_payload(rows: list[dict[str, Any]]) -> tuple[bytes, int, str]:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _scalar(value) for key, value in row.items()})
    return buffer.getvalue().encode("utf-8"), len(rows), "routine_research_data"


def _jsonl_payload(rows: list[dict[str, Any]]) -> tuple[bytes, int, str]:
    text = "".join(json.dumps(_jsonable(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    return text.encode("utf-8"), len(rows), "routine_research_data"


def _scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (dict, list)):
        return json.dumps(_jsonable(value), ensure_ascii=False, sort_keys=True)
    return str(value)


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _participants_rows(db: Session) -> list[dict[str, Any]]:
    participants = db.scalars(select(Participant).order_by(Participant.participant_code)).all()
    rows: list[dict[str, Any]] = []
    for participant in participants:
        session = participant.experiment_session
        rows.append(
            {
                "participant_code": participant.participant_code,
                "imported_at": participant.imported_at,
                "import_batch_id": "",
                "assigned_group_imported": participant.assigned_group,
                "created_at": participant.created_at,
                "excluded": bool(session.excluded) if session else False,
                "exclusion_reason": session.exclusion_reason if session else None,
            }
        )
    return rows


def _session_rows(db: Session) -> list[dict[str, Any]]:
    sessions = db.scalars(select(ExperimentSession).order_by(ExperimentSession.started_at)).all()
    rows: list[dict[str, Any]] = []
    for session in sessions:
        participant = db.get(Participant, session.participant_id)
        met_min_turns = session.participant_turn_count >= DialogueService.MIN_PARTICIPANT_TURNS
        met_min_duration = session.dialogue_elapsed_seconds >= DialogueService.MIN_ELAPSED_SECONDS
        rows.append(
            {
                "experiment_session_id": session.id,
                "participant_code": participant.participant_code if participant else "",
                "group": session.group,
                "assignment_source": session.assignment_source,
                "status": session.status,
                "started_at": session.started_at,
                "pre_survey_submitted_at": session.pre_survey_submitted_at,
                "chat_started_at": session.chat_started_at,
                "chat_completed_at": session.chat_completed_at,
                "post_survey_submitted_at": session.post_survey_submitted_at,
                "completed_at": session.completed_at,
                "participant_turn_count": session.participant_turn_count,
                "dialogue_elapsed_seconds": session.dialogue_elapsed_seconds,
                "met_min_turns": met_min_turns,
                "met_min_duration": met_min_duration,
                "resume_count": session.resume_count,
                "last_seen_at": session.last_seen_at,
                "excluded": session.excluded,
                "exclusion_reason": session.exclusion_reason,
                "excluded_at": session.excluded_at,
            }
        )
    return rows


def _questionnaire_response_rows(db: Session) -> list[dict[str, Any]]:
    responses = db.scalars(
        select(QuestionnaireResponse).order_by(
            QuestionnaireResponse.participant_code,
            QuestionnaireResponse.phase,
            QuestionnaireResponse.item_key,
            QuestionnaireResponse.submitted_at,
        )
    ).all()
    return [
        {
            "participant_code": row.participant_code,
            "experiment_session_id": row.experiment_session_id,
            "phase": row.phase,
            "questionnaire_version": row.questionnaire_version,
            "item_key": row.item_key,
            "instrument": row.instrument,
            "dimension": row.dimension,
            "response_value": row.response_value,
            "response_text": row.response_text,
            "submitted_at": row.submitted_at,
            "superseded_at": row.superseded_at,
        }
        for row in responses
    ]


def _questionnaire_score_rows(db: Session) -> list[dict[str, Any]]:
    scores = db.scalars(
        select(QuestionnaireScore).order_by(
            QuestionnaireScore.participant_code,
            QuestionnaireScore.phase,
            QuestionnaireScore.instrument,
            QuestionnaireScore.dimension,
            QuestionnaireScore.created_at,
        )
    ).all()
    return [
        {
            "participant_code": row.participant_code,
            "experiment_session_id": row.experiment_session_id,
            "phase": row.phase,
            "questionnaire_version": row.questionnaire_version,
            "instrument": row.instrument,
            "dimension": row.dimension,
            "score": row.score,
            "valid_items": row.valid_items,
            "missing_items": row.missing_items,
            "attention_check_passed": row.attention_check_passed,
            "created_at": row.created_at,
            "superseded_at": row.superseded_at,
        }
        for row in scores
    ]


def _analysis_dataset_rows(db: Session) -> list[dict[str, Any]]:
    participants = db.scalars(select(Participant).order_by(Participant.participant_code)).all()
    active_scores = db.scalars(
        select(QuestionnaireScore)
        .where(QuestionnaireScore.superseded_at.is_(None))
        .order_by(QuestionnaireScore.participant_code, QuestionnaireScore.phase)
    ).all()
    scores_by_code: dict[str, dict[tuple[str, str, str], float | None]] = {}
    attention_by_code: dict[str, dict[str, bool | None]] = {}
    for score in active_scores:
        key = (
            _field_token(score.instrument),
            _field_token(score.dimension),
            score.phase,
        )
        scores_by_code.setdefault(score.participant_code, {})[key] = score.score
        attention_by_code.setdefault(score.participant_code, {})[score.phase] = score.attention_check_passed

    rows: list[dict[str, Any]] = []
    for participant in participants:
        session = participant.experiment_session
        participant_scores = scores_by_code.get(participant.participant_code, {})
        row: dict[str, Any] = {
            "participant_code": participant.participant_code,
            "group": session.group if session else None,
            "assignment_source": session.assignment_source if session else None,
            "status": session.status if session else "not_started",
            "excluded": bool(session.excluded) if session else False,
            "exclusion_reason": session.exclusion_reason if session else None,
            "completed": bool(session.completed_at) if session else False,
            "pre_survey_submitted_at": session.pre_survey_submitted_at if session else None,
            "chat_started_at": session.chat_started_at if session else None,
            "chat_completed_at": session.chat_completed_at if session else None,
            "post_survey_submitted_at": session.post_survey_submitted_at if session else None,
            "completed_at": session.completed_at if session else None,
            "participant_turn_count": session.participant_turn_count if session else 0,
            "dialogue_elapsed_seconds": session.dialogue_elapsed_seconds if session else 0,
            "met_min_turns": (
                session.participant_turn_count >= DialogueService.MIN_PARTICIPANT_TURNS if session else False
            ),
            "met_min_duration": (
                session.dialogue_elapsed_seconds >= DialogueService.MIN_ELAPSED_SECONDS if session else False
            ),
            "resume_count": session.resume_count if session else 0,
            "pre_attention_check_passed": attention_by_code.get(participant.participant_code, {}).get("pre"),
            "post_attention_check_passed": attention_by_code.get(participant.participant_code, {}).get("post"),
        }
        score_prefixes = sorted({(instrument, dimension) for instrument, dimension, _ in participant_scores})
        for instrument, dimension in score_prefixes:
            pre = participant_scores.get((instrument, dimension, "pre"))
            post = participant_scores.get((instrument, dimension, "post"))
            prefix = f"{instrument}_{dimension}"
            row[f"{prefix}_pre"] = pre
            row[f"{prefix}_post"] = post
            row[f"{prefix}_change"] = (
                round(post - pre, 6) if isinstance(pre, (int, float)) and isinstance(post, (int, float)) else None
            )
        rows.append(row)
    return rows


def _field_token(value: str) -> str:
    token = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return token or "unknown"


def _chat_message_rows(db: Session) -> list[dict[str, Any]]:
    messages = db.scalars(
        select(ChatMessage).order_by(ChatMessage.participant_code, ChatMessage.message_index)
    ).all()
    session_group_by_id = {
        session.id: session.group
        for session in db.scalars(select(ExperimentSession)).all()
    }
    return [
        {
            "experiment_session_id": message.experiment_session_id,
            "participant_code": message.participant_code,
            "group": session_group_by_id.get(message.experiment_session_id),
            "message_index": message.message_index,
            "role": message.role,
            "content": message.content,
            "created_at": message.created_at,
            "provider_name": message.provider_name,
            "model_name": message.model_name,
            "system_prompt_version": message.system_prompt_version,
            "generation_params": message.generation_params,
        }
        for message in messages
    ]


def _behavior_event_rows(db: Session) -> list[dict[str, Any]]:
    events = db.scalars(select(BehaviorEvent).order_by(BehaviorEvent.created_at, BehaviorEvent.id)).all()
    return [
        {
            "event_id": event.id,
            "experiment_session_id": event.experiment_session_id,
            "participant_code": event.participant_code,
            "event_type": event.event_type,
            "stage": event.stage,
            "created_at": event.created_at,
            "metadata": event.event_metadata,
        }
        for event in events
    ]


def _audit_log_rows(db: Session) -> list[dict[str, Any]]:
    logs = db.scalars(select(AuditLog).order_by(AuditLog.created_at, AuditLog.id)).all()
    return [
        {
            "audit_log_id": log.id,
            "admin_id": log.admin_id,
            "action": log.action,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "reason": log.reason,
            "created_at": log.created_at,
            "metadata": log.audit_metadata,
        }
        for log in logs
    ]


def _ai_call_rows(db: Session) -> list[dict[str, Any]]:
    assistant_messages = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.role == "assistant")
        .order_by(ChatMessage.participant_code, ChatMessage.message_index)
    ).all()
    return [
        {
            "ai_call_id": message.id,
            "experiment_session_id": message.experiment_session_id,
            "participant_code": message.participant_code,
            "provider_name": message.provider_name,
            "model_name": message.model_name,
            "system_prompt_version": message.system_prompt_version,
            "request_started_at": message.request_started_at,
            "response_completed_at": message.response_completed_at,
            "duration_ms": message.duration_ms,
            "retry_count": message.retry_count,
            "status": "error" if message.error_code else "success",
            "error_code": message.error_code,
            "error_message_sanitized": message.error_message_sanitized,
        }
        for message in assistant_messages
    ]


def _readme(*, export_id: str, generated_at: datetime, admin_id: str) -> str:
    settings = get_settings()
    return f"""# Mentor Echo Export Package

Export ID: `{export_id}`
Generated at: `{generated_at.isoformat()}`
Generated by administrator: `{admin_id}`

## System-of-record statement

This ZIP is a generated snapshot from PostgreSQL. It is not a database backup and
must not become a competing source of truth.

## Questionnaire and AI configuration

- Questionnaire version: `{QUESTIONNAIRE_VERSION}`
- AI provider: `{settings.ai_provider_name}`
- AI base URL: `{settings.ai_base_url}`
- AI model: `{settings.ai_model_name}`
- Generation parameters: temperature `{settings.ai_temperature}`, max tokens `{settings.ai_max_tokens}`
- Experiment prompt version: `{EXPERIMENT_PROMPT_VERSION}`
- Control prompt version: `{CONTROL_PROMPT_VERSION}`
- Completion rule: 10 participant turns + 15 minutes
- Group assignment: imported assignment wins; blank imports randomize once and then lock

## Files

- `participants.csv`: participant-code registry and exclusion fields.
- `experiment_sessions.csv`: lifecycle status, assignment, timestamps, resume, and dialogue metrics.
- `questionnaire_responses.csv`: long-form raw questionnaire responses.
- `questionnaire_scores.csv`: long-form derived questionnaire scores.
- `analysis_dataset.csv`: one row per participant for routine analysis. It intentionally excludes raw chat text.
- `chat_messages.jsonl`: SENSITIVE RAW CHAT export containing participant and assistant message content.
- `behavior_events.jsonl`: participant/technical lifecycle events.
- `audit_logs.csv`: researcher administrator action history.
- `ai_call_records.csv`: AI provider diagnostics derived from assistant message records.
- `export_manifest.json`: machine-readable row counts, checksums, and sensitivity metadata.

## Privacy warnings

SENSITIVE RAW CHAT: `chat_messages.jsonl` contains complete dialogue text and
should be shared only with researchers who need qualitative coding or text
analysis access. Routine statistical workflows should use `analysis_dataset.csv`.

The platform stores participant codes, not participant names. Full IP addresses
are not exported by default. API keys and provider secrets are never included in
this package.
"""


def _manifest(
    *,
    export_id: str,
    generated_at: datetime,
    admin_id: str,
    payloads: dict[str, tuple[bytes, int, str]],
) -> dict[str, Any]:
    files = {
        filename: {
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "row_count": row_count,
            "classification": "sensitive_raw_chat"
            if filename == "chat_messages.jsonl"
            else classification,
        }
        for filename, (content, row_count, classification) in payloads.items()
    }
    row_counts = {filename: metadata["row_count"] for filename, metadata in files.items()}
    return {
        "export_id": export_id,
        "generated_at": generated_at.isoformat(),
        "administrator_id": admin_id,
        "filters_applied": {},
        "included_files": list(EXPORT_FILES),
        "files": files,
        "row_counts": row_counts,
        "contains_raw_chat": True,
        "sensitive_files": ["chat_messages.jsonl"],
        "privacy_boundary": {
            "analysis_dataset_excludes_raw_chat": True,
            "participant_names_exported": False,
            "full_ip_addresses_exported_by_default": False,
            "frontend_provider_secrets_exported": False,
        },
    }
