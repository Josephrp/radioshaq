"""Radio transmission specialized agent."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger

from shakods.middleware.upstream import UpstreamEvent
from shakods.specialized.base import SpecializedAgent


class RadioTransmissionAgent(SpecializedAgent):
    """
    Specialized agent for ham radio transmission.
    Supports voice, digital modes, and packet radio.
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
    ):
        self.rig_manager = rig_manager
        self.digital_modes = digital_modes
        self.packet_radio = packet_radio

    async def execute(
        self,
        task: dict[str, Any],
        upstream_callback: Any = None,
    ) -> dict[str, Any]:
        """Execute radio transmission task."""
        transmission_type = task.get("transmission_type", "voice")
        frequency = task.get("frequency", 0.0)
        message = task.get("message", "")
        mode = task.get("mode", "FM")

        await self.emit_progress(
            upstream_callback,
            "preparing",
            frequency=frequency,
            mode=mode,
            transmission_type=transmission_type,
        )

        try:
            if transmission_type == "voice":
                result = await self._transmit_voice(frequency, message, mode)
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
            logger.exception("Radio TX failed: %s", e)
            await self.emit_error(upstream_callback, str(e))
            raise

    async def _transmit_voice(
        self, frequency_hz: float, message: str, mode: str
    ) -> dict[str, Any]:
        """Voice transmission via rig (PTT + message for logging)."""
        if not self.rig_manager:
            return {
                "success": False,
                "frequency": frequency_hz,
                "mode": mode,
                "transmission_type": "voice",
                "message_sent": message[:100],
                "timestamp": datetime.utcnow().isoformat(),
                "notes": "Rig manager not configured",
            }
        await self.rig_manager.set_frequency(frequency_hz)
        await self.rig_manager.set_mode(mode)
        await self.rig_manager.set_ptt(True)
        try:
            import asyncio
            await asyncio.sleep(0.5)
        finally:
            await self.rig_manager.set_ptt(False)
        return {
            "success": True,
            "frequency": frequency_hz,
            "mode": mode,
            "transmission_type": "voice",
            "message_sent": message[:100],
            "timestamp": datetime.utcnow().isoformat(),
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
                "timestamp": datetime.utcnow().isoformat(),
                "notes": "FLDIGI not configured",
            }
        if self.rig_manager:
            await self.rig_manager.set_frequency(frequency_hz)
        await self.digital_modes.set_modem(digital_mode)
        await self.digital_modes.transmit_text(message)
        return {
            "success": True,
            "frequency": frequency_hz,
            "mode": digital_mode,
            "transmission_type": "digital",
            "message_sent": message[:100],
            "timestamp": datetime.utcnow().isoformat(),
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
                "timestamp": datetime.utcnow().isoformat(),
                "notes": "Packet radio not configured",
            }
        await self.packet_radio.send_packet(destination, message)
        return {
            "success": True,
            "destination": destination,
            "transmission_type": "packet",
            "message_sent": message[:100],
            "timestamp": datetime.utcnow().isoformat(),
        }
