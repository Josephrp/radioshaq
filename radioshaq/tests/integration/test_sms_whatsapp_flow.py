"""Integration tests for SMS/WhatsApp config and agent registry.

With Twilio env unset, SMS agent is registered and send returns twilio_not_configured;
WhatsApp agent is registered and send returns not configured.
Does not call real Twilio API.
"""

from __future__ import annotations

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_registry_sms_and_whatsapp_registered_without_twilio() -> None:
    """Without Twilio config, both sms and whatsapp agents are registered; send returns not configured."""
    from radioshaq.config.schema import Config
    from radioshaq.orchestrator.factory import create_agent_registry

    config = Config()
    # Ensure twilio is empty (default)
    assert getattr(config.twilio, "account_sid", None) is None or config.twilio.account_sid is None
    registry = create_agent_registry(config, db=None, message_bus=None)
    sms = registry.get_agent("sms")
    whatsapp = registry.get_agent("whatsapp")
    assert sms is not None
    assert whatsapp is not None

    result_sms = await sms.execute(
        {"action": "send", "to": "+15551234567", "message": "Test"},
        upstream_callback=None,
    )
    assert result_sms.get("success") is False
    assert result_sms.get("reason") == "twilio_not_configured" or "not configured" in (result_sms.get("notes") or "")

    result_wa = await whatsapp.execute(
        {"action": "send_message", "to": "+15551234567", "message": "Test"},
        upstream_callback=None,
    )
    assert result_wa.get("success") is False
    assert "not configured" in (result_wa.get("notes") or "").lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sms_agent_receive_placeholder() -> None:
    """SMS agent receive action returns placeholder without Twilio."""
    from radioshaq.config.schema import Config
    from radioshaq.orchestrator.factory import create_agent_registry

    config = Config()
    registry = create_agent_registry(config, db=None, message_bus=None)
    sms = registry.get_agent("sms")
    assert sms is not None
    result = await sms.execute({"action": "receive"}, upstream_callback=None)
    assert result.get("success") is True
    assert result.get("action") == "receive"
