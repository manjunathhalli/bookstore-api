"""Shared pytest fixtures (Feature: Pytest).

Three swaps make the whole app testable with **zero external services**
(no MySQL, no Redis, no Celery worker), which is exactly why they're all done
here in one place instead of scattered through test files:

1. **Database** — ``app.core.database.engine``/``SessionLocal`` are replaced
   with an in-memory SQLite database *before* ``app.main`` is imported.
   ``get_db`` looks up ``SessionLocal`` by name at call time (not at import
   time), so every router that already did ``from app.core.database import
   get_db`` automatically starts using the test database too — see the note
   in ``app/core/database.py``.
2. **Celery** — ``task_always_eager`` makes ``.delay()`` run the task
   synchronously, in-process, instead of publishing to a Redis broker that
   isn't running. ``cache+memory://`` as the result backend means
   ``AsyncResult(task_id)`` can still look the result back up afterwards
   (matching how the real report-status endpoint polls it), purely in memory.
3. **Redis cache** — left untouched. `app/books/cache.py` already treats a
   connection failure as a cache miss (see its ``try/except``), so with no
   Redis server running these tests simply exercise the "cache is down, fall
   back to the database" path for free.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.core.database as database_module

_TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # one shared connection -> the in-memory DB persists
)
database_module.engine = _TEST_ENGINE
database_module.SessionLocal = sessionmaker(
    bind=_TEST_ENGINE, autocommit=False, autoflush=False, future=True
)

from app.core.celery_app import celery_app  # noqa: E402  (must run before app.main import)

celery_app.conf.update(
    task_always_eager=True,
    task_eager_propagates=True,
    task_store_eager_result=True,
    result_backend="cache+memory://",
)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402  (picks up the patched engine above)


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def register_and_login(client: TestClient, role: str, email: str, password: str = "secret123") -> dict:
    """Register a fresh user through the real API and return auth headers."""
    client.post(
        "/api/register",
        json={
            "role": role,
            "first_name": "Test",
            "last_name": "User",
            "phone_no": "9876543210",
            "email": email,
            "password": password,
            "confirm_password": password,
        },
    )
    response = client.post("/api/login", json={"email": email, "password": password})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_headers(client: TestClient) -> dict:
    return register_and_login(client, "admin", "admin@example.com")


@pytest.fixture()
def user_headers(client: TestClient) -> dict:
    return register_and_login(client, "user", "shopper@example.com")
