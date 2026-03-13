"""Relay delivery worker: process pending deliver_at transcripts (radio inject/TX or SMS/WhatsApp via bus)."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from radioshaq.compliance_plugin import get_band_plan_source_for_config
from radioshaq.radio.bands import BAND_PLANS
from radioshaq.radio.injection import get_injection_queue


def _is_consent_valid_for_region(region: str | None, prefs: dict[str, Any]) -> bool:
    """True if contact preferences have a valid consent record (API enforces consent for explicit regions before setting notify_consent_at)."""
    return bool(prefs.get("notify_consent_at"))


async def run_relay_delivery_worker(
    db: Any,
    config: Any,
    *,
    stop_event: asyncio.Event,
    interval_seconds: float = 60.0,
    radio_tx_agent: Any = None,
    message_bus: Any = None,
) -> None:
    """
    Periodically query transcripts with deliver_at <= now and delivery_status != delivered.
    - If extra_data has delivery_channel sms or whatsapp: publish OutboundMessage to message_bus
      (outbound dispatcher will send via SMS/WhatsApp).
    - Else: inject to target band and optionally call radio_tx (existing behavior).

    db must have search_pending_relay_deliveries() and mark_transcript_delivery_done(id).
    """
    if not db or not hasattr(db, "search_pending_relay_deliveries"):
        logger.debug("Relay delivery worker: no db or search_pending_relay_deliveries, exiting")
        return
    radio_cfg = getattr(config, "radio", None)
    relay_tx = getattr(radio_cfg, "relay_tx_target_band", False) if radio_cfg else False
    band_plans = (
        get_band_plan_source_for_config(
            getattr(radio_cfg, "restricted_bands_region", "FCC"),
            getattr(radio_cfg, "band_plan_region", None),
        )
        if radio_cfg
        else BAND_PLANS
    )

    while not stop_event.is_set():
        try:
            pending = await db.search_pending_relay_deliveries(limit=50)
            for t in pending:
                tid = t.get("id")
                extra = t.get("extra_data") or {}
                text = t.get("transcript_text") or ""
                source = t.get("source_callsign") or "UNKNOWN"
                dest = t.get("destination_callsign")

                delivery_channel = extra.get("delivery_channel")
                destination_phone = extra.get("destination_phone")

                mark_delivered = False
                if delivery_channel in ("sms", "whatsapp"):
                    if destination_phone and message_bus and hasattr(message_bus, "publish_outbound"):
                        from radioshaq.vendor.nanobot.bus.events import OutboundMessage
                        ok_pub = await message_bus.publish_outbound(
                            OutboundMessage(
                                channel=delivery_channel,
                                chat_id=destination_phone,
                                content=text,
                                reply_to=None,
                                media=[],
                                metadata={"relay_transcript_id": tid, "source_callsign": source},
                            )
                        )
                        if not ok_pub:
                            logger.warning(
                                "Relay delivery: outbound queue full for transcript {} ({})",
                                tid,
                                delivery_channel,
                            )
                        else:
                            mark_delivered = True
                        else:
                            logger.warning(
                                "Relay delivery: cannot deliver transcript {} via {} (bus unavailable or no phone)",
                                tid,
                                delivery_channel,
                            )
                        # Do NOT fall through to radio injection; leave undelivered for retry
                else:
                    band = extra.get("band") or extra.get("relay_from_band") or "unknown"
                    mode = t.get("mode") or "FM"
                    freq = t.get("frequency_hz") or 0.0
                    if not freq and band and band in band_plans:
                        plan = band_plans.get(band)
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
                    if relay_tx and radio_tx_agent and hasattr(radio_tx_agent, "execute") and freq > 0:
                        try:
                            await radio_tx_agent.execute({
                                "transmission_type": "voice",
                                "frequency": freq,
                                "message": text,
                                "mode": mode,
                            })
                        except Exception as e:
                            logger.warning("Relay delivery radio_tx failed for transcript {}: {}", tid, e)
                    mark_delivered = True

                if mark_delivered:
                    ok = await db.mark_transcript_delivery_done(tid)
                    if ok:
                        try:
                            from radioshaq.api.routes.metrics import increment_relay_deliveries
                            increment_relay_deliveries()
                        except Exception:
                            pass
                        # Notify-on-relay (§8.3): only after confirmed delivery, for radio only; if destination has notify preferences, send short SMS/WhatsApp
                        if (
                            delivery_channel not in ("sms", "whatsapp")
                            and dest
                            and message_bus
                            and hasattr(message_bus, "publish_outbound")
                            and hasattr(db, "get_contact_preferences")
                        ):
                            try:
                                prefs = await db.get_contact_preferences(dest)
                                if not prefs:
                                    continue
                                if not prefs.get("notify_on_relay"):
                                    continue
                                region = getattr(radio_cfg, "restricted_bands_region", None) if radio_cfg else None
                                if not _is_consent_valid_for_region(region, prefs):
                                    continue
                                sms_phone = prefs.get("notify_sms_phone") if not prefs.get("notify_opt_out_at_sms") else None
                                whatsapp_phone = prefs.get("notify_whatsapp_phone") if not prefs.get("notify_opt_out_at_whatsapp") else None
                                if not sms_phone and not whatsapp_phone:
                                    continue
                                band = extra.get("band") or extra.get("relay_from_band") or "radio"
                                snippet = (text or "")[:80].replace("\n", " ")
                                if len(text or "") > 80:
                                    snippet += "..."
                                notify_text = f"You have a new message on {band} from {source}: {snippet}"
                                from radioshaq.vendor.nanobot.bus.events import OutboundMessage
                                for ch, phone in (("sms", sms_phone), ("whatsapp", whatsapp_phone)):
                                    if not phone:
                                        continue
                                    ok_pub = await message_bus.publish_outbound(
                                        OutboundMessage(
                                            channel=ch,
                                            chat_id=phone,
                                            content=notify_text,
                                            reply_to=None,
                                            media=[],
                                            metadata={
                                                "notify_on_relay": True,
                                                "destination_callsign": dest,
                                                "relay_transcript_id": tid,
                                            },
                                        )
                                    )
                                    if ok_pub:
                                        logger.info(
                                            "Notify-on-relay sent to {} for callsign {} (transcript {})",
                                            ch,
                                            dest,
                                            tid,
                                        )
                                    else:
                                        logger.warning("Notify-on-relay queue full for {} {}", ch, dest)
                            except Exception as e:
                                logger.warning("Notify-on-relay failed for dest {}: {}", dest, e)
                    else:
                        logger.warning("Could not mark transcript {} delivered", tid)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.exception("Relay delivery worker error: {}", e)
        await asyncio.sleep(interval_seconds)
