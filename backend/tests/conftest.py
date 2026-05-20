from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

DEFAULT_TEST_DATABASE_URL = "postgresql+pg8000://mentor_echo:mentor_echo@localhost:5432/mentor_echo_test"
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)


def ensure_test_database(database_url: str) -> None:
    url = make_url(database_url)
    database_name = url.database or ""
    if "test" not in database_name.lower():
        raise RuntimeError(f"Refusing to run destructive tests against non-test database: {database_name}")
    if not url.drivername.startswith("postgresql"):
        return

    maintenance_url = url.set(database="postgres")
    engine = create_engine(maintenance_url, isolation_level="AUTOCOMMIT", future=True)
    with engine.connect() as connection:
        exists = connection.execute(
            text("select 1 from pg_database where datname = :database_name"),
            {"database_name": database_name},
        ).scalar()
        if not exists:
            escaped_database_name = database_name.replace('"', '""')
            connection.exec_driver_sql(f'create database "{escaped_database_name}"')
    engine.dispose()


ensure_test_database(TEST_DATABASE_URL)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
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


def drop_test_schema(engine) -> None:
    Base.metadata.drop_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("drop table if exists alembic_version"))


@pytest.fixture(autouse=True)
def reset_database() -> None:
    get_settings.cache_clear()
    reset_engine()
    engine = get_engine()
    drop_test_schema(engine)
    Base.metadata.create_all(bind=engine)
    yield
    drop_test_schema(engine)
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
