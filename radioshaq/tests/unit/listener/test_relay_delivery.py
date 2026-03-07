"""Unit tests for relay_delivery worker: notify-on-relay (§8.3)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from radioshaq.listener.relay_delivery import _is_consent_valid_for_region, run_relay_delivery_worker


@pytest.mark.unit
def test_is_consent_valid_for_region_no_consent_at():
    """Consent invalid when notify_consent_at is missing."""
    assert _is_consent_valid_for_region("FCC", {"notify_consent_at": None}) is False
    assert _is_consent_valid_for_region("CEPT", {"notify_consent_at": None}) is False


@pytest.mark.unit
def test_is_consent_valid_for_region_with_consent():
    """Consent valid when notify_consent_at is set."""
    assert _is_consent_valid_for_region("FCC", {"notify_consent_at": "2026-03-07T12:00:00Z"}) is True
    assert _is_consent_valid_for_region("CEPT", {"notify_consent_at": "2026-03-07T12:00:00Z"}) is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_relay_delivery_notify_on_relay_publishes_when_prefs_set():
    """After radio delivery, if destination_callsign has notify_on_relay and phones, publish_outbound is called."""
    stop = asyncio.Event()
    pending = [
        {
            "id": 1,
            "transcript_text": "Hello from K5ABC",
            "source_callsign": "K5ABC",
            "destination_callsign": "W1XYZ",
            "extra_data": {"band": "40m"},
            "mode": "SSB",
            "frequency_hz": 7.2e6,
        }
    ]
    db = MagicMock()
    db.search_pending_relay_deliveries = AsyncMock(return_value=pending)
    db.mark_transcript_delivery_done = AsyncMock(return_value=True)
    db.get_contact_preferences = AsyncMock(
        return_value={
            "callsign": "W1XYZ",
            "notify_sms_phone": "+15559876543",
            "notify_whatsapp_phone": None,
            "notify_on_relay": True,
            "notify_consent_at": "2026-03-07T12:00:00Z",
            "notify_consent_source": "api",
            "notify_opt_out_at": None,
            "notify_opt_out_at_sms": None,
            "notify_opt_out_at_whatsapp": None,
        }
    )
    message_bus = MagicMock()
    message_bus.publish_outbound = AsyncMock(return_value=True)
    config = MagicMock()
    config.radio = MagicMock()
    config.radio.restricted_bands_region = "FCC"
    config.radio.relay_tx_target_band = False

    mock_queue = MagicMock()
    with patch("radioshaq.listener.relay_delivery.get_injection_queue", return_value=mock_queue):
        async def run_once():
            task = asyncio.create_task(
                run_relay_delivery_worker(
                    db,
                    config,
                    stop_event=stop,
                    interval_seconds=0.05,
                    message_bus=message_bus,
                )
            )
            await asyncio.sleep(0.15)
            stop.set()
            await asyncio.wait_for(task, timeout=3.0)

        await run_once()

    db.get_contact_preferences.assert_called_once_with("W1XYZ")
    message_bus.publish_outbound.assert_called()
    calls = message_bus.publish_outbound.call_args_list
    assert len(calls) >= 1
    outbound = calls[0][0][0]
    assert outbound.channel == "sms"
    assert outbound.chat_id == "+15559876543"
    assert "new message" in outbound.content and "40m" in outbound.content and "K5ABC" in outbound.content


@pytest.mark.unit
@pytest.mark.asyncio
async def test_relay_delivery_skips_notify_when_opt_out():
    """Notify-on-relay is skipped when notify_opt_out_at is set."""
    stop = asyncio.Event()
    pending = [
        {
            "id": 2,
            "transcript_text": "Hi",
            "source_callsign": "K5ABC",
            "destination_callsign": "W2ABC",
            "extra_data": {"band": "2m"},
            "mode": "FM",
            "frequency_hz": 146.52e6,
        }
    ]
    db = MagicMock()
    db.search_pending_relay_deliveries = AsyncMock(return_value=pending)
    db.mark_transcript_delivery_done = AsyncMock(return_value=True)
    db.get_contact_preferences = AsyncMock(
        return_value={
            "callsign": "W2ABC",
            "notify_sms_phone": "+15551111111",
            "notify_whatsapp_phone": None,
            "notify_on_relay": True,
            "notify_consent_at": "2026-03-07T12:00:00Z",
            "notify_opt_out_at_sms": "2026-03-08T00:00:00Z",
            "notify_opt_out_at_whatsapp": None,
        }
    )
    message_bus = MagicMock()
    message_bus.publish_outbound = AsyncMock(return_value=True)
    config = MagicMock()
    config.radio = MagicMock()
    config.radio.restricted_bands_region = "FCC"
    config.radio.relay_tx_target_band = False

    mock_queue = MagicMock()
    with patch("radioshaq.listener.relay_delivery.get_injection_queue", return_value=mock_queue):
        async def run_once():
            task = asyncio.create_task(
                run_relay_delivery_worker(
                    db,
                    config,
                    stop_event=stop,
                    interval_seconds=0.05,
                    message_bus=message_bus,
                )
            )
            await asyncio.sleep(0.15)
            stop.set()
            await asyncio.wait_for(task, timeout=3.0)

        await run_once()

    message_bus.publish_outbound.assert_not_called()
