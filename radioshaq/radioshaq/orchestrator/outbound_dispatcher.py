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

    while not stop_event.is_set():
        try:
            msg = await bus.consume_outbound()
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
                        logger.warning("Outbound sms execute failed: %s", e)
                else:
                    logger.debug("Outbound sms: no sms agent, skipping")
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
                        logger.warning("Outbound whatsapp execute failed: %s", e)
                else:
                    logger.debug("Outbound whatsapp: no whatsapp agent, skipping")
            else:
                logger.debug("Outbound unsupported channel: %s", msg.channel)
        except asyncio.CancelledError:
            logger.debug("Outbound handler cancelled")
            break
        except asyncio.TimeoutError:
            continue
        except Exception as e:
            logger.exception("Outbound handler error: %s", e)
