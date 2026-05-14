from __future__ import annotations

from tests.conftest import import_participants


def test_participant_code_entry_accepts_known_rejects_unknown_and_logs_events(client, admin_headers):
    import_response = import_participants(
        client,
        admin_headers,
        [{"participant_code": "abc-001", "assigned_group": None}],
    )
    assert import_response.status_code == 200

    unknown = client.post("/api/participant/entry", json={"participant_code": "missing"})
    assert unknown.status_code == 404
    assert unknown.json()["detail"] == "Participant code not recognized. Please contact the researcher."

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


def test_reentering_participant_code_resumes_one_session_and_completed_session_is_not_duplicated(client, admin_headers):
    assert import_participants(
        client, admin_headers, [{"participant_code": "P200", "assigned_group": "control"}]
    ).status_code == 200

    first = client.post("/api/participant/entry", json={"participant_code": "P200"}).json()["session"]
    second = client.post("/api/participant/entry", json={"participant_code": "p200"}).json()["session"]

    assert second["experiment_session_id"] == first["experiment_session_id"]
    assert second["resume_count"] == 1

    transition = client.post(
        f"/api/admin/sessions/{first['experiment_session_id']}/transition",
        headers=admin_headers,
        json={"status": "pre_survey_submitted", "reason": "test progression"},
    )
    assert transition.status_code == 200
    for next_status in ["chat_in_progress", "chat_eligible_to_finish", "chat_completed", "completed"]:
        transition = client.post(
            f"/api/admin/sessions/{first['experiment_session_id']}/transition",
            headers=admin_headers,
            json={"status": next_status, "reason": "test progression"},
        )
        assert transition.status_code == 200, transition.text

    completed_reentry = client.post("/api/participant/entry", json={"participant_code": "P200"}).json()["session"]
    assert completed_reentry["experiment_session_id"] == first["experiment_session_id"]
    assert completed_reentry["status"] == "completed"

    status_rows = client.get("/api/admin/status", headers=admin_headers).json()["participants"]
    assert len(status_rows) == 1
    assert status_rows[0]["experiment_session_id"] == first["experiment_session_id"]


def test_invalid_lifecycle_transition_is_rejected(client, admin_headers):
    assert import_participants(
        client, admin_headers, [{"participant_code": "P300", "assigned_group": None}]
    ).status_code == 200
    session = client.post("/api/participant/entry", json={"participant_code": "P300"}).json()["session"]

    response = client.post(
        f"/api/admin/sessions/{session['experiment_session_id']}/transition",
        headers=admin_headers,
        json={"status": "completed", "reason": "invalid shortcut"},
    )

    assert response.status_code == 409
    assert "Invalid transition from not_started to completed" in response.json()["detail"]
