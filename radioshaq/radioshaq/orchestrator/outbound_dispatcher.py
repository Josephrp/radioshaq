"""Single outbound consumer: dispatch by channel to radio_rx, sms, or whatsapp (Option A)."""

from __future__ import annotations

import asyncio
import dataclasses
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from radioshaq.orchestrator.outbound_radio import handle_one_outbound_radio

MAX_OUTBOUND_RETRIES = 3


async def _maybe_reenqueue_outbound(bus: Any, msg: Any, channel_label: str) -> None:
    """Re-enqueue msg with incremented _retries, or log as dead-letter if over limit."""
    meta = dict(getattr(msg, "metadata", None) or {})
    retries = int(meta.get("_retries", 0))
    if retries >= MAX_OUTBOUND_RETRIES:
        logger.error(
            "Outbound {} to {} failed {} times, dropping to dead-letter",
            channel_label,
            msg.chat_id,
            MAX_OUTBOUND_RETRIES,
        )
        return
    meta["_retries"] = retries + 1
    try:
        if dataclasses.is_dataclass(msg):
            await bus.publish_outbound(dataclasses.replace(msg, metadata=meta))
        else:
            from radioshaq.vendor.nanobot.bus.events import OutboundMessage
            await bus.publish_outbound(OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=msg.content or "",
                reply_to=getattr(msg, "reply_to", None),
                media=list(getattr(msg, "media", [])),
                metadata=meta,
            ))
    except Exception:
        logger.error(
            "Failed to re-enqueue outbound {} message to {}",
            channel_label,
            msg.chat_id,
        )


async def _mark_emergency_sent(db: Any, msg: Any) -> None:
    """Stamp sent_at only after the downstream channel agent reports success."""
    if not db or not hasattr(db, "update_coordination_event"):
        return
    meta = dict(getattr(msg, "metadata", None) or {})
    event_id = meta.get("emergency_event_id")
    if not event_id:
        return
    try:
        await db.update_coordination_event(
            int(event_id),
            extra_data={"sent_at": datetime.now(timezone.utc).isoformat()},
        )
    except Exception as e:
        logger.warning(
            "Could not update sent_at for emergency event {}: {}",
            event_id,
            e,
        )


async def run_outbound_handler(
    bus: Any,
    config: Any,
    agent_registry: Any,
    db: Any = None,
    *,
    stop_event: asyncio.Event,
) -> None:
    """
    Consume outbound messages and dispatch by channel:
    - radio_rx -> handle_one_outbound_radio (radio_tx agent)
    - sms -> SMS agent execute(send)
    - whatsapp -> WhatsApp agent execute(send_message)
    Other channels are logged and skipped.
    """
    if not bus or not hasattr(bus, "consume_outbound"):
        logger.debug("Outbound handler: no bus or consume_outbound, exiting")
        return

    consume_timeout = 5.0
    while not stop_event.is_set():
        try:
            msg = await asyncio.wait_for(bus.consume_outbound(), timeout=consume_timeout)
            if msg.channel == "radio_rx":
                radio_tx = agent_registry.get_agent("radio_tx") if agent_registry else None
                try:
                    handled = await handle_one_outbound_radio(msg, radio_tx, config)
                    if handled is False:
                        await _maybe_reenqueue_outbound(bus, msg, "radio_rx")
                except Exception as e:
                    logger.warning("Outbound radio_rx failed: {}", e)
                    await _maybe_reenqueue_outbound(bus, msg, "radio_rx")
            elif msg.channel == "sms":
                sms_agent = agent_registry.get_agent("sms") if agent_registry else None
                if sms_agent and hasattr(sms_agent, "execute"):
                    try:
                        result = await sms_agent.execute(
                            {"action": "send", "to": msg.chat_id, "message": msg.content or ""},
                            upstream_callback=None,
                        )
                        if result.get("success") is False:
                            logger.warning(
                                "Outbound sms execute returned unsuccessful result for {}",
                                msg.chat_id,
                            )
                            await _maybe_reenqueue_outbound(bus, msg, "sms")
                        else:
                            await _mark_emergency_sent(db, msg)
                    except Exception as e:
                        logger.warning("Outbound sms execute failed: {}", e)
                        await _maybe_reenqueue_outbound(bus, msg, "sms")
                else:
                    logger.debug("Outbound sms: no sms agent, re-enqueuing")
                    await _maybe_reenqueue_outbound(bus, msg, "sms")
            elif msg.channel == "whatsapp":
                wa_agent = agent_registry.get_agent("whatsapp") if agent_registry else None
                if wa_agent and hasattr(wa_agent, "execute"):
                    try:
                        result = await wa_agent.execute(
                            {
                                "action": "send_message",
                                "to": msg.chat_id,
                                "message": msg.content or "",
                            },
                            upstream_callback=None,
                        )
                        if result.get("success") is False:
                            logger.warning(
                                "Outbound whatsapp execute returned unsuccessful result for {}",
                                msg.chat_id,
                            )
                            await _maybe_reenqueue_outbound(bus, msg, "whatsapp")
                        else:
                            await _mark_emergency_sent(db, msg)
                    except Exception as e:
                        logger.warning("Outbound whatsapp execute failed: {}", e)
                        await _maybe_reenqueue_outbound(bus, msg, "whatsapp")
                else:
                    logger.debug("Outbound whatsapp: no whatsapp agent, re-enqueuing")
                    await _maybe_reenqueue_outbound(bus, msg, "whatsapp")
            else:
                logger.debug("Outbound unsupported channel: {}", msg.channel)
        except asyncio.CancelledError:
            logger.debug("Outbound handler cancelled")
            break
        except asyncio.TimeoutError:
            continue
        except Exception as e:
            logger.exception("Outbound handler error: {}", e)
