"""Radio reception specialized agent."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from shakods.specialized.base import SpecializedAgent


class RadioReceptionAgent(SpecializedAgent):
    """
    Specialized agent for ham radio reception and monitoring.
    """

    name = "radio_rx"
    description = "Monitors and receives messages via ham radio"
    capabilities = [
        "frequency_monitoring",
        "message_reception",
        "signal_reporting",
        "band_scanning",
    ]

    def __init__(
        self,
        rig_manager: Any = None,
        digital_modes: Any = None,
    ):
        self.rig_manager = rig_manager
        self.digital_modes = digital_modes

    async def execute(
        self,
        task: dict[str, Any],
        upstream_callback: Any = None,
    ) -> dict[str, Any]:
        """Execute monitor task: monitor_frequency for duration."""
        frequency = task.get("frequency", 0.0)
        duration_seconds = int(task.get("duration_seconds", 10))
        mode = task.get("mode", "FM")
        return await self.monitor_frequency(
            frequency,
            duration_seconds,
            mode=mode,
            upstream_callback=upstream_callback,
        )

    async def monitor_frequency(
        self,
        frequency: float,
        duration_seconds: int,
        mode: str = "FM",
        upstream_callback: Any = None,
    ) -> dict[str, Any]:
        """Monitor a frequency for incoming transmissions."""
        received_messages: list[dict[str, Any]] = []
        loop = asyncio.get_running_loop()
        start = loop.time()

        if self.rig_manager:
            await self.rig_manager.set_frequency(frequency)
            await self.rig_manager.set_mode(mode)

        try:
            from shakods.radio.injection import get_injection_queue
            injection_queue = get_injection_queue()
        except Exception:
            injection_queue = None

        while (loop.time() - start) < duration_seconds:
            if self.digital_modes and mode in ("PSK31", "FT8", "RTTY", "CW"):
                try:
                    text = await asyncio.wait_for(
                        self.digital_modes.receive_text(timeout=1.0),
                        timeout=1.5,
                    )
                    if text:
                        msg = {"message": text, "mode": mode}
                        received_messages.append(msg)
                        await self.emit_result(upstream_callback, msg)
                except asyncio.TimeoutError:
                    pass
            elif injection_queue:
                # Demo path: no FLDIGI; consume from injection queue (user injection script)
                inj = injection_queue.receive_injected_nowait()
                if inj:
                    msg = {
                        "message": inj.text,
                        "mode": inj.mode,
                        "frequency": inj.frequency_hz or frequency,
                        "band": inj.band,
                        "source_callsign": inj.source_callsign,
                    }
                    received_messages.append(msg)
                    await self.emit_result(upstream_callback, msg)

            await self.emit_progress(
                upstream_callback,
                "monitoring",
                frequency=frequency,
                mode=mode,
                elapsed=loop.time() - start,
                messages_received=len(received_messages),
            )
            await asyncio.sleep(0.5)

        return {
            "frequency": frequency,
            "duration": duration_seconds,
            "messages_received": len(received_messages),
            "messages": received_messages,
        }
