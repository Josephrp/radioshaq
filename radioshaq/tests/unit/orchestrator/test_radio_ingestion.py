"""Unit tests for radio_ingestion helper."""

from __future__ import annotations

import pytest

from radioshaq.orchestrator.radio_ingestion import radio_received_to_inbound


@pytest.mark.unit
def test_radio_received_to_inbound_shape() -> None:
    """InboundMessage has channel=radio_rx, sender_id=source_callsign, chat_id=band, content=text, metadata."""
    msg = radio_received_to_inbound(
        text="hello from 40m",
        band="40m",
        frequency_hz=7.15e6,
        source_callsign="W1ABC",
        destination_callsign="K5XYZ",
        mode="SSB",
    )
    assert msg.channel == "radio_rx"
    assert msg.sender_id == "W1ABC"
    assert msg.chat_id == "40m"
    assert msg.content == "hello from 40m"
    assert msg.metadata.get("band") == "40m"
    assert msg.metadata.get("frequency_hz") == 7.15e6
    assert msg.metadata.get("destination_callsign") == "K5XYZ"
    assert msg.metadata.get("mode") == "SSB"


@pytest.mark.unit
def test_radio_received_to_inbound_defaults() -> None:
    """Missing source_callsign becomes UNKNOWN; missing band chat_id is 'radio'."""
    msg = radio_received_to_inbound(text="test", band=None)
    assert msg.sender_id == "UNKNOWN"
    assert msg.chat_id == "radio"
    assert msg.metadata.get("band") is None
