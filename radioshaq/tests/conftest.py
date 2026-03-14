"""Pytest configuration and shared fixtures for RadioShaq tests."""

from __future__ import annotations

import os
from typing import Any, Generator
from urllib.parse import urlparse

import pytest

# Default test DB URL (same as env_overrides); migrations need DATABASE_URL set
_TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://radioshaq:radioshaq@127.0.0.1:5434/radioshaq",
)


def _ensure_test_database_exists(url: str) -> None:
    """Create the test database if it does not exist (connect to 'postgres' to run CREATE DATABASE)."""
    parsed = urlparse(url)
    path = (parsed.path or "/").lstrip("/")
    db_name = (path.split("/")[0] or "radioshaq").split("?")[0]
    try:
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    except ImportError:
        return  # no psycopg2, skip create; let migration fail with real error
    try:
        conn = psycopg2.connect(
            host=parsed.hostname or "127.0.0.1",
            port=parsed.port or 5434,
            user=parsed.username or "radioshaq",
            password=parsed.password or "radioshaq",
            dbname="postgres",
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        if cur.fetchone() is None:
            cur.execute(f'CREATE DATABASE "{db_name}"')
        cur.close()
        conn.close()
    except Exception:
        pass  # e.g. connection refused; migration will fail with clearer error


@pytest.fixture(scope="session")
def _run_db_migrations() -> None:
    """Run Alembic migrations so test DB has current schema (e.g. notify_opt_out_at_sms)."""
    try:
        _ensure_test_database_exists(_TEST_DB_URL)
        prev = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = _TEST_DB_URL
        from radioshaq.scripts.alembic_runner import upgrade
        code = upgrade()
        if prev is not None:
            os.environ["DATABASE_URL"] = prev
        else:
            os.environ.pop("DATABASE_URL", None)
        if code != 0:
            pytest.skip("Alembic upgrade failed (is Postgres running?)")
    except Exception as e:
        pytest.skip(f"Migrations unavailable: {e}")


@pytest.fixture(scope="session")
def env_overrides() -> dict[str, str]:
    """Override env for tests (no real API keys, local DB optional)."""
    return {
        "RADIOSHAQ_MODE": "field",
        "JWT_SECRET": "test-secret",
        # Use HackRF broker mode by default in tests so compliance and service
        # client tests exercise the TX endpoints without requiring real hardware.
        "SDR_TYPE": "hackrf",
        "RADIOSHAQ_DATABASE__POSTGRES_URL": _TEST_DB_URL,
        # Disable external ElevenLabs calls and require explicit API keys in tests.
        "ELEVENLABS_API_KEY": "",
        "RADIOSHAQ_AUDIO__ELEVEN_VOICE_ISOLATOR_ENABLED": "false",
        "ELEVEN_VOICE_ISOLATOR_ENABLED": "false",
        # Ensure Twilio is treated as unconfigured so SMS/WhatsApp tests match CI.
        "RADIOSHAQ_TWILIO__ACCOUNT_SID": "",
        "RADIOSHAQ_TWILIO__AUTH_TOKEN": "",
        "RADIOSHAQ_TWILIO__FROM_NUMBER": "",
        "RADIOSHAQ_TWILIO__WHATSAPP_FROM": "",
        # Make sure callsign registry is not required by default in unit tests.
        "RADIOSHAQ_RADIO__CALLSIGN_REGISTRY_REQUIRED": "false",
        "RADIOSHAQ_MEMORY__HINDSIGHT_ENABLED": "false",
    }


@pytest.fixture(autouse=True)
def patch_env(env_overrides: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    """Apply env_overrides for tests that need config."""
    for k, v in env_overrides.items():
        monkeypatch.setenv(k, v)


@pytest.fixture
def client(_run_db_migrations: None) -> Generator[Any, None, None]:
    """FastAPI test client (lifespan handled). Migrations run before first use."""
    from fastapi.testclient import TestClient

    from radioshaq.api.server import app

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


@pytest.fixture
def auth_headers_callsign(client: Any) -> dict[str, str]:
    """Headers with JWT whose station_id matches a callsign for memory routes."""
    r = client.post(
        "/auth/token",
        params={"subject": "mem-test", "role": "field", "station_id": "W1ABC"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def memory_manager(env_overrides: dict[str, str]):
    """MemoryManager with test DB URL. Caller must close or use as context."""
    from radioshaq.memory import MemoryManager
    url = env_overrides.get(
        "RADIOSHAQ_DATABASE__POSTGRES_URL",
        "postgresql+asyncpg://radioshaq:radioshaq@127.0.0.1:5434/radioshaq_test",
    )
    mgr = MemoryManager(url)
    yield mgr
    await mgr.close()
