"""Helper: build InboundMessage from received radio message for MessageBus."""

from __future__ import annotations

from radioshaq.vendor.nanobot.bus.events import InboundMessage


def radio_received_to_inbound(
    text: str,
    band: str | None = None,
    frequency_hz: float = 0.0,
    source_callsign: str | None = None,
    destination_callsign: str | None = None,
    mode: str | None = None,
) -> InboundMessage:
    """Build InboundMessage for a received radio message. chat_id=band so reply path uses correct band."""
    return InboundMessage(
        channel="radio_rx",
        sender_id=(source_callsign or "UNKNOWN").strip().upper(),
        chat_id=band or "radio",
        content=text or "",
        metadata={
            "band": band,
            "frequency_hz": frequency_hz,
            "destination_callsign": destination_callsign,
            "mode": mode or "",
        },
    )
