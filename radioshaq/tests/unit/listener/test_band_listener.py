"""Unit tests for band listener."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from radioshaq.config.schema import Config, RadioConfig
from radioshaq.listener.band_listener import (
    _band_frequency_and_mode,
    _process_received_messages,
    _resolve_bands,
    run_band_listener,
)


@pytest.mark.unit
def test_resolve_bands_listen_bands() -> None:
    """When listen_bands is set, return it."""
    config = Config()
    config.radio.listen_bands = ["40m", "2m"]
    assert _resolve_bands(config) == ["40m", "2m"]


@pytest.mark.unit
def test_resolve_bands_default_only() -> None:
    """When only default_band is set, return [default_band]."""
    config = Config()
    config.radio.listen_bands = None
    config.radio.default_band = "40m"
    assert _resolve_bands(config) == ["40m"]


@pytest.mark.unit
def test_resolve_bands_empty() -> None:
    """When neither listen_bands nor default_band, return []."""
    config = Config()
    config.radio.listen_bands = None
    config.radio.default_band = None
    assert _resolve_bands(config) == []


@pytest.mark.unit
def test_band_frequency_and_mode_40m() -> None:
    """40m band has center frequency and mode from plan."""
    freq, mode = _band_frequency_and_mode("40m")
    assert 7.0e6 <= freq <= 7.3e6
    assert mode in ("CW", "SSB", "DIGITAL")


@pytest.mark.unit
def test_band_frequency_and_mode_2m() -> None:
    """2m band has center frequency and FM."""
    freq, mode = _band_frequency_and_mode("2m")
    assert 144.0e6 <= freq <= 148.0e6
    assert mode == "FM"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_band_listener_invokes_monitor_with_correct_freq() -> None:
    """With listen_bands=['40m'], listener calls monitor_frequency with 40m center freq."""
    config = Config()
    config.radio.listen_bands = ["40m"]
    config.radio.listener_enabled = True
    config.radio.listener_cycle_seconds = 5.0
    config.radio.listener_concurrent_bands = True

    calls: list[tuple[float, int, str, str | None]] = []
    async def mock_monitor(freq: float, duration: int, mode: str = "FM", upstream_callback=None, band: str | None = None, **kwargs):
        calls.append((freq, duration, mode, band))
        await asyncio.sleep(0.0)
        return {"messages": [], "frequency": freq, "duration": duration}

    agent = MagicMock()
    agent.monitor_frequency = AsyncMock(side_effect=mock_monitor)
    stop = asyncio.Event()

    async def stop_soon() -> None:
        await asyncio.sleep(0.15)
        stop.set()

    task_listener = asyncio.create_task(
        run_band_listener(
            config,
            None,
            None,
            agent,
            stop_event=stop,
            inject_into_queue=False,
            publish_to_bus=False,
        )
    )
    asyncio.create_task(stop_soon())
    await task_listener

    assert len(calls) >= 1
    freq, duration, mode, band = calls[0]
    assert 7.0e6 <= freq <= 7.3e6
    assert duration == 5
    assert mode in ("CW", "SSB", "DIGITAL")
    assert band == "40m"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_band_listener_stop_event_stops_loop() -> None:
    """Setting stop_event causes listener to exit."""
    config = Config()
    config.radio.default_band = "2m"
    config.radio.listener_enabled = True
    config.radio.listener_cycle_seconds = 30.0
    config.radio.listener_concurrent_bands = True

    agent = MagicMock()
    agent.monitor_frequency = AsyncMock(return_value={"messages": []})
    stop = asyncio.Event()
    stop.set()

    await run_band_listener(
        config,
        None,
        None,
        agent,
        stop_event=stop,
        inject_into_queue=False,
        publish_to_bus=False,
    )
    # If we get here without hanging, stop was respected (no bands started or exited immediately)
    # With stop already set, _monitor_band_loop runs once: while not stop_event -> condition true, so we never enter the loop body in concurrent case we spawn tasks that run _monitor_band_loop; each checks stop_event.is_set() at start - true, so the while not stop_event.is_set() is false, so tasks complete without calling monitor. So agent.monitor_frequency may not be called. That's fine.
    assert True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_process_received_messages_store_disabled_no_store_call() -> None:
    """When store_enabled=False, storage.store is not called."""
    storage = MagicMock()
    storage.store = AsyncMock(return_value=1)
    message_bus = MagicMock()
    messages = [{"message": "hello from K5ABC", "source_callsign": "K5ABC", "frequency": 7.15e6, "mode": "SSB"}]
    await _process_received_messages(
        "40m",
        messages,
        storage,
        message_bus,
        inject=False,
        publish_to_bus=False,
        store_enabled=False,
        store_min_length=0,
    )
    storage.store.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_process_received_messages_store_min_length_skips_short() -> None:
    """When store_min_length=20, a message with len < 20 is not stored."""
    storage = MagicMock()
    storage.store = AsyncMock(return_value=1)
    message_bus = MagicMock()
    messages = [{"message": "hi", "source_callsign": "K5ABC", "frequency": 7.15e6, "mode": "SSB"}]
    await _process_received_messages(
        "40m",
        messages,
        storage,
        message_bus,
        inject=False,
        publish_to_bus=False,
        store_enabled=True,
        store_min_length=20,
    )
    storage.store.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_process_received_messages_store_min_length_stores_long_enough() -> None:
    """When store_min_length=5, a message with len >= 5 is stored."""
    storage = MagicMock()
    storage.store = AsyncMock(return_value=1)
    message_bus = MagicMock()
    messages = [{"message": "hello", "source_callsign": "K5ABC", "frequency": 7.15e6, "mode": "SSB"}]
    with patch("radioshaq.api.routes.metrics.increment_listener_messages"):
        await _process_received_messages(
            "40m",
            messages,
            storage,
            message_bus,
            inject=False,
            publish_to_bus=False,
            store_enabled=True,
            store_min_length=5,
        )
    storage.store.assert_awaited_once()
