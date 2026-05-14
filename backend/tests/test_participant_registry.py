from __future__ import annotations

from app.models import Participant
from tests.conftest import import_participants


def test_admin_login_and_import_are_audit_logged(client, admin_headers):
    response = import_participants(
        client,
        admin_headers,
        [
            {"participant_code": " p001 ", "assigned_group": "experiment"},
            {"participant_code": "p002", "assigned_group": ""},
        ],
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"imported_count": 2, "participant_codes": ["P001", "P002"]}

    status_response = client.get("/api/admin/status", headers=admin_headers)
    assert status_response.status_code == 200
    rows = status_response.json()["participants"]
    assert [row["participant_code"] for row in rows] == ["P001", "P002"]
    assert rows[0]["assigned_group_imported"] == "experiment"
    assert rows[1]["assigned_group_imported"] is None
    assert all(row["status"] == "not_started" for row in rows)

    audit_response = client.get("/api/admin/audit-logs", headers=admin_headers)
    assert audit_response.status_code == 200
    actions = [row["action"] for row in audit_response.json()]
    assert actions == ["admin_login", "participant_import"]


def test_duplicate_participant_codes_are_rejected_without_conflicting_records(client, admin_headers):
    duplicate_response = import_participants(
        client,
        admin_headers,
        [
            {"participant_code": "same", "assigned_group": "experiment"},
            {"participant_code": " SAME ", "assigned_group": "control"},
        ],
    )

    assert duplicate_response.status_code == 400
    assert duplicate_response.json()["detail"]["errors"][0]["message"] == "duplicate participant_code in import"

    status_response = client.get("/api/admin/status", headers=admin_headers)
    assert status_response.status_code == 200
    assert status_response.json()["participants"] == []

    first = import_participants(
        client,
        admin_headers,
        [{"participant_code": "P100", "assigned_group": None}],
    )
    assert first.status_code == 200
    second = import_participants(
        client,
        admin_headers,
        [{"participant_code": "p100", "assigned_group": None}],
    )
    assert second.status_code == 400
    assert second.json()["detail"]["errors"][0]["message"] == "participant_code already exists"


def test_participant_model_has_no_name_storage_column():
    column_names = {column.name for column in Participant.__table__.columns}

    assert "participant_code" in column_names
    assert not any("name" in column_name for column_name in column_names)
