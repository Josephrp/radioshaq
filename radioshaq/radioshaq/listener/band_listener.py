"""Multi-band listener: one concurrent task per band when hardware allows."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from loguru import logger

from radioshaq.compliance_plugin import get_band_plan_source_for_config
from radioshaq.config.schema import Config
from radioshaq.radio.bands import BAND_PLANS
from radioshaq.radio.injection import get_injection_queue


def _resolve_bands(config: Config) -> list[str]:
    """Bands to monitor: listen_bands or [default_band] if set."""
    radio = config.radio
    if radio.listen_bands:
        return list(radio.listen_bands)
    if radio.default_band:
        return [radio.default_band]
    return []


def _band_frequency_and_mode(band: str, band_plans: dict | None = None) -> tuple[float, str]:
    """Center frequency (Hz) and default mode for a band."""
    plans = band_plans if band_plans is not None else BAND_PLANS
    plan = plans.get(band)
    if not plan:
        return 0.0, "FM"
    freq = plan.freq_start_hz + (plan.freq_end_hz - plan.freq_start_hz) / 2
    mode = (plan.modes or ["FM"])[0]
    return freq, mode


async def _process_received_messages(
    band: str,
    messages: list[dict[str, Any]],
    storage: Any,
    message_bus: Any,
    inject: bool,
    publish_to_bus: bool,
    *,
    store_enabled: bool = True,
    store_min_length: int = 0,
) -> None:
    """Store, optionally inject, and optionally publish to bus for each message."""
    for msg in messages:
        text = msg.get("message", "") or ""
        if not text:
            continue
        source = (msg.get("source_callsign") or "UNKNOWN").strip().upper()
        freq = msg.get("frequency") or 0.0
        mode = msg.get("mode") or "FM"
        session_id = f"listener-{band}-{uuid.uuid4().hex[:8]}"
        metadata = {"band": band, "source": "band_listener"}

        if storage and store_enabled:
            if store_min_length > 0 and len(text.strip()) < store_min_length:
                pass  # skip store: too short
            else:
                try:
                    from radioshaq.api.routes.metrics import increment_listener_messages
                    increment_listener_messages(band)
                    await storage.store(
                        session_id=session_id,
                        source_callsign=source,
                        frequency_hz=freq,
                        mode=mode,
                        transcript_text=text,
                        destination_callsign=None,
                        metadata=metadata,
                    )
                except Exception as e:
                    logger.warning("Band listener store failed: {}", e)
        if inject:
            try:
                queue = get_injection_queue()
                queue.inject_message(
                    text=text,
                    band=band,
                    frequency_hz=freq,
                    mode=mode,
                    source_callsign=source,
                    destination_callsign=None,
                )
            except Exception as e:
                logger.warning("Band listener inject failed: {}", e)
        if publish_to_bus and message_bus:
            try:
                from radioshaq.orchestrator.radio_ingestion import radio_received_to_inbound
                inbound = radio_received_to_inbound(
                    text=text,
                    band=band,
                    frequency_hz=freq,
                    source_callsign=source,
                    destination_callsign=None,
                    mode=mode,
                )
                ok = await message_bus.publish_inbound(inbound)
                if not ok:
                    logger.debug("Bus full, dropped radio_rx message for {}", band)
            except Exception as e:
                logger.warning("Band listener publish_inbound failed: {}", e)


async def _monitor_band_loop(
    band: str,
    radio_rx_agent: Any,
    storage: Any,
    message_bus: Any,
    cycle_seconds: float,
    inject: bool,
    publish_to_bus: bool,
    stop_event: asyncio.Event,
    *,
    band_plans: dict | None = None,
    store_enabled: bool = True,
    store_min_length: int = 0,
) -> None:
    """Single-band loop: monitor for cycle_seconds, process messages, repeat until stop."""
    freq, mode = _band_frequency_and_mode(band, band_plans)
    if freq <= 0:
        logger.warning("Band {} has no plan, skipping", band)
        return
    while not stop_event.is_set():
        try:
            result = await radio_rx_agent.monitor_frequency(
                freq,
                int(cycle_seconds),
                mode=mode,
                upstream_callback=None,
                band=band,
            )
            messages = result.get("messages") or []
            if messages:
                await _process_received_messages(
                    band, messages, storage, message_bus, inject, publish_to_bus,
                    store_enabled=store_enabled,
                    store_min_length=store_min_length,
                )
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.exception("Band listener {} error: {}", band, e)
        await asyncio.sleep(0.2)


async def run_band_listener(
    config: Config,
    storage: Any,
    message_bus: Any,
    radio_rx_agent: Any,
    *,
    stop_event: asyncio.Event,
    inject_into_queue: bool = True,
    publish_to_bus: bool = True,
) -> None:
    """
    Run multi-band listener: one concurrent task per band when listener_concurrent_bands
    is True, else round-robin over bands with cycle_seconds per band.

    On each received message: store with metadata.band, optionally inject into RX queue,
    and optionally publish InboundMessage(channel=radio_rx, chat_id=band) to message_bus.
    """
    bands = _resolve_bands(config)
    if not bands:
        logger.debug("Band listener: no listen_bands or default_band, exiting")
        return
    radio = config.radio
    if not getattr(radio, "listener_enabled", False):
        logger.debug("Band listener: listener_enabled=False, exiting")
        return
    if not radio_rx_agent:
        logger.warning("Band listener: no radio_rx agent, exiting")
        return

    cycle_seconds = getattr(radio, "listener_cycle_seconds", 30.0) or 30.0
    concurrent = getattr(radio, "listener_concurrent_bands", True)
    store_enabled = storage is not None and getattr(radio, "band_listener_store", True)
    store_min_length = getattr(radio, "band_listener_store_min_length", 0) or 0
    band_plans = get_band_plan_source_for_config(
        radio.restricted_bands_region,
        getattr(radio, "band_plan_region", None),
    )

    if concurrent:
        tasks = [
            asyncio.create_task(
                _monitor_band_loop(
                    band,
                    radio_rx_agent,
                    storage,
                    message_bus,
                    cycle_seconds,
                    inject_into_queue,
                    publish_to_bus,
                    stop_event,
                    band_plans=band_plans,
                    store_enabled=store_enabled,
                    store_min_length=store_min_length,
                )
            )
            for band in bands
        ]
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    else:
        # Single receiver: round-robin
        while not stop_event.is_set():
            for band in bands:
                if stop_event.is_set():
                    break
                await _monitor_band_loop(
                    band,
                    radio_rx_agent,
                    storage,
                    message_bus,
                    cycle_seconds,
                    inject_into_queue,
                    publish_to_bus,
                    stop_event,
                    band_plans=band_plans,
                    store_enabled=store_enabled,
                    store_min_length=store_min_length,
                )
