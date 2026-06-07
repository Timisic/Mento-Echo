from __future__ import annotations

from app.models import (
    ChatMessage,
    ExperimentSession,
    Participant,
    QuestionnaireResponse,
    QuestionnaireScore,
)
from app.questionnaire_config import get_items
from app.services import log_audit
from tests.conftest import import_participants


def responses_for_phase(phase: str) -> dict[str, int | str]:
    responses: dict[str, int | str] = {}
    for item in get_items(phase):  # type: ignore[arg-type]
        if item.scale == "gender_options":
            responses[item.item_key] = "女"
        elif item.scale == "grade_options":
            responses[item.item_key] = "本科三年级"
        elif item.scale == "major_text":
            responses[item.item_key] = "心理学"
        elif item.scale == "age_years":
            responses[item.item_key] = 20
        elif item.attention_check and item.attention_check_expected_value is not None:
            responses[item.item_key] = item.attention_check_expected_value
        else:
            responses[item.item_key] = 4
    return responses


def test_participant_self_registration_generates_sequential_code_with_suffix(client, admin_headers):
    first = client.post("/api/participant/self-register")
    second = client.post("/api/participant/self-register")

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    first_body = first.json()
    second_body = second.json()
    assert first_body["participant_code"].startswith("P500-")
    assert second_body["participant_code"].startswith("P501-")
    assert first_body["session"]["participant_code"] == first_body["participant_code"]
    assert first_body["session"]["status"] == "not_started"

    status_rows = client.get("/api/admin/status", headers=admin_headers).json()["participants"]
    assert [row["participant_code"] for row in status_rows] == [
        first_body["participant_code"],
        second_body["participant_code"],
    ]


def test_self_registration_continues_after_cleanup_high_watermark(client, db_session):
    log_audit(
        db_session,
        admin_id="researcher",
        action="participant_cleanup_under_six_turns",
        target_type="participant_batch",
        metadata={"self_registration_high_watermark_by_prefix": {"P": 518}},
    )
    db_session.commit()

    response = client.post("/api/participant/self-register")

    assert response.status_code == 200, response.text
    assert response.json()["participant_code"].startswith("P519-")


def test_self_registration_stops_after_twenty_two_new_codes(client):
    issued_codes = [
        client.post("/api/participant/self-register").json()["participant_code"] for _ in range(22)
    ]

    blocked = client.post("/api/participant/self-register")

    assert issued_codes[0].startswith("P500-")
    assert issued_codes[-1].startswith("P521-")
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "人数过多，被试已招满"


def test_participant_code_entry_accepts_known_rejects_unknown_and_logs_events(
    client, admin_headers
):
    import_response = import_participants(
        client,
        admin_headers,
        [{"participant_code": "abc-001", "assigned_group": None}],
    )
    assert import_response.status_code == 200

    unknown = client.post("/api/participant/entry", json={"participant_code": "missing"})
    assert unknown.status_code == 404
    assert (
        unknown.json()["detail"]
        == "Participant code not recognized. Please contact the researcher."
    )

    known = client.post("/api/participant/entry", json={"participant_code": " abc-001 "})
    assert known.status_code == 200, known.text
    body = known.json()
    assert body["accepted"] is True
    assert body["session"]["participant_code"] == "ABC-001"
    assert body["session"]["status"] == "not_started"

    events = client.get("/api/admin/behavior-events", headers=admin_headers).json()
    event_types = [event["event_type"] for event in events]
    assert "participant_code_rejected" in event_types
    assert "participant_code_accepted" in event_types
    assert "experiment_session_created" in event_types


def test_reentering_participant_code_resumes_one_session_and_completed_session_is_not_duplicated(
    client, admin_headers
):
    assert (
        import_participants(
            client, admin_headers, [{"participant_code": "P200", "assigned_group": "control"}]
        ).status_code
        == 200
    )

    first = client.post("/api/participant/entry", json={"participant_code": "P200"}).json()[
        "session"
    ]
    second = client.post("/api/participant/entry", json={"participant_code": "p200"}).json()[
        "session"
    ]

    assert second["experiment_session_id"] == first["experiment_session_id"]
    assert second["resume_count"] == 1

    transition = client.post(
        f"/api/admin/sessions/{first['experiment_session_id']}/transition",
        headers=admin_headers,
        json={"status": "pre_survey_submitted", "reason": "test progression"},
    )
    assert transition.status_code == 200
    for next_status in [
        "chat_in_progress",
        "chat_eligible_to_finish",
        "chat_completed",
        "completed",
    ]:
        transition = client.post(
            f"/api/admin/sessions/{first['experiment_session_id']}/transition",
            headers=admin_headers,
            json={"status": next_status, "reason": "test progression"},
        )
        assert transition.status_code == 200, transition.text

    completed_reentry = client.post(
        "/api/participant/entry", json={"participant_code": "P200"}
    ).json()["session"]
    assert completed_reentry["experiment_session_id"] == first["experiment_session_id"]
    assert completed_reentry["status"] == "completed"

    status_rows = client.get("/api/admin/status", headers=admin_headers).json()["participants"]
    assert len(status_rows) == 1
    assert status_rows[0]["experiment_session_id"] == first["experiment_session_id"]


def test_pilot001_opens_non_persistent_test_session_and_skips_admin_collection(
    client, admin_headers, db_session
):
    entry = client.post("/api/participant/entry", json={"participant_code": " pilot001 "})

    assert entry.status_code == 200, entry.text
    session = entry.json()["session"]
    assert session["participant_code"] == "PILOT001"
    assert session["experiment_session_id"] == "pilot001-test-session"
    assert session["assignment_locked"] is True
    assert db_session.query(Participant).count() == 0
    assert db_session.query(ExperimentSession).count() == 0

    assignment = client.post(
        f"/api/participant/sessions/{session['experiment_session_id']}/assignment"
    )
    assert assignment.status_code == 200, assignment.text
    assert assignment.json()["group"] == "pilot"

    pre_definition = client.get(
        f"/api/participant/sessions/{session['experiment_session_id']}/questionnaires/pre"
    )
    post_definition = client.get(
        f"/api/participant/sessions/{session['experiment_session_id']}/questionnaires/post"
    )
    assert pre_definition.status_code == 200, pre_definition.text
    assert post_definition.status_code == 200, post_definition.text
    assert pre_definition.json()["locked"] is False
    assert post_definition.json()["locked"] is False

    pre_submit = client.post(
        f"/api/participant/sessions/{session['experiment_session_id']}/questionnaires/pre/submit",
        json={"responses": responses_for_phase("pre")},
    )
    post_submit = client.post(
        f"/api/participant/sessions/{session['experiment_session_id']}/questionnaires/post/submit",
        json={"responses": responses_for_phase("post")},
    )
    assert pre_submit.status_code == 200, pre_submit.text
    assert post_submit.status_code == 200, post_submit.text
    assert pre_submit.json()["locked"] is False
    assert post_submit.json()["locked"] is False
    assert post_submit.json()["session"]["status"] == "completed"

    dialogue = client.get(f"/api/participant/sessions/{session['experiment_session_id']}/dialogue")
    assert dialogue.status_code == 200, dialogue.text
    assert dialogue.json()["progress"]["eligible_to_finish"] is True
    sent = client.post(
        f"/api/participant/sessions/{session['experiment_session_id']}/dialogue/messages",
        json={"content": "测试一条消息"},
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["assistant_message"]["content"]
    finish = client.post(
        f"/api/participant/sessions/{session['experiment_session_id']}/dialogue/finish",
        json={"decision": "can_end"},
    )
    assert finish.status_code == 200, finish.text
    assert finish.json()["status"] == "chat_completed"

    assert db_session.query(Participant).count() == 0
    assert db_session.query(ExperimentSession).count() == 0
    assert db_session.query(QuestionnaireResponse).count() == 0
    assert db_session.query(QuestionnaireScore).count() == 0
    assert db_session.query(ChatMessage).count() == 0
    assert client.get("/api/admin/status", headers=admin_headers).json()["participants"] == []


def test_invalid_lifecycle_transition_is_rejected(client, admin_headers):
    assert (
        import_participants(
            client, admin_headers, [{"participant_code": "P300", "assigned_group": None}]
        ).status_code
        == 200
    )
    session = client.post("/api/participant/entry", json={"participant_code": "P300"}).json()[
        "session"
    ]

    response = client.post(
        f"/api/admin/sessions/{session['experiment_session_id']}/transition",
        headers=admin_headers,
        json={"status": "completed", "reason": "invalid shortcut"},
    )

    assert response.status_code == 409
    assert "Invalid transition from not_started to completed" in response.json()["detail"]
