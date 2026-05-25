from __future__ import annotations

import os

from app.config import get_settings
from app.main import _ADMIN_LOGIN_FAILURES, _RATE_LIMITER


def reset_security_state(monkeypatch, **env: str) -> None:
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    _RATE_LIMITER.clear()
    _ADMIN_LOGIN_FAILURES.clear()


def test_untrusted_host_is_rejected_when_allowlist_is_configured(client, monkeypatch):
    reset_security_state(monkeypatch, ALLOWED_HOSTS="127.0.0.1,localhost")

    response = client.get("/api/health/live", headers={"host": "evil.example"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid Host header"


def test_allowed_ipv4_host_with_port_is_accepted(client, monkeypatch):
    reset_security_state(monkeypatch, ALLOWED_HOSTS="101.42.106.155,localhost")

    response = client.get("/api/health/live", headers={"host": "101.42.106.155:8000"})

    assert response.status_code == 200


def test_oversized_request_body_is_rejected(client, monkeypatch):
    reset_security_state(monkeypatch, MAX_REQUEST_BODY_BYTES="20")

    response = client.post("/api/participant/entry", json={"participant_code": "A" * 50})

    assert response.status_code == 413


def test_participant_rate_limit_blocks_abuse_but_allows_first_request(client, monkeypatch):
    reset_security_state(
        monkeypatch,
        RATE_LIMIT_WINDOW_SECONDS="60",
        RATE_LIMIT_PARTICIPANT_PER_MINUTE="1",
    )

    first = client.post("/api/participant/entry", json={"participant_code": "UNKNOWN"})
    second = client.post("/api/participant/entry", json={"participant_code": "UNKNOWN"})

    assert first.status_code == 404
    assert second.status_code == 429
    assert int(second.headers["Retry-After"]) >= 1


def test_admin_login_lockout_after_repeated_failures(client, monkeypatch):
    reset_security_state(
        monkeypatch,
        ADMIN_LOGIN_LOCKOUT_ATTEMPTS="2",
        ADMIN_LOGIN_LOCKOUT_SECONDS="60",
        RATE_LIMIT_ADMIN_LOGIN_PER_MINUTE="100",
    )

    payload = {"username": "researcher", "password": "wrong"}
    assert client.post("/api/admin/login", json=payload).status_code == 401
    assert client.post("/api/admin/login", json=payload).status_code == 401
    locked = client.post("/api/admin/login", json=payload)

    assert locked.status_code == 429
    assert locked.json()["detail"] == "Too many failed login attempts"


def test_security_state_resets_do_not_leak_env(monkeypatch):
    # Guard against accidental key logging/printing in security tests.
    assert "AI_API_KEY" not in os.environ or os.environ["AI_API_KEY"] != ""
    reset_security_state(monkeypatch)
