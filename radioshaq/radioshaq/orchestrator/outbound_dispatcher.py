"""Single outbound consumer: dispatch by channel to radio_rx, sms, or whatsapp (Option A)."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from radioshaq.orchestrator.outbound_radio import handle_one_outbound_radio


async def run_outbound_handler(
    bus: Any,
    config: Any,
    agent_registry: Any,
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
                await handle_one_outbound_radio(msg, radio_tx, config)
            elif msg.channel == "sms":
                sms_agent = agent_registry.get_agent("sms") if agent_registry else None
                if sms_agent and hasattr(sms_agent, "execute"):
                    try:
                        await sms_agent.execute(
                            {"action": "send", "to": msg.chat_id, "message": msg.content or ""},
                            upstream_callback=None,
                        )
                    except Exception as e:
                        logger.warning("Outbound sms execute failed, re-enqueuing: %s", e)
                        try:
                            await bus.publish_outbound(msg)
                        except Exception:
                            logger.error("Failed to re-enqueue outbound sms message to %s", msg.chat_id)
                else:
                    logger.debug("Outbound sms: no sms agent, re-enqueuing")
                    try:
                        await bus.publish_outbound(msg)
                    except Exception:
                        logger.error("Failed to re-enqueue outbound sms message to %s", msg.chat_id)
            elif msg.channel == "whatsapp":
                wa_agent = agent_registry.get_agent("whatsapp") if agent_registry else None
                if wa_agent and hasattr(wa_agent, "execute"):
                    try:
                        await wa_agent.execute(
                            {
                                "action": "send_message",
                                "to": msg.chat_id,
                                "message": msg.content or "",
                            },
                            upstream_callback=None,
                        )
                    except Exception as e:
                        logger.warning("Outbound whatsapp execute failed, re-enqueuing: %s", e)
                        try:
                            await bus.publish_outbound(msg)
                        except Exception:
                            logger.error("Failed to re-enqueue outbound whatsapp message to %s", msg.chat_id)
                else:
                    logger.debug("Outbound whatsapp: no whatsapp agent, re-enqueuing")
                    try:
                        await bus.publish_outbound(msg)
                    except Exception:
                        logger.error("Failed to re-enqueue outbound whatsapp message to %s", msg.chat_id)
            else:
                logger.debug("Outbound unsupported channel: %s", msg.channel)
        except asyncio.CancelledError:
            logger.debug("Outbound handler cancelled")
            break
        except asyncio.TimeoutError:
            continue
        except Exception as e:
            logger.exception("Outbound handler error: %s", e)
