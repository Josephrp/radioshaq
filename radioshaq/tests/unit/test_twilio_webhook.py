from __future__ import annotations

from typing import Any


def test_twilio_sms_webhook_publishes_inbound(client: Any) -> None:
    from radioshaq.api.server import app

    bus = getattr(app.state, "message_bus", None)
    assert bus is not None
    before = bus.get_stats()["inbound_published"]

    r = client.post(
        "/twilio/sms",
        data={
            "From": "+15551234567",
            "To": "+15557654321",
            "Body": "hello from sms",
            "MessageSid": "SMTEST123",
            "NumMedia": "0",
        },
    )
    assert r.status_code == 200

    after = bus.get_stats()["inbound_published"]
    assert after == before + 1


def test_twilio_whatsapp_webhook_publishes_inbound(client: Any) -> None:
    from radioshaq.api.server import app

    bus = getattr(app.state, "message_bus", None)
    assert bus is not None
    before = bus.get_stats()["inbound_published"]

    r = client.post(
        "/twilio/whatsapp",
        data={
            "From": "whatsapp:+15551234567",
            "To": "whatsapp:+15557654321",
            "Body": "hello from whatsapp",
            "MessageSid": "SMTEST456",
            "NumMedia": "0",
        },
    )
    assert r.status_code == 200

    after = bus.get_stats()["inbound_published"]
    assert after == before + 1

