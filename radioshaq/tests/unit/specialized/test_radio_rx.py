"""Unit tests for RadioReceptionAgent (radio_rx) band-aware injection."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from radioshaq.radio.injection import InMemoryInjectionQueue, InjectedMessage
from radioshaq.specialized.radio_rx import RadioReceptionAgent


@pytest.fixture
def injection_queue() -> InMemoryInjectionQueue:
    """Fresh injection queue for tests (no rig, no digital_modes)."""
    return InMemoryInjectionQueue(maxsize=10)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_band_filter_rejects_wrong_band_reputs_message(
    injection_queue: InMemoryInjectionQueue,
) -> None:
    """With band=40m, an injected message with band=2m is re-put and not received."""
    injection_queue.inject_message("Hello 2m", band="2m", mode="FM")
    agent = RadioReceptionAgent(rig_manager=None, digital_modes=None)
    with patch("radioshaq.radio.injection.get_injection_queue", return_value=injection_queue):
        result = await agent.monitor_frequency(
            7.15e6,  # 40m
            1,
            mode="SSB",
            band="40m",
        )
    assert result["messages_received"] == 0
    assert len(result["messages"]) == 0
    # Message should still be in queue (re-put)
    assert injection_queue.qsize() == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_band_filter_accepts_matching_band(
    injection_queue: InMemoryInjectionQueue,
) -> None:
    """With band=2m, an injected message with band=2m is received."""
    injection_queue.inject_message("Hello 2m", band="2m", mode="FM")
    agent = RadioReceptionAgent(rig_manager=None, digital_modes=None)
    with patch("radioshaq.radio.injection.get_injection_queue", return_value=injection_queue):
        result = await agent.monitor_frequency(
            145.0e6,  # 2m
            1,
            mode="FM",
            band="2m",
        )
    assert result["messages_received"] == 1
    assert len(result["messages"]) == 1
    assert result["messages"][0]["message"] == "Hello 2m"
    assert result["messages"][0]["band"] == "2m"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_band_filter_accepts_unset_band(
    injection_queue: InMemoryInjectionQueue,
) -> None:
    """When injected message has band=None, it is accepted by any monitor (no filter)."""
    injection_queue.inject_message("No band", band=None, mode="FM")
    agent = RadioReceptionAgent(rig_manager=None, digital_modes=None)
    with patch("radioshaq.radio.injection.get_injection_queue", return_value=injection_queue):
        result = await agent.monitor_frequency(
            7.15e6,
            1,
            mode="SSB",
            band="40m",
        )
    assert result["messages_received"] == 1
    assert result["messages"][0]["message"] == "No band"


@pytest.mark.unit
def test_put_back_nowait_returns_true_when_not_full() -> None:
    """put_back_nowait returns True when queue has space."""
    q = InMemoryInjectionQueue(maxsize=2)
    msg = InjectedMessage(text="x", band="2m")
    q.inject_message("first")
    assert q.receive_injected_nowait() is not None
    assert q.put_back_nowait(msg) is True
    assert q.qsize() == 1
