"""Voice listener: run radio_rx_audio monitor in a loop so voice (rig audio to ASR) feeds the message queue.

When audio_input_enabled and voice_listener_enabled (or audio_monitoring_enabled), this task
runs continuously and publishes transcribed segments to the MessageBus (default capture path).
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from radioshaq.config.schema import Config
from radioshaq.radio.bands import BAND_PLANS


def _resolve_voice_band(config: Config) -> str | None:
    """Band to monitor for voice: default_band or first of listen_bands."""
    radio = getattr(config, "radio", None)
    if not radio:
        return None
    if getattr(radio, "default_band", None):
        return radio.default_band
    bands = getattr(radio, "listen_bands", None) or []
    if bands:
        return bands[0]
    return None


def _voice_frequency_and_mode(band: str) -> tuple[float, str]:
    """Center frequency (Hz) and default mode for a band."""
    plan = BAND_PLANS.get(band)
    if not plan:
        return 0.0, "FM"
    freq = plan.freq_start_hz + (plan.freq_end_hz - plan.freq_start_hz) / 2
    mode = (plan.modes or ["FM"])[0]
    return freq, mode


async def run_voice_listener(
    config: Config,
    message_bus: Any,
    radio_rx_audio_agent: Any,
    *,
    stop_event: asyncio.Event,
    cycle_seconds: float = 3600.0,
) -> None:
    """
    Run voice listener: call radio_rx_audio execute(monitor) in a loop so that
    rig audio is captured, transcribed, and published to the message queue.

    Resolves frequency and mode from config.radio.default_band or first of
    config.radio.listen_bands. On each iteration runs monitor for cycle_seconds,
    then sleeps briefly and repeats until stop_event is set.
    """
    band = _resolve_voice_band(config)
    if not band:
        logger.debug("Voice listener: no default_band or listen_bands, exiting")
        return
    freq, mode = _voice_frequency_and_mode(band)
    if freq <= 0:
        logger.warning("Voice listener: band %s has no plan, skipping", band)
        return
    if not radio_rx_audio_agent:
        logger.warning("Voice listener: no radio_rx_audio agent, exiting")
        return

    logger.info("Voice listener started for band %s (%.0f Hz %s)", band, freq, mode)
    while not stop_event.is_set():
        try:
            await radio_rx_audio_agent.execute(
                {
                    "action": "monitor",
                    "frequency": freq,
                    "duration_seconds": int(cycle_seconds),
                    "mode": mode,
                },
                upstream_callback=None,
            )
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.exception("Voice listener error: %s", e)
        if not stop_event.is_set():
            await asyncio.sleep(0.5)
    logger.debug("Voice listener stopped")
