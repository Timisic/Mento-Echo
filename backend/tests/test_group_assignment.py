from __future__ import annotations

from app.config import get_settings
from tests.conftest import import_participants


def test_pilot_single_assignment_ignores_grouping_and_is_visible_in_admin_status(client, admin_headers):
    assert import_participants(
        client, admin_headers, [{"participant_code": "P400", "assigned_group": "experiment"}]
    ).status_code == 200
    session = client.post("/api/participant/entry", json={"participant_code": "P400"}).json()["session"]

    assignment = client.post(
        f"/api/participant/sessions/{session['experiment_session_id']}/assignment"
    ).json()

    assert assignment["group"] == "pilot"
    assert assignment["assignment_source"] == "pilot_single"
    assert assignment["assignment_locked"] is True

    status = client.get("/api/admin/status", headers=admin_headers).json()["participants"][0]
    assert status["group"] == "pilot"
    assert status["assignment_source"] == "pilot_single"
    assert status["assignment_locked"] is True


def test_grouped_mode_imported_assignment_is_applied(client, admin_headers, monkeypatch):
    monkeypatch.setenv("STUDY_MODE", "grouped")
    get_settings.cache_clear()
    assert import_participants(
        client, admin_headers, [{"participant_code": "P450", "assigned_group": "experiment"}]
    ).status_code == 200
    session = client.post("/api/participant/entry", json={"participant_code": "P450"}).json()["session"]

    assignment = client.post(f"/api/participant/sessions/{session['experiment_session_id']}/assignment").json()

    assert assignment["group"] == "experiment"
    assert assignment["assignment_source"] == "imported"


def test_grouped_mode_blank_assignment_randomizes_once_and_does_not_rerandomize(client, admin_headers, monkeypatch):
    monkeypatch.setenv("STUDY_MODE", "grouped")
    get_settings.cache_clear()
    assert import_participants(
        client, admin_headers, [{"participant_code": "P500", "assigned_group": ""}]
    ).status_code == 200
    session = client.post("/api/participant/entry", json={"participant_code": "P500"}).json()["session"]

    first = client.post(f"/api/participant/sessions/{session['experiment_session_id']}/assignment").json()
    second = client.post(f"/api/participant/sessions/{session['experiment_session_id']}/assignment").json()
    reentered_session = client.post("/api/participant/entry", json={"participant_code": "P500"}).json()["session"]
    third = client.post(
        f"/api/participant/sessions/{reentered_session['experiment_session_id']}/assignment"
    ).json()

    assert first["assignment_source"] == "randomized"
    assert first["group"] in {"experiment", "control"}
    assert second == first
    assert third == first

    events = client.get("/api/admin/behavior-events", headers=admin_headers).json()
    assignment_events = [event for event in events if event["event_type"] == "group_assignment_created"]
    assert len(assignment_events) == 1
    assert assignment_events[0]["metadata"]["assignment_source"] == "randomized"
