"""Bridge: MessageBus (nanobot) InboundMessage → REACT orchestrator → OutboundMessage."""

from __future__ import annotations

from typing import Any

from loguru import logger

from radioshaq.orchestrator.react_loop import REACTOrchestrator, REACTResult
from radioshaq.vendor.nanobot.bus.events import InboundMessage, OutboundMessage
from radioshaq.vendor.nanobot.bus.queue import MessageBus


def _resolve_callsign(message: InboundMessage) -> str | None:
    """Resolve and normalize callsign from message (sender_id)."""
    raw = getattr(message, "sender_id", None) or ""
    if not raw or not str(raw).strip():
        return None
    return str(raw).strip().upper()


async def process_inbound_message(
    bus: MessageBus,
    orchestrator: REACTOrchestrator,
    message: InboundMessage,
    callsign_repository: Any = None,
) -> REACTResult:
    """
    Process one inbound message: run REACT, then publish outbound reply to same channel/chat.
    For radio_rx, pass inbound_metadata and preserve reply_band in outbound for TX on correct band.
    When callsign_repository is set and message is radio_rx, update last_band for the sender callsign.
    """
    callsign = _resolve_callsign(message)
    inbound_metadata = dict(message.metadata) if message.channel == "radio_rx" else None
    result = await orchestrator.process_request(
        message.content,
        callsign=callsign,
        inbound_metadata=inbound_metadata,
    )
    meta = {"task_id": result.state.task_id, "success": result.success}
    if message.channel == "radio_rx":
        meta["reply_band"] = message.chat_id
        meta["frequency_hz"] = message.metadata.get("frequency_hz")
        band = message.metadata.get("band") or message.chat_id
        if band and callsign and callsign_repository and hasattr(callsign_repository, "update_last_band"):
            try:
                await callsign_repository.update_last_band(callsign, band)
            except Exception as e:
                logger.debug("update_last_band failed: %s", e)
    out = OutboundMessage(
        channel=message.channel,
        chat_id=message.chat_id,
        content=result.message,
        reply_to=None,
        media=[],
        metadata=meta,
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
    callsign_repository: Any = None,
) -> None:
    """
    Consume inbound messages in a loop and process each with the orchestrator.
    If stop_event is provided (e.g. asyncio.Event), exit when it is set.
    callsign_repository: optional; when set, update_last_band for radio_rx senders.
    """
    import asyncio
    stop = stop_event
    while True:
        try:
            if stop is not None and stop.is_set():
                break
            msg = await bus.consume_inbound()
            await process_inbound_message(bus, orchestrator, msg, callsign_repository=callsign_repository)
        except asyncio.CancelledError:
            logger.debug("Inbound consumer cancelled")
            break
        except asyncio.TimeoutError:
            # Bus uses inbound_timeout; wake periodically to check stop_event
            continue
        except Exception as e:
            logger.exception("Inbound consumer error: %s", e)
