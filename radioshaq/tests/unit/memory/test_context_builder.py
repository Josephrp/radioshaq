"""Unit tests for radioshaq.memory.context_builder."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from radioshaq.memory.context_builder import build_memory_context


@pytest.mark.asyncio
async def test_build_memory_context_structure() -> None:
    """Assert return has system_prefix, messages, metadata."""
    memory = AsyncMock()
    memory.get_core_blocks = AsyncMock(return_value={
        "user": "Operator W1ABC",
        "identity": "RadioShaq assistant",
        "ideaspace": "",
        "system_instructions": "Be concise.",
    })
    memory.load_messages = AsyncMock(return_value=[])
    memory.load_daily_summaries = AsyncMock(return_value=[])

    tz = ZoneInfo("America/New_York")
    result = await build_memory_context(
        memory,
        "W1ABC",
        recent_limit=40,
        summary_days=7,
        timezone=tz,
    )

    assert "system_prefix" in result
    assert "messages" in result
    assert "metadata" in result
    assert result["metadata"].get("callsign") == "W1ABC"
    assert "Current Time" in result["system_prefix"]
    assert "Core Memory" in result["system_prefix"]
    assert "User" in result["system_prefix"]
    assert "Identity" in result["system_prefix"]


@pytest.mark.asyncio
async def test_build_memory_context_includes_summaries() -> None:
    """Assert daily summaries section when present."""
    memory = AsyncMock()
    memory.get_core_blocks = AsyncMock(return_value={
        "user": "",
        "identity": "",
        "ideaspace": "",
        "system_instructions": "",
    })
    memory.load_messages = AsyncMock(return_value=[])
    memory.load_daily_summaries = AsyncMock(return_value=[
        {"summary_date": "2026-03-03", "content": "Discussed antenna setup."},
    ])

    tz = ZoneInfo("America/New_York")
    result = await build_memory_context(
        memory,
        "K5XYZ",
        recent_limit=40,
        summary_days=7,
        timezone=tz,
    )

    assert "Recent Days" in result["system_prefix"] or "summary" in result["system_prefix"].lower()
    assert "2026-03-03" in result["system_prefix"]
    assert "antenna" in result["system_prefix"].lower()
