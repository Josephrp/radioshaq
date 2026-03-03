"""Bridge: MessageBus (nanobot) InboundMessage → REACT orchestrator → OutboundMessage."""

from __future__ import annotations

from typing import Any

from loguru import logger

from radioshaq.orchestrator.react_loop import REACTOrchestrator, REACTResult
from radioshaq.vendor.nanobot.bus.events import InboundMessage, OutboundMessage
from radioshaq.vendor.nanobot.bus.queue import MessageBus


async def process_inbound_message(
    bus: MessageBus,
    orchestrator: REACTOrchestrator,
    message: InboundMessage,
) -> REACTResult:
    """
    Process one inbound message: run REACT, then publish outbound reply to same channel/chat.
    """
    result = await orchestrator.process_request(message.content)
    out = OutboundMessage(
        channel=message.channel,
        chat_id=message.chat_id,
        content=result.message,
        reply_to=None,
        media=[],
        metadata={"task_id": result.state.task_id, "success": result.success},
    )
    ok = await bus.publish_outbound(out)
    if not ok:
        logger.warning("Outbound queue full, could not send reply to %s:%s", message.channel, message.chat_id)
    return result


async def run_inbound_consumer(
    bus: MessageBus,
    orchestrator: REACTOrchestrator,
    *,
    stop_event: Any = None,
) -> None:
    """
    Consume inbound messages in a loop and process each with the orchestrator.
    If stop_event is provided (e.g. asyncio.Event), exit when it is set.
    """
    import asyncio
    stop = stop_event
    while True:
        try:
            if stop is not None and stop.is_set():
                break
            msg = await bus.consume_inbound()
            await process_inbound_message(bus, orchestrator, msg)
        except asyncio.CancelledError:
            logger.debug("Inbound consumer cancelled")
            break
        except asyncio.TimeoutError:
            # Bus uses inbound_timeout; wake periodically to check stop_event
            continue
        except Exception as e:
            logger.exception("Inbound consumer error: %s", e)
