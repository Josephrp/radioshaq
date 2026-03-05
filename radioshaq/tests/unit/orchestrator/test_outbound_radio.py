"""Unit tests for outbound radio handler."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from radioshaq.vendor.nanobot.bus.events import OutboundMessage


@pytest.mark.unit
@pytest.mark.asyncio
async def test_outbound_radio_handler_uses_chat_id_as_band() -> None:
    """Feed OutboundMessage(channel=radio_rx, chat_id=2m, content=OK); assert radio_tx.execute called with 2m freq."""
    call_args: list[dict] = []
    async def capture_execute(task: dict) -> dict:
        call_args.append(dict(task))
        return {"ok": True}
    agent = MagicMock()
    agent.execute = AsyncMock(side_effect=capture_execute)

    # Mock bus: first consume_outbound returns our message, second blocks forever
    first = OutboundMessage(
        channel="radio_rx",
        chat_id="2m",
        content="OK",
        metadata={"reply_band": "2m"},
    )
    second_wait = asyncio.Future()

    async def consume_outbound():
        if not hasattr(consume_outbound, "_first_done"):
            consume_outbound._first_done = True
            return first
        await second_wait
        return None

    bus = MagicMock()
    bus.consume_outbound = consume_outbound

    config = MagicMock()
    config.radio = MagicMock()
    config.radio.radio_reply_tx_enabled = True

    stop = asyncio.Event()

    async def stop_soon() -> None:
        await asyncio.sleep(0.2)
        stop.set()
        second_wait.cancel()

    from radioshaq.orchestrator.outbound_radio import run_outbound_radio_handler
    task = asyncio.create_task(run_outbound_radio_handler(bus, agent, config, stop_event=stop))
    asyncio.create_task(stop_soon())
    try:
        await asyncio.wait_for(task, timeout=2.0)
    except asyncio.CancelledError:
        pass
    except asyncio.TimeoutError:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert len(call_args) >= 1
    t = call_args[0]
    assert t.get("message") == "OK"
    assert t.get("use_tts") is True
    freq = t.get("frequency")
    assert freq is not None
    assert 144.0e6 <= freq <= 148.0e6  # 2m band


@pytest.mark.unit
@pytest.mark.asyncio
async def test_outbound_radio_handler_respects_radio_reply_use_tts_false() -> None:
    """When radio_reply_use_tts=False, outbound task sets use_tts=False explicitly."""
    call_args: list[dict] = []

    async def capture_execute(task: dict) -> dict:
        call_args.append(dict(task))
        return {"ok": True}

    agent = MagicMock()
    agent.execute = AsyncMock(side_effect=capture_execute)

    first = OutboundMessage(
        channel="radio_rx",
        chat_id="2m",
        content="OK",
        metadata={"reply_band": "2m"},
    )
    second_wait = asyncio.Future()

    async def consume_outbound():
        if not hasattr(consume_outbound, "_first_done"):
            consume_outbound._first_done = True
            return first
        await second_wait
        return None

    bus = MagicMock()
    bus.consume_outbound = consume_outbound

    config = MagicMock()
    config.radio = MagicMock()
    config.radio.radio_reply_tx_enabled = True
    config.radio.radio_reply_use_tts = False

    stop = asyncio.Event()

    async def stop_soon() -> None:
        await asyncio.sleep(0.2)
        stop.set()
        second_wait.cancel()

    from radioshaq.orchestrator.outbound_radio import run_outbound_radio_handler

    task = asyncio.create_task(run_outbound_radio_handler(bus, agent, config, stop_event=stop))
    asyncio.create_task(stop_soon())
    try:
        await asyncio.wait_for(task, timeout=2.0)
    except asyncio.CancelledError:
        pass
    except asyncio.TimeoutError:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert len(call_args) >= 1
    t = call_args[0]
    assert t.get("use_tts") is False
