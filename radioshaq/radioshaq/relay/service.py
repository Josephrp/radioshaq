"""Shared relay service: store source + relayed transcripts; optional inject and radio_tx.

Used by POST /messages/relay and by the relay_message_between_bands tool.
Default is store-only; recipient polls GET /transcripts. Inject and TX only when config enables.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from radioshaq.compliance_plugin import get_band_plan_source_for_config
from radioshaq.radio.bands import BAND_PLANS


async def relay_message_between_bands_service(
    message: str,
    source_band: str,
    target_band: str,
    *,
    source_frequency_hz: float | None = None,
    target_frequency_hz: float | None = None,
    source_callsign: str = "UNKNOWN",
    destination_callsign: str | None = None,
    session_id: str | None = None,
    deliver_at: str | None = None,
    storage: Any = None,
    injection_queue: Any = None,
    radio_tx_agent: Any = None,
    config: Any = None,
    source_audio_path: str | None = None,
    target_audio_path: str | None = None,
    store_only_relayed: bool = False,
) -> dict[str, Any]:
    """
    Relay a message from source band to target band: store two transcripts,
    optionally inject and/or TX on target band when deliver_at is not set.

    Returns dict with ok, source_transcript_id, relayed_transcript_id (when stored),
    source_band, target_band, session_id, deliver_at. When no storage, returns
    ok=True, relay="no_storage" and band/freq/callsign info only.
    """
    if config is not None:
        radio_cfg = getattr(config, "radio", config)
        band_plans = get_band_plan_source_for_config(
            getattr(radio_cfg, "restricted_bands_region", "FCC"),
            getattr(radio_cfg, "band_plan_region", None),
        )
    else:
        band_plans = BAND_PLANS
    if source_band not in band_plans or target_band not in band_plans:
        return {
            "ok": False,
            "error": "Unknown band; use e.g. 40m, 2m, 20m",
            "source_band": source_band,
            "target_band": target_band,
        }

    source_plan = band_plans[source_band]
    target_plan = band_plans[target_band]
    source_freq = source_frequency_hz or (
        source_plan.freq_start_hz + (source_plan.freq_end_hz - source_plan.freq_start_hz) / 2
    )
    target_freq = target_frequency_hz or (
        target_plan.freq_start_hz + (target_plan.freq_end_hz - target_plan.freq_start_hz) / 2
    )
    mode = (source_plan.modes or ["SSB"])[0]
    target_mode = (target_plan.modes or ["FM"])[0]

    if not storage or not getattr(storage, "_db", None):
        return {
            "ok": True,
            "relay": "no_storage",
            "message": "Relay accepted (no DB to store)",
            "source_band": source_band,
            "source_frequency_hz": source_freq,
            "target_band": target_band,
            "target_frequency_hz": target_freq,
            "source_callsign": source_callsign,
            "destination_callsign": destination_callsign,
            "session_id": session_id or "relay-no-storage",
            "deliver_at": deliver_at,
        }

    import uuid
    sid = session_id or f"relay-{uuid.uuid4().hex[:12]}"

    orig_id: int | None = None
    if not store_only_relayed:
        source_metadata = {"band": source_band, "relay_role": "source"}
        orig_id = await storage.store(
            session_id=sid,
            source_callsign=source_callsign,
            frequency_hz=source_freq,
            mode=mode,
            transcript_text=message,
            destination_callsign=destination_callsign,
            metadata=source_metadata,
            raw_audio_path=source_audio_path,
        )

    relay_metadata = {
        "band": target_band,
        "relay_role": "relayed",
        "relay_from_transcript_id": orig_id,
        "relay_from_band": source_band,
        "relay_from_frequency_hz": source_freq,
    }
    if deliver_at:
        relay_metadata["deliver_at"] = deliver_at
    relay_id = await storage.store(
        session_id=sid,
        source_callsign=source_callsign,
        frequency_hz=target_freq,
        mode=target_mode,
        transcript_text=message,
        destination_callsign=destination_callsign,
        metadata=relay_metadata,
        raw_audio_path=target_audio_path,
    )

    immediate = not deliver_at
    radio_cfg = getattr(config, "radio", None) if config else None
    if not radio_cfg:
        radio_cfg = config
    if immediate and radio_cfg:
        if getattr(radio_cfg, "relay_inject_target_band", False) and injection_queue:
            injection_queue.inject_message(
                text=message,
                band=target_band,
                frequency_hz=target_freq,
                mode=target_mode,
                source_callsign=source_callsign,
                destination_callsign=destination_callsign,
            )
        if getattr(radio_cfg, "relay_tx_target_band", False) and radio_tx_agent and hasattr(radio_tx_agent, "execute"):
            try:
                await radio_tx_agent.execute({
                    "transmission_type": "voice",
                    "frequency": target_freq,
                    "message": message,
                    "mode": target_mode,
                })
            except Exception as e:
                logger.warning("Relay radio_tx on target band failed: %s", e)

    return {
        "ok": True,
        "source_transcript_id": orig_id,
        "relayed_transcript_id": relay_id,
        "source_band": source_band,
        "source_frequency_hz": source_freq,
        "target_band": target_band,
        "target_frequency_hz": target_freq,
        "session_id": sid,
        "deliver_at": deliver_at,
    }
