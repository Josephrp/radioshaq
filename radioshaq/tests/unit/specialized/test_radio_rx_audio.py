"""Tests for RadioAudioReceptionAgent."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from radioshaq.config.schema import AudioConfig, ResponseMode, TriggerMatchMode
from radioshaq.specialized.radio_rx_audio import (
    ConfirmationManager,
    RadioAudioReceptionAgent,
    TriggerFilter,
)


def test_trigger_filter_disabled() -> None:
    config = AudioConfig(trigger_enabled=False)
    f = TriggerFilter(config)
    assert f.check("any text", 0.5) is True


def test_trigger_filter_confidence_reject() -> None:
    config = AudioConfig(trigger_enabled=True, trigger_min_confidence=0.9)
    f = TriggerFilter(config)
    assert f.check("radioshaq here", 0.5) is False


def test_trigger_filter_contains() -> None:
    config = AudioConfig(
        trigger_enabled=True,
        trigger_phrases=["radioshaq"],
        trigger_match_mode=TriggerMatchMode.CONTAINS,
    )
    f = TriggerFilter(config)
    assert f.check("this is radioshaq calling", 0.8) is True
    assert f.check("hello world", 0.8) is False


@pytest.mark.asyncio
async def test_confirmation_manager_create_and_list() -> None:
    config = AudioConfig(response_timeout_seconds=30.0)
    mgr = ConfirmationManager(config)
    pending = await mgr.create_pending(
        transcript="incoming",
        proposed_message="Ack",
    )
    assert pending.id
    assert pending.status.value == "pending"
    listed = await mgr.list_pending()
    assert len(listed) == 1
    assert listed[0].id == pending.id


@pytest.mark.asyncio
async def test_radio_rx_audio_unknown_action() -> None:
    config = AudioConfig()
    agent = RadioAudioReceptionAgent(config=config)
    result = await agent.execute({"action": "unknown"})
    assert "error" in result
    assert "Unknown action" in result["error"]


@pytest.mark.asyncio
async def test_radio_rx_audio_monitor_no_capture() -> None:
    config = AudioConfig()
    agent = RadioAudioReceptionAgent(config=config, capture_service=None)
    result = await agent.execute({
        "action": "monitor",
        "frequency": 146520000,
        "duration_seconds": 1,
    })
    assert "error" in result
    assert "Audio capture not configured" in result["error"]


@pytest.mark.asyncio
async def test_radio_rx_audio_transcribe_file_no_path() -> None:
    config = AudioConfig()
    agent = RadioAudioReceptionAgent(config=config)
    result = await agent.execute({"action": "transcribe_file"})
    assert "error" in result
    assert "audio_path" in result["error"]
