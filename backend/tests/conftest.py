from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL", "postgresql+pg8000://mentor_echo:mentor_echo@localhost:5432/mentor_echo"
)
os.environ.setdefault("ADMIN_USERNAME", "researcher")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")
os.environ.setdefault("AI_PROVIDER_NAME", "mock")
os.environ.setdefault("AI_MODEL_NAME", "mock-mentor-echo")

from app.config import get_settings  # noqa: E402
from app.db import get_engine, reset_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402


@pytest.fixture(autouse=True)
def reset_database() -> None:
    get_settings.cache_clear()
    reset_engine()
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    reset_engine()


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/admin/login",
        json={"username": "researcher", "password": "test-admin-password"},
    )
    assert response.status_code == 200, response.text
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def import_participants(client: TestClient, admin_headers: dict[str, str], rows: list[dict[str, str | None]]):
    return client.post("/api/admin/participants/import", headers=admin_headers, json={"participants": rows})


@pytest.fixture
def db_session() -> Session:
    with Session(get_engine()) as session:
        yield session
