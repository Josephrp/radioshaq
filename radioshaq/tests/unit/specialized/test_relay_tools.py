"""Unit tests for RelayMessageTool."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from radioshaq.specialized.relay_tools import RelayMessageTool


@pytest.mark.unit
def test_relay_tool_to_schema_has_required_params() -> None:
    """to_schema() requires only message and source_band; target_band is optional (required for radio in validate_params)."""
    tool = RelayMessageTool()
    schema = tool.to_schema()
    required = schema["function"]["parameters"]["required"]
    assert "message" in required
    assert "source_band" in required
    assert "target_band" not in required
    assert schema["function"]["name"] == "relay_message_between_bands"


@pytest.mark.unit
def test_relay_tool_validate_params_rejects_missing_message() -> None:
    """validate_params returns error when message is missing."""
    tool = RelayMessageTool()
    err = tool.validate_params({"source_band": "40m", "target_band": "2m"})
    assert any("message" in e for e in err)


@pytest.mark.unit
def test_relay_tool_validate_params_rejects_unknown_band() -> None:
    """validate_params returns error for unknown band."""
    tool = RelayMessageTool()
    err = tool.validate_params({
        "message": "Hi",
        "source_band": "99m",
        "target_band": "2m",
    })
    assert any("Unknown" in e and "source_band" in e for e in err)
    err2 = tool.validate_params({
        "message": "Hi",
        "source_band": "40m",
        "target_band": "99m",
    })
    assert any("Unknown" in e and "target_band" in e for e in err2)


@pytest.mark.unit
def test_relay_tool_validate_params_accepts_valid() -> None:
    """validate_params returns no errors for valid params."""
    tool = RelayMessageTool()
    assert tool.validate_params({
        "message": "Hello",
        "source_band": "40m",
        "target_band": "2m",
    }) == []
    assert tool.validate_params({
        "message": "Hi",
        "source_band": "40m",
        "target_band": "2m",
        "source_callsign": "K5ABC",
        "destination_callsign": "W1XYZ",
        "deliver_at": "2026-12-01T12:00:00Z",
    }) == []


@pytest.mark.unit
def test_relay_tool_validate_params_target_band_required_only_for_radio() -> None:
    """target_band is required when target_channel is radio; optional for sms/whatsapp."""
    tool = RelayMessageTool()
    err_radio = tool.validate_params({"message": "Hi", "source_band": "40m", "target_channel": "radio"})
    assert any("target_band" in e for e in err_radio)
    assert tool.validate_params({
        "message": "Hi",
        "source_band": "40m",
        "target_channel": "whatsapp",
        "destination_phone": "+15551234567",
    }) == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_relay_tool_execute_no_storage_returns_error() -> None:
    """When storage is None, execute returns error string."""
    tool = RelayMessageTool(storage=None)
    result = await tool.execute(message="Hi", source_band="40m", target_band="2m")
    assert result.startswith("Error")
    assert "no storage" in result.lower() or "not available" in result.lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_relay_tool_execute_calls_service_and_formats_result() -> None:
    """Execute calls relay_message_between_bands_service and returns string with Relayed and ids."""
    storage = MagicMock()
    storage.db = MagicMock()
    storage.store = AsyncMock(side_effect=[101, 102])
    queue = MagicMock()
    get_radio_tx = MagicMock(return_value=None)
    config = MagicMock()

    with patch("radioshaq.specialized.relay_tools.relay_message_between_bands_service", new_callable=AsyncMock) as m_svc:
        m_svc.return_value = {
            "ok": True,
            "source_transcript_id": 101,
            "relayed_transcript_id": 102,
            "source_band": "40m",
            "target_band": "2m",
        }
        tool = RelayMessageTool(
            storage=storage,
            injection_queue=queue,
            get_radio_tx=get_radio_tx,
            config=config,
        )
        result = await tool.execute(
            message="Hello",
            source_band="40m",
            target_band="2m",
        )
        assert "Relayed" in result
        assert "101" in result
        assert "102" in result
        m_svc.assert_awaited_once()
        call_kw = m_svc.await_args[1]
        assert call_kw["message"] == "Hello"
        assert call_kw["source_band"] == "40m"
        assert call_kw["target_band"] == "2m"
        assert call_kw["storage"] is storage
        assert call_kw["injection_queue"] is queue
