"""Unit tests for outbound WhatsApp path (dispatcher -> WhatsApp agent)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from radioshaq.vendor.nanobot.bus.events import OutboundMessage


@pytest.mark.unit
@pytest.mark.asyncio
async def test_outbound_dispatcher_whatsapp_calls_agent_execute() -> None:
    """When dispatcher consumes channel=whatsapp, it calls whatsapp agent execute with send_message, to=chat_id, message=content."""
    call_args: list[dict] = []

    async def capture_execute(task: dict, upstream_callback=None) -> dict:
        call_args.append(dict(task))
        return {"success": True, "sid": "WA99"}

    wa_agent = MagicMock()
    wa_agent.execute = AsyncMock(side_effect=capture_execute)

    registry = MagicMock()
    registry.get_agent = MagicMock(side_effect=lambda name: wa_agent if name == "whatsapp" else None)

    msg = OutboundMessage(
        channel="whatsapp",
        chat_id="+15559876543",
        content="Hello via WhatsApp",
        metadata={},
    )
    second_wait = asyncio.Future()

    async def consume_outbound():
        if not getattr(consume_outbound, "_first_done", False):
            consume_outbound._first_done = True  # type: ignore[attr-defined]
            return msg
        await second_wait
        return None

    bus = MagicMock()
    bus.consume_outbound = consume_outbound
    config = MagicMock()
    stop = asyncio.Event()

    async def stop_soon() -> None:
        await asyncio.sleep(0.2)
        stop.set()
        second_wait.cancel()

    from radioshaq.orchestrator.outbound_dispatcher import run_outbound_handler
    task = asyncio.create_task(run_outbound_handler(bus, config, registry, stop_event=stop))
    asyncio.create_task(stop_soon())
    try:
        await asyncio.wait_for(task, timeout=2.0)
    except (asyncio.CancelledError, asyncio.TimeoutError):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert len(call_args) >= 1
    t = call_args[0]
    assert t.get("action") == "send_message"
    assert t.get("to") == "+15559876543"
    assert t.get("message") == "Hello via WhatsApp"
