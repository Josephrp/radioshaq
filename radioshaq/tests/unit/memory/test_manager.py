"""Unit tests for radioshaq.memory.manager.MemoryManager.

Requires PostgreSQL with memory tables (run migration first).
Uses TEST_DATABASE_URL or env_overrides; skips if DB unavailable or tables missing.
"""

from __future__ import annotations

import asyncio
import os

import pytest

from radioshaq.memory.manager import MemoryManager, _normalize_callsign


def test_normalize_callsign() -> None:
    assert _normalize_callsign("  w1abc  ") == "W1ABC"
    assert _normalize_callsign("") == "UNKNOWN"
    assert _normalize_callsign("K5XYZ-1") == "K5XYZ-1"


@pytest.fixture
def db_url() -> str:
    """Same default as tests/conftest._TEST_DB_URL so migrations apply to this DB."""
    return os.environ.get(
        "TEST_DATABASE_URL",
        os.environ.get(
            "RADIOSHAQ_DATABASE__POSTGRES_URL",
            "postgresql+asyncpg://radioshaq:radioshaq@127.0.0.1:5434/radioshaq",
        ),
    )


# Max time to wait for DB probe so tests don't hang when Postgres is unreachable
_MEMORY_DB_PROBE_TIMEOUT = 8.0


@pytest.fixture
async def memory_manager(_run_db_migrations: None, db_url: str):
    """MemoryManager with test DB; migrations run first so memory_* tables exist."""
    try:
        mgr = MemoryManager(db_url)
        await asyncio.wait_for(mgr.get_core_blocks("TESTCALL"), timeout=_MEMORY_DB_PROBE_TIMEOUT)
    except asyncio.TimeoutError:
        pytest.skip(f"MemoryManager DB probe timed out after {_MEMORY_DB_PROBE_TIMEOUT}s (is Postgres running?)")
    except Exception as e:
        pytest.skip(f"MemoryManager requires migrated DB: {e}")
    yield mgr
    await mgr.close()


@pytest.mark.asyncio
async def test_manager_get_core_blocks(memory_manager: MemoryManager) -> None:
    blocks = await memory_manager.get_core_blocks("TESTCALL")
    assert isinstance(blocks, dict)
    assert "system_instructions" in blocks
    for key in ("user", "identity", "ideaspace"):
        assert key in blocks


@pytest.mark.asyncio
async def test_manager_update_block(memory_manager: MemoryManager) -> None:
    success, msg = await memory_manager.update_block("TESTCALL", "user", "Test operator info")
    assert success is True
    content = await memory_manager.get_block("TESTCALL", "user")
    assert "Test operator info" in content


@pytest.mark.asyncio
async def test_manager_append_to_block(memory_manager: MemoryManager) -> None:
    await memory_manager.update_block("TESTCALL", "ideaspace", "Goal: test")
    success, _ = await memory_manager.append_to_block("TESTCALL", "ideaspace", "Appended line")
    assert success is True
    content = await memory_manager.get_block("TESTCALL", "ideaspace")
    assert "test" in content and "Appended" in content


@pytest.mark.asyncio
async def test_manager_load_messages(memory_manager: MemoryManager) -> None:
    await memory_manager.append_messages("TESTCALL", [
        ("user", "Hello", None, None),
        ("assistant", "Hi there", None, None),
    ])
    messages = await memory_manager.load_messages("TESTCALL", limit=10)
    assert isinstance(messages, list)
    assert len(messages) >= 2
    roles = [m.get("role") for m in messages]
    assert "user" in roles and "assistant" in roles


@pytest.mark.asyncio
async def test_manager_invalid_block_type(memory_manager: MemoryManager) -> None:
    success, msg = await memory_manager.update_block("TESTCALL", "invalid_type", "x")
    assert success is False
    assert "Invalid" in msg


@pytest.mark.asyncio
async def test_manager_delete_messages_older_than_future_cutoff_returns_zero(memory_manager: MemoryManager) -> None:
    """delete_messages_older_than with a cutoff in the future deletes nothing and returns 0."""
    from datetime import datetime, timedelta, timezone
    future = datetime.now(timezone.utc) + timedelta(days=365)
    n = await memory_manager.delete_messages_older_than(future, limit=10_000)
    assert n == 0
