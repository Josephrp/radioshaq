"""Radio transmission specialized agent."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from radioshaq.compliance_plugin import get_band_plan_source_for_config
from radioshaq.middleware.upstream import UpstreamEvent
from radioshaq.radio.compliance import is_tx_allowed, is_tx_spectrum_allowed, log_tx
from radioshaq.radio.modes import normalize_mode
from radioshaq.radio.analog_mod import am_modulate, cw_tone_iq, ssb_modulate
from radioshaq.radio.fm import nfm_modulate
from radioshaq.specialized.base import SpecializedAgent


class RadioTransmissionAgent(SpecializedAgent):
    """
    Specialized agent for ham radio transmission.
    Supports voice (with optional audio file or TTS), digital modes, and packet radio.
    """

    name = "radio_tx"
    description = "Transmits messages via ham radio on specified bands and modes"
    capabilities = [
        "voice_transmission",
        "digital_mode_transmission",
        "packet_radio_transmission",
        "scheduled_transmission",
    ]

    def __init__(
        self,
        rig_manager: Any = None,
        digital_modes: Any = None,
        packet_radio: Any = None,
        config: Any = None,
        sdr_transmitter: Any = None,
        ptt_coordinator: Any = None,
    ):
        self.rig_manager = rig_manager
        self.digital_modes = digital_modes
        self.packet_radio = packet_radio
        self.config = config
        self.sdr_transmitter = sdr_transmitter
        self.ptt_coordinator = ptt_coordinator

    async def execute(
        self,
        task: dict[str, Any],
        upstream_callback: Any = None,
    ) -> dict[str, Any]:
        """Execute radio transmission task."""
        transmission_type = task.get("transmission_type", "voice")
        # Accept both "frequency" and "frequency_hz" task keys for compatibility.
        frequency = task.get("frequency")
        if frequency is None:
            frequency = task.get("frequency_hz") or 0.0
        message = task.get("message", "")
        mode = task.get("mode")
        audio_path = task.get("audio_path")
        use_tts = task.get("use_tts") if "use_tts" in task else None

        await self.emit_progress(
            upstream_callback,
            "preparing",
            frequency=frequency,
            mode=mode,
            transmission_type=transmission_type,
        )

        # Compliance: do not TX on restricted or out-of-band frequencies
        radio_cfg = getattr(self.config, "radio", None) if self.config else None
        if frequency and radio_cfg and getattr(radio_cfg, "tx_allowed_bands_only", True):
            restricted_region = getattr(radio_cfg, "restricted_bands_region", "FCC")
            band_plan_source = get_band_plan_source_for_config(
                restricted_region,
                getattr(radio_cfg, "band_plan_region", None),
            )
            if not is_tx_allowed(
                frequency,
                band_plan_source=band_plan_source,
                allow_tx_only_amateur_bands=True,
                restricted_region=restricted_region,
            ):
                err = {
                    "success": False,
                    "frequency": frequency,
                    "transmission_type": transmission_type,
                    "message_sent": message[:100],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "notes": "Frequency not allowed for TX (restricted or out of band)",
                }
                await self.emit_result(upstream_callback, err)
                return err

        try:
            if transmission_type == "voice":
                result = await self._transmit_voice(
                    frequency, message, mode,
                    audio_path=audio_path,
                    use_tts=use_tts,
                )
            elif transmission_type == "digital":
                result = await self._transmit_digital(
                    frequency,
                    message,
                    task.get("digital_mode", "PSK31"),
                )
            elif transmission_type == "packet":
                result = await self._transmit_packet(
                    task.get("destination_callsign", "APRS"),
                    message,
                )
            else:
                raise ValueError(f"Unknown transmission type: {transmission_type}")

            await self.emit_result(upstream_callback, result)
            return result
        except Exception as e:
            logger.exception("Radio TX failed: {}", e)
            await self.emit_error(upstream_callback, str(e))
            raise

    async def _transmit_voice(
        self,
        frequency_hz: float,
        message: str,
        mode: str | None,
        *,
        audio_path: str | Path | None = None,
        use_tts: bool | None = None,
    ) -> dict[str, Any]:
        """Voice transmission: CAT (PTT + audio) or SDR (tone) when use_sdr/sdr_transmitter."""
        use_sdr = getattr(
            getattr(self.config, "radio", None) if self.config else None,
            "sdr_tx_enabled",
            False,
        )
        if use_sdr and self.sdr_transmitter:
            # SDR path: transmit NFM if we have an audio file, else a short tone.
            try:
                mode_name = normalize_mode(mode)
                if audio_path:
                    try:
                        import soundfile as sf
                    except Exception as e:
                        raise RuntimeError(
                            "SDR voice TX from file requires optional deps: uv sync --extra voice_tx"
                        ) from e
                    tx_rate = 2_000_000
                    loop = asyncio.get_running_loop()
                    # Run blocking file I/O in executor to avoid stalling the event loop.
                    data, sr = await loop.run_in_executor(
                        None,
                        lambda: sf.read(str(audio_path), dtype="float32", always_2d=False),
                    )
                    # Modulate to 2 MHz (HackRF-friendly); run CPU-heavy scipy in executor to avoid blocking event loop.
                    if mode_name.value in ("NFM",):
                        iq = await loop.run_in_executor(
                            None, lambda: nfm_modulate(data, int(sr), tx_rate, deviation_hz=2_500.0)
                        )
                    elif mode_name.value == "AM":
                        iq = await loop.run_in_executor(
                            None, lambda: am_modulate(data, int(sr), tx_rate)
                        )
                    elif mode_name.value in ("USB", "LSB"):
                        iq = await loop.run_in_executor(
                            None, lambda: ssb_modulate(data, int(sr), tx_rate, sideband=mode_name.value)
                        )
                    elif mode_name.value == "CW":
                        # CW audio TX is typically keying; as a minimal baseline, emit a short carrier.
                        iq = cw_tone_iq(duration_sec=0.5, rf_rate_hz=tx_rate)
                    else:
                        iq = await loop.run_in_executor(
                            None, lambda: nfm_modulate(data, int(sr), tx_rate, deviation_hz=2_500.0)
                        )
                    # Compliance for SDR TX should consider occupied bandwidth (not just center).
                    bw = {
                        "NFM": 12_500.0,
                        "AM": 10_000.0,
                        "USB": 3_000.0,
                        "LSB": 3_000.0,
                        "CW": 500.0,
                    }.get(mode_name.value, 12_500.0)
                    radio_cfg = getattr(self.config, "radio", None) if self.config else None
                    if radio_cfg and getattr(radio_cfg, "tx_allowed_bands_only", True):
                        restricted_region = getattr(radio_cfg, "restricted_bands_region", "FCC")
                        band_plan_source = get_band_plan_source_for_config(
                            restricted_region,
                            getattr(radio_cfg, "band_plan_region", None),
                        )
                        if not is_tx_spectrum_allowed(
                            frequency_hz,
                            bw,
                            band_plan_source=band_plan_source,
                            allow_tx_only_amateur_bands=True,
                            restricted_region=restricted_region,
                        ):
                            return {
                                "success": False,
                                "frequency": frequency_hz,
                                "mode": mode,
                                "transmission_type": "voice",
                                "message_sent": message[:100],
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "notes": f"TX spectrum not allowed for BW={bw} Hz (mode={mode_name.value})",
                            }

                    await self.sdr_transmitter.transmit_iq(
                        frequency_hz,
                        iq,
                        sample_rate=tx_rate,
                        occupied_bandwidth_hz=bw,
                    )
                else:
                    await self.sdr_transmitter.transmit_tone(
                        frequency_hz, duration_sec=0.5, sample_rate=2_000_000
                    )
                return {
                    "success": True,
                    "frequency": frequency_hz,
                    "mode": mode,
                    "transmission_type": "voice",
                    "message_sent": message[:100],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "notes": f"SDR {mode_name.value} voice (HackRF)" if audio_path else "SDR tone (HackRF)",
                }
            except ValueError as e:
                return {
                    "success": False,
                    "frequency": frequency_hz,
                    "mode": mode,
                    "transmission_type": "voice",
                    "message_sent": message[:100],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "notes": str(e),
                }
        if not self.rig_manager:
            return {
                "success": False,
                "frequency": frequency_hz,
                "mode": mode,
                "transmission_type": "voice",
                "message_sent": message[:100],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "notes": "Rig manager not configured",
                "error": "Rig manager not configured; enable radio.enabled for CAT control or configure SDR TX (radio.sdr_tx_enabled=true).",
            }

        play_path: str | Path | None = None
        voice_use_tts = getattr(
            getattr(self.config, "radio", None) if self.config else None,
            "voice_use_tts",
            False,
        )
        if audio_path:
            play_path = Path(audio_path)
            if not play_path.exists():
                return {
                    "success": False,
                    "frequency": frequency_hz,
                    "mode": mode,
                    "transmission_type": "voice",
                    "message_sent": message[:100],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "notes": f"Audio file not found: {play_path}",
                }
        elif (((use_tts is True) or (use_tts is None and voice_use_tts)) and message):
            play_path: str | None = None
            try:
                import tempfile
                from radioshaq.audio.tts_plugin import synthesize_speech
                tts_cfg = getattr(self.config, "tts", None) if self.config else None
                provider = getattr(tts_cfg, "provider", "elevenlabs") if tts_cfg else "elevenlabs"
                suffix = ".wav" if provider == "kokoro" else ".mp3"
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                    play_path = f.name
                kwargs: dict[str, Any] = {}
                if tts_cfg and provider == "elevenlabs":
                    kwargs["voice"] = getattr(tts_cfg, "elevenlabs_voice_id", None)
                    kwargs["model_id"] = getattr(tts_cfg, "elevenlabs_model_id", None)
                    kwargs["output_format"] = getattr(tts_cfg, "elevenlabs_output_format", None)
                elif tts_cfg and provider == "kokoro":
                    kwargs["voice"] = getattr(tts_cfg, "kokoro_voice", None)
                    kwargs["lang_code"] = getattr(tts_cfg, "kokoro_lang_code", None)
                    kwargs["speed"] = getattr(tts_cfg, "kokoro_speed", None)
                synthesize_speech(message, provider, output_path=play_path, **kwargs)
            except Exception as e:
                if play_path:
                    Path(play_path).unlink(missing_ok=True)
                logger.warning("TTS failed for voice TX: {}", e)
                return {
                    "success": False,
                    "frequency": frequency_hz,
                    "mode": mode,
                    "transmission_type": "voice",
                    "message_sent": message[:100],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "notes": f"TTS failed: {e}",
                }

        # If no explicit frequency is provided, transmit on the current rig frequency.
        if frequency_hz and frequency_hz > 0:
            await self.rig_manager.set_frequency(frequency_hz)
        if mode:
            await self.rig_manager.set_mode(mode)

        if self.ptt_coordinator:
            if not await self.ptt_coordinator.request_transmit():
                return {
                    "success": False,
                    "frequency": frequency_hz,
                    "mode": mode,
                    "transmission_type": "voice",
                    "message_sent": message[:100],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "notes": "TX denied by PTT coordinator (channel busy or safety)",
                }
            if not await self.ptt_coordinator.begin_transmit():
                return {
                    "success": False,
                    "frequency": frequency_hz,
                    "mode": mode,
                    "transmission_type": "voice",
                    "message_sent": message[:100],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "notes": "PTT begin denied by coordinator",
                }

        result_notes = "PTT only (no audio)"
        try:
            if play_path is not None:
                device = None
                if self.config and hasattr(self.config, "radio"):
                    device = getattr(self.config.radio, "audio_output_device", None)
                from radioshaq.audio.playback import play_audio_to_device
                loop = asyncio.get_event_loop()
                duration = await loop.run_in_executor(
                    None,
                    lambda: play_audio_to_device(path=play_path, device=device),
                )
                result_notes = f"played {duration:.1f}s"
            else:
                await asyncio.sleep(0.5)
        finally:
            if self.ptt_coordinator:
                await self.ptt_coordinator.end_transmit()
            else:
                await self.rig_manager.set_ptt(False)

        # Audit log for CAT TX
        radio_cfg = getattr(self.config, "radio", None) if self.config else None
        if radio_cfg and getattr(radio_cfg, "tx_audit_log_path", None):
            duration = 1.0 if play_path is not None else 0.5
            log_tx(
                frequency_hz=frequency_hz,
                duration_sec=duration,
                mode=mode,
                rig_or_sdr="cat",
                audit_log_path=radio_cfg.tx_audit_log_path,
            )

        return {
            "success": True,
            "frequency": frequency_hz,
            "mode": mode,
            "transmission_type": "voice",
            "message_sent": message[:100],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "notes": result_notes,
        }

    async def _transmit_digital(
        self, frequency_hz: float, message: str, digital_mode: str
    ) -> dict[str, Any]:
        """Digital mode transmission via FLDIGI."""
        if not self.digital_modes:
            return {
                "success": False,
                "frequency": frequency_hz,
                "mode": digital_mode,
                "transmission_type": "digital",
                "message_sent": message[:100],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "notes": "FLDIGI not configured",
            }
        if self.rig_manager and frequency_hz and frequency_hz > 0:
            await self.rig_manager.set_frequency(frequency_hz)
        await self.digital_modes.set_modem(digital_mode)
        await self.digital_modes.transmit_text(message)
        return {
            "success": True,
            "frequency": frequency_hz,
            "mode": digital_mode,
            "transmission_type": "digital",
            "message_sent": message[:100],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _transmit_packet(
        self, destination: str, message: str
    ) -> dict[str, Any]:
        """Packet radio transmission."""
        if not self.packet_radio:
            return {
                "success": False,
                "destination": destination,
                "transmission_type": "packet",
                "message_sent": message[:100],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "notes": "Packet radio not configured",
            }
        await self.packet_radio.send_packet(destination, message)
        return {
            "success": True,
            "destination": destination,
            "transmission_type": "packet",
            "message_sent": message[:100],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
