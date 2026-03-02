"""Pytest configuration and shared fixtures for SHAKODS tests."""

from __future__ import annotations

import os
from typing import Any, Generator

import pytest


@pytest.fixture(scope="session")
def env_overrides() -> dict[str, str]:
    """Override env for tests (no real API keys, local DB optional)."""
    return {
        "SHAKODS_MODE": "field",
        "JWT_SECRET": "test-secret",
        "SHAKODS_DATABASE__POSTGRES_URL": os.environ.get(
            "TEST_DATABASE_URL",
            "postgresql+asyncpg://shakods:shakods@127.0.0.1:5434/shakods",
        ),
    }


@pytest.fixture(autouse=True)
def patch_env(env_overrides: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    """Apply env_overrides for tests that need config."""
    for k, v in env_overrides.items():
        monkeypatch.setenv(k, v)


@pytest.fixture
def client() -> Generator[Any, None, None]:
    """FastAPI test client (lifespan handled)."""
    from fastapi.testclient import TestClient

    from shakods.api.server import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(client: Any) -> dict[str, str]:
    """Headers with valid JWT for API tests."""
    r = client.post(
        "/auth/token",
        params={"subject": "test-user", "role": "field", "station_id": "TEST-01"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
