"""Outbound handler: consume OutboundMessage for channel=radio_rx and transmit on correct band via radio_tx."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from radioshaq.radio.bands import BAND_PLANS


async def run_outbound_radio_handler(
    bus: Any,
    radio_tx_agent: Any,
    config: Any,
    *,
    stop_event: asyncio.Event,
) -> None:
    """
    Consume outbound messages; for channel=radio_rx, transmit reply on the band (chat_id/reply_band)
    using radio_tx agent. When radio_reply_tx_enabled is False, consume but do not call radio_tx.
    """
    if not bus or not hasattr(bus, "consume_outbound"):
        logger.debug("Outbound radio handler: no bus or consume_outbound, exiting")
        return
    radio_cfg = getattr(config, "radio", None)
    tx_enabled = getattr(radio_cfg, "radio_reply_tx_enabled", True) if radio_cfg else True
    reply_use_tts = getattr(radio_cfg, "radio_reply_use_tts", True) if radio_cfg else True

    while not stop_event.is_set():
        try:
            msg = await bus.consume_outbound()
            if msg.channel != "radio_rx":
                continue
            if not tx_enabled:
                continue
            if not radio_tx_agent or not hasattr(radio_tx_agent, "execute"):
                logger.debug("Outbound radio: no radio_tx agent, skipping TX")
                continue
            band = msg.chat_id or msg.metadata.get("reply_band") or ""
            freq = msg.metadata.get("frequency_hz")
            mode = msg.metadata.get("mode")
            if not band and freq is None:
                logger.warning("Outbound radio_rx: no band or frequency_hz, skipping")
                continue
            plan = BAND_PLANS.get(band) if band else None
            if plan:
                if freq is None or freq <= 0:
                    freq = plan.freq_start_hz + (plan.freq_end_hz - plan.freq_start_hz) / 2
                if not mode:
                    mode = (plan.modes or ["FM"])[0]
            else:
                mode = mode or "FM"
            if freq is None or freq <= 0:
                logger.warning("Outbound radio_rx: could not resolve frequency for band %s", band)
                continue
            try:
                await radio_tx_agent.execute({
                    "transmission_type": "voice",
                    "frequency": freq,
                    "message": msg.content or "",
                    "mode": mode,
                    "use_tts": bool(reply_use_tts),
                })
            except Exception as e:
                logger.warning("Outbound radio_tx execute failed: %s", e)
        except asyncio.CancelledError:
            logger.debug("Outbound radio handler cancelled")
            break
        except asyncio.TimeoutError:
            continue
        except Exception as e:
            logger.exception("Outbound radio handler error: %s", e)
