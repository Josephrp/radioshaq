"""Relay delivery worker: process pending deliver_at transcripts (inject and optionally TX on target band)."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from radioshaq.radio.bands import BAND_PLANS
from radioshaq.radio.injection import get_injection_queue


async def run_relay_delivery_worker(
    db: Any,
    config: Any,
    *,
    stop_event: asyncio.Event,
    interval_seconds: float = 60.0,
    radio_tx_agent: Any = None,
) -> None:
    """
    Periodically query transcripts with deliver_at <= now and delivery_status != delivered;
    for each: inject to target band, optionally call radio_tx, then mark delivered.

    db must have search_pending_relay_deliveries() and mark_transcript_delivery_done(id).
    """
    if not db or not hasattr(db, "search_pending_relay_deliveries"):
        logger.debug("Relay delivery worker: no db or search_pending_relay_deliveries, exiting")
        return
    radio_cfg = getattr(config, "radio", None)
    relay_tx = getattr(radio_cfg, "relay_tx_target_band", False) if radio_cfg else False

    while not stop_event.is_set():
        try:
            pending = await db.search_pending_relay_deliveries(limit=50)
            for t in pending:
                tid = t.get("id")
                extra = t.get("extra_data") or {}
                band = extra.get("band") or extra.get("relay_from_band") or "unknown"
                text = t.get("transcript_text") or ""
                source = t.get("source_callsign") or "UNKNOWN"
                dest = t.get("destination_callsign")
                mode = t.get("mode") or "FM"
                freq = t.get("frequency_hz") or 0.0
                if not freq and band:
                    plan = BAND_PLANS.get(band)
                    if plan:
                        freq = plan.freq_start_hz + (plan.freq_end_hz - plan.freq_start_hz) / 2

                queue = get_injection_queue()
                queue.inject_message(
                    text=text,
                    band=band,
                    frequency_hz=freq,
                    mode=mode,
                    source_callsign=source,
                    destination_callsign=dest,
                )
                if relay_tx and radio_tx_agent and hasattr(radio_tx_agent, "execute"):
                    try:
                        await radio_tx_agent.execute({
                            "transmission_type": "voice",
                            "frequency": freq,
                            "message": text,
                            "mode": mode,
                        })
                    except Exception as e:
                        logger.warning("Relay delivery radio_tx failed for transcript %s: %s", tid, e)
                ok = await db.mark_transcript_delivery_done(tid)
                if ok:
                    try:
                        from radioshaq.api.routes.metrics import increment_relay_deliveries
                        increment_relay_deliveries()
                    except Exception:
                        pass
                else:
                    logger.warning("Could not mark transcript %s delivered", tid)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.exception("Relay delivery worker error: %s", e)
        await asyncio.sleep(interval_seconds)
