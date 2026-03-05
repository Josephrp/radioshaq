"""Unit tests for relay_message_between_bands_service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from radioshaq.relay.service import relay_message_between_bands_service


@pytest.mark.unit
@pytest.mark.asyncio
async def test_relay_service_no_storage_returns_no_storage_dict() -> None:
    """When storage is None, return ok=True, relay=no_storage with band/freq/callsign."""
    result = await relay_message_between_bands_service(
        message="Hello",
        source_band="40m",
        target_band="2m",
        storage=None,
    )
    assert result["ok"] is True
    assert result.get("relay") == "no_storage"
    assert result["source_band"] == "40m"
    assert result["target_band"] == "2m"
    assert "source_frequency_hz" in result
    assert "target_frequency_hz" in result
    assert result.get("source_transcript_id") is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_relay_service_storage_without_db_returns_no_storage() -> None:
    """When storage has no _db, return no_storage (same as None)."""
    storage = MagicMock(spec=[])
    result = await relay_message_between_bands_service(
        message="Test",
        source_band="40m",
        target_band="2m",
        storage=storage,
    )
    assert result["ok"] is True
    assert result.get("relay") == "no_storage"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_relay_service_with_mock_storage_two_store_calls() -> None:
    """With mock storage (store returns ids), assert two store calls and correct metadata."""
    storage = MagicMock(_db=MagicMock())
    storage.store = AsyncMock(side_effect=[101, 102])
    result = await relay_message_between_bands_service(
        message="Relay me",
        source_band="40m",
        target_band="2m",
        source_callsign="K5ABC",
        destination_callsign="W1XYZ",
        storage=storage,
    )
    assert result["ok"] is True
    assert result["source_transcript_id"] == 101
    assert result["relayed_transcript_id"] == 102
    assert result["source_band"] == "40m"
    assert result["target_band"] == "2m"
    assert storage.store.await_count == 2
    call1 = storage.store.await_args_list[0]
    call2 = storage.store.await_args_list[1]
    assert call1[1]["metadata"] == {"band": "40m", "relay_role": "source"}
    assert call1[1]["transcript_text"] == "Relay me"
    assert call2[1]["metadata"]["band"] == "2m"
    assert call2[1]["metadata"]["relay_role"] == "relayed"
    assert call2[1]["metadata"]["relay_from_transcript_id"] == 101
    assert call2[1]["metadata"]["relay_from_band"] == "40m"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_relay_service_store_only_relayed_one_store_call() -> None:
    """When store_only_relayed=True, only the relayed row is stored; source_transcript_id is None."""
    storage = MagicMock(_db=MagicMock())
    storage.store = AsyncMock(return_value=202)
    result = await relay_message_between_bands_service(
        message="Relay only",
        source_band="40m",
        target_band="2m",
        storage=storage,
        store_only_relayed=True,
    )
    assert result["ok"] is True
    assert result["source_transcript_id"] is None
    assert result["relayed_transcript_id"] == 202
    assert storage.store.await_count == 1
    call_kw = storage.store.await_args[1]
    assert call_kw["metadata"]["band"] == "2m"
    assert call_kw["metadata"]["relay_role"] == "relayed"
    assert call_kw["metadata"]["relay_from_transcript_id"] is None
    assert call_kw["metadata"]["relay_from_band"] == "40m"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_relay_service_unknown_band_returns_error_dict() -> None:
    """Unknown band returns ok=False and error message."""
    result = await relay_message_between_bands_service(
        message="Hi",
        source_band="99m",
        target_band="2m",
        storage=MagicMock(_db=MagicMock()),
    )
    assert result["ok"] is False
    assert "error" in result
    assert "Unknown band" in result["error"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_relay_service_deliver_at_set_no_inject_no_tx() -> None:
    """When deliver_at is set, do not call inject_message or radio_tx.execute."""
    storage = MagicMock(_db=MagicMock())
    storage.store = AsyncMock(side_effect=[1, 2])
    queue = MagicMock()
    radio_tx = MagicMock(execute=AsyncMock())
    config = MagicMock()
    config.relay_inject_target_band = True
    config.relay_tx_target_band = True
    result = await relay_message_between_bands_service(
        message="Scheduled",
        source_band="40m",
        target_band="2m",
        deliver_at="2026-12-01T12:00:00Z",
        storage=storage,
        injection_queue=queue,
        radio_tx_agent=radio_tx,
        config=config,
    )
    assert result["ok"] is True
    queue.inject_message.assert_not_called()
    radio_tx.execute.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_relay_service_immediate_with_config_inject_and_tx() -> None:
    """When deliver_at is None and config enables inject and TX, call both."""
    storage = MagicMock(_db=MagicMock())
    storage.store = AsyncMock(side_effect=[10, 20])
    queue = MagicMock()
    radio_tx = MagicMock(execute=AsyncMock())
    config = MagicMock()
    config.relay_inject_target_band = True
    config.relay_tx_target_band = True
    result = await relay_message_between_bands_service(
        message="Immediate",
        source_band="40m",
        target_band="2m",
        storage=storage,
        injection_queue=queue,
        radio_tx_agent=radio_tx,
        config=config,
    )
    assert result["ok"] is True
    queue.inject_message.assert_called_once()
    call_kw = queue.inject_message.call_args[1]
    assert call_kw["text"] == "Immediate"
    assert call_kw["band"] == "2m"
    assert call_kw["source_callsign"] == "UNKNOWN"
    radio_tx.execute.assert_awaited_once()
    tx_call = radio_tx.execute.await_args[0][0]
    assert tx_call.get("message") == "Immediate"
    assert tx_call.get("transmission_type") == "voice"
    assert 144e6 <= tx_call.get("frequency", 0) <= 148e6
