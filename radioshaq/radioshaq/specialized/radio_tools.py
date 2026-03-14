"""Agent tools for radio (LLM-callable). Implements nanobot Tool protocol for send_audio_over_radio."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from radioshaq.specialized.radio_tx import RadioTransmissionAgent


class SendAudioOverRadioTool:
    """
    Tool: send audio over the radio (voice TX with optional TTS or file).
    Uses CAT rig + sound device (Option A). Register with ToolRegistry for LLM function calling.
    """

    name = "send_audio_over_radio"
    description = (
        "Transmit voice over ham radio: send a message (optionally as TTS) or an audio file "
        "on a given frequency and mode. Uses the configured rig and audio output device."
    )

    def __init__(self, rig_manager: Any = None, config: Any = None):
        self._agent = RadioTransmissionAgent(
            rig_manager=rig_manager,
            digital_modes=None,
            packet_radio=None,
            config=config,
        )

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "Text to speak (used for TTS when use_tts is true or as fallback label)",
                        },
                        "frequency_hz": {
                            "type": "number",
                            "description": "Frequency in Hz (e.g. 7200000 for 7.2 MHz)",
                        },
                        "mode": {
                            "type": "string",
                            "description": "Mode: FM, LSB, USB, etc.",
                            "default": "FM",
                        },
                        "audio_path": {
                            "type": "string",
                            "description": "Optional path to WAV/MP3 file to transmit instead of TTS",
                        },
                        "use_tts": {
                            "type": "boolean",
                            "description": "If true, generate speech from message using TTS before transmitting",
                            "default": False,
                        },
                    },
                    "required": ["frequency_hz"],
                },
            },
        }

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        errors = []
        if "frequency_hz" not in params:
            errors.append("frequency_hz is required")
        elif not isinstance(params.get("frequency_hz"), (int, float)):
            errors.append("frequency_hz must be a number")
        if "message" not in params and "audio_path" not in params:
            errors.append("Either message or audio_path is required")
        if "audio_path" in params and params["audio_path"]:
            p = Path(params["audio_path"])
            if not p.exists():
                errors.append(f"audio_path not found: {params['audio_path']}")
        return errors

    async def execute(
        self,
        message: str = "",
        frequency_hz: float = 0.0,
        mode: str = "FM",
        audio_path: str | None = None,
        use_tts: bool = False,
        **kwargs: Any,
    ) -> str:
        if not self._agent.rig_manager:
            return "Error: Rig not configured. Enable radio and set rig_model/port in config."
        task = {
            "transmission_type": "voice",
            "frequency": frequency_hz,
            "message": message or "",
            "mode": mode,
            "audio_path": audio_path,
            "use_tts": use_tts,
        }
        try:
            result = await self._agent.execute(task, upstream_callback=None)
            if result.get("success"):
                return (
                    f"Transmitted on {result.get('frequency')} Hz {result.get('mode')}: "
                    f"{result.get('notes', 'ok')}"
                )
            return f"Error: {result.get('notes', result.get('error', 'Unknown failure'))}"
        except Exception as e:
            logger.exception("send_audio_over_radio failed: {}", e)
            return f"Error: {e}"