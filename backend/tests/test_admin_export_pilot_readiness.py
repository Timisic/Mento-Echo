from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from datetime import timedelta

from app.models import AuditLog, BehaviorEvent, ExperimentSession
from app.services import DialogueService
from tests.conftest import import_participants
from tests.test_questionnaire_flow import responses_for_phase


def _csv_rows(zip_file: zipfile.ZipFile, path: str) -> list[dict[str, str]]:
    with zip_file.open(path) as handle:
        text = io.TextIOWrapper(handle, encoding="utf-8", newline="")
        return list(csv.DictReader(text))


def _jsonl_rows(zip_file: zipfile.ZipFile, path: str) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in zip_file.read(path).decode("utf-8").splitlines()
        if line.strip()
    ]


def _member(names: list[str], suffix: str) -> str:
    matches = [name for name in names if name.endswith(suffix)]
    assert len(matches) == 1, f"expected one member ending with {suffix}, got {matches}"
    return matches[0]


def _complete_pilot_flow(client, admin_headers, db_session, code: str = "PILOT01") -> str:
    assert import_participants(
        client, admin_headers, [{"participant_code": code, "assigned_group": "experiment"}]
    ).status_code == 200
    entry = client.post("/api/participant/entry", json={"participant_code": code})
    assert entry.status_code == 200, entry.text
    session_id = entry.json()["session"]["experiment_session_id"]

    pre = client.post(
        f"/api/participant/sessions/{session_id}/questionnaires/pre/submit",
        json={"responses": responses_for_phase("pre", numeric_value=4)},
    )
    assert pre.status_code == 200, pre.text
    assignment = client.post(f"/api/participant/sessions/{session_id}/assignment")
    assert assignment.status_code == 200
    assert assignment.json()["assignment_source"] == "imported"

    state = client.get(f"/api/participant/sessions/{session_id}/dialogue")
    assert state.status_code == 200, state.text
    session = db_session.get(ExperimentSession, session_id)
    assert session is not None and session.chat_started_at is not None
    session.chat_started_at = session.chat_started_at - timedelta(
        seconds=DialogueService.MIN_ELAPSED_SECONDS + 10
    )
    db_session.commit()

    for index in range(10):
        message = client.post(
            f"/api/participant/sessions/{session_id}/dialogue/messages",
            json={"content": f"raw identity reflection text {index}"},
        )
        assert message.status_code == 200, message.text
    finish = client.post(f"/api/participant/sessions/{session_id}/dialogue/finish")
    assert finish.status_code == 200, finish.text
    assert finish.json()["status"] == "chat_completed"

    post = client.post(
        f"/api/participant/sessions/{session_id}/questionnaires/post/submit",
        json={"responses": responses_for_phase("post", numeric_value=5)},
    )
    assert post.status_code == 200, post.text
    assert post.json()["session"]["status"] == "completed"
    return session_id


def test_admin_dashboard_reset_exclusion_controls_and_audit_events(client, admin_headers, db_session):
    assert import_participants(
        client, admin_headers, [{"participant_code": "ADMIN01", "assigned_group": "control"}]
    ).status_code == 200
    session_id = client.post("/api/participant/entry", json={"participant_code": "ADMIN01"}).json()[
        "session"
    ]["experiment_session_id"]
    assert client.post(
        f"/api/participant/sessions/{session_id}/questionnaires/pre/submit",
        json={"responses": responses_for_phase("pre")},
    ).status_code == 200
    assert client.get(f"/api/participant/sessions/{session_id}/dialogue").status_code == 200

    status = client.get("/api/admin/status", headers=admin_headers)
    assert status.status_code == 200
    row = status.json()["participants"][0]
    assert row["participant_code"] == "ADMIN01"
    assert row["group"] == "control"
    assert row["assignment_source"] == "imported"
    assert row["status"] == "chat_in_progress"
    assert row["pre_survey_submitted"] is True
    assert row["post_survey_submitted"] is False
    assert row["dialogue_completion_eligible"] is False
    assert row["dialogue_completed"] is False
    assert row["completed"] is False
    assert row["excluded"] is False
    assert row["exclusion_reason"] is None
    assert isinstance(row["dialogue_elapsed_minutes"], (int, float))
    assert row["last_seen_at"] is not None

    missing_reset_reason = client.post(
        f"/api/admin/sessions/{session_id}/questionnaires/pre/reset",
        headers=admin_headers,
        json={"reason": " "},
    )
    assert missing_reset_reason.status_code == 422

    reset = client.post(
        f"/api/admin/sessions/{session_id}/questionnaires/pre/reset",
        headers=admin_headers,
        json={"reason": "researcher correction before pilot"},
    )
    assert reset.status_code == 200, reset.text

    missing_exclusion_reason = client.post(
        f"/api/admin/sessions/{session_id}/exclusion",
        headers=admin_headers,
        json={"excluded": True, "reason": " "},
    )
    assert missing_exclusion_reason.status_code == 422

    excluded = client.post(
        f"/api/admin/sessions/{session_id}/exclusion",
        headers=admin_headers,
        json={"excluded": True, "reason": "pilot invalid attention pattern"},
    )
    assert excluded.status_code == 200, excluded.text
    assert excluded.json()["status"] == "excluded"
    assert excluded.json()["excluded"] is True

    status_after = client.get("/api/admin/status", headers=admin_headers).json()["participants"][0]
    assert status_after["status"] == "excluded"
    assert status_after["excluded"] is True
    assert status_after["exclusion_reason"] == "pilot invalid attention pattern"

    audit_actions = [row.action for row in db_session.query(AuditLog).order_by(AuditLog.created_at)]
    assert "pre_survey_reset" in audit_actions
    assert "session_excluded" in audit_actions
    event_types = [row.event_type for row in db_session.query(BehaviorEvent).order_by(BehaviorEvent.created_at)]
    assert "admin_stage_reset" in event_types
    assert "session_excluded" in event_types


def test_export_package_structure_content_and_privacy_boundaries(client, admin_headers, db_session):
    _complete_pilot_flow(client, admin_headers, db_session, code="EXPORT01")

    export = client.post("/api/admin/export", headers=admin_headers)
    assert export.status_code == 200, export.text
    assert export.headers["content-type"] == "application/zip"

    with zipfile.ZipFile(io.BytesIO(export.content)) as archive:
        names = archive.namelist()
        required_suffixes = {
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
        }
        assert {_member(names, suffix).split("/")[-1] for suffix in required_suffixes} == required_suffixes

        readme = archive.read(_member(names, "README.md")).decode("utf-8")
        assert "SENSITIVE RAW CHAT" in readme
        assert "10 participant turns + 15 minutes" in readme
        assert "mock-mentor-echo" in readme

        manifest = json.loads(archive.read(_member(names, "export_manifest.json")))
        assert manifest["contains_raw_chat"] is True
        assert "chat_messages.jsonl" in manifest["sensitive_files"]
        assert manifest["row_counts"]["participants.csv"] == 1
        assert manifest["row_counts"]["analysis_dataset.csv"] == 1
        assert manifest["files"]["chat_messages.jsonl"]["classification"] == "sensitive_raw_chat"

        participants = _csv_rows(archive, _member(names, "participants.csv"))
        assert participants[0]["participant_code"] == "EXPORT01"
        assert participants[0]["excluded"] == "False"

        sessions = _csv_rows(archive, _member(names, "experiment_sessions.csv"))
        assert sessions[0]["status"] == "completed"
        assert sessions[0]["met_min_turns"] == "True"
        assert sessions[0]["met_min_duration"] == "True"
        assert int(sessions[0]["participant_turn_count"]) == 10

        analysis = _csv_rows(archive, _member(names, "analysis_dataset.csv"))
        assert len(analysis) == 1
        analysis_row = analysis[0]
        assert analysis_row["participant_code"] == "EXPORT01"
        assert analysis_row["completed"] == "True"
        assert analysis_row["excluded"] == "False"
        assert "raw identity reflection text" not in json.dumps(analysis_row, ensure_ascii=False)
        assert not any("content" in column or "message" in column for column in analysis_row)
        assert any(column.endswith("_change") for column in analysis_row)

        chat_messages = _jsonl_rows(archive, _member(names, "chat_messages.jsonl"))
        assert any("raw identity reflection text" in str(message["content"]) for message in chat_messages)
        assert {message["role"] for message in chat_messages} == {"participant", "assistant"}

        behavior_events = _jsonl_rows(archive, _member(names, "behavior_events.jsonl"))
        event_types = {str(event["event_type"]) for event in behavior_events}
        assert {
            "participant_code_accepted",
            "pre_survey_submitted",
            "group_assignment_created",
            "dialogue_started",
            "participant_message_saved",
            "ai_response_saved",
            "completion_eligibility_reached",
            "dialogue_completed",
            "post_survey_submitted",
            "data_export_requested",
            "data_export_completed",
        } <= event_types

        audits = _csv_rows(archive, _member(names, "audit_logs.csv"))
        audit_actions = {row["action"] for row in audits}
        assert {"participant_import", "data_export_requested", "data_export_completed"} <= audit_actions

        ai_calls = _csv_rows(archive, _member(names, "ai_call_records.csv"))
        assert len(ai_calls) == 10
        assert {row["provider_name"] for row in ai_calls} == {"mock"}
        assert all(row["error_code"] == "" for row in ai_calls)

        export_text = "\n".join(
            archive.read(name).decode("utf-8") for name in names if not name.endswith("/")
        )
        assert "AI_API_KEY" not in export_text
        assert "api_key" not in export_text.lower()
        assert not re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", export_text)


def test_end_to_end_pilot_regression_flow_reaches_dashboard_and_export(
    client, admin_headers, db_session
):
    _complete_pilot_flow(client, admin_headers, db_session, code="E2E01")

    dashboard = client.get("/api/admin/status", headers=admin_headers)
    assert dashboard.status_code == 200
    row = dashboard.json()["participants"][0]
    assert row["participant_code"] == "E2E01"
    assert row["status"] == "completed"
    assert row["completed"] is True
    assert row["dialogue_completion_eligible"] is True
    assert row["post_survey_submitted"] is True

    export = client.post("/api/admin/export", headers=admin_headers)
    assert export.status_code == 200
    with zipfile.ZipFile(io.BytesIO(export.content)) as archive:
        analysis = _csv_rows(archive, _member(archive.namelist(), "analysis_dataset.csv"))
    assert len(analysis) == 1
    assert analysis[0]["participant_code"] == "E2E01"
