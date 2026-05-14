from __future__ import annotations


def test_health_reports_database_connectivity(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"app": "ok", "database": {"ok": True}}
