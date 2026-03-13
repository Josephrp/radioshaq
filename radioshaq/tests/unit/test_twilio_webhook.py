from __future__ import annotations

from typing import Any


def _enable_unsigned_twilio(app) -> None:
    cfg = getattr(app.state, "config", None)
    if cfg and getattr(cfg, "twilio", None):
        cfg.twilio.allow_unsigned_webhooks = True
        # Clear auth_token so tests do not depend on host environment secrets.
        cfg.twilio.auth_token = None


def test_twilio_sms_webhook_publishes_inbound(client: Any) -> None:
    from radioshaq.api.server import app

    bus = getattr(app.state, "message_bus", None)
    assert bus is not None
    before = bus.get_stats()["inbound_published"]

    _enable_unsigned_twilio(app)

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

    _enable_unsigned_twilio(app)

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


def test_twilio_webhook_503_when_missing_auth_token_and_unsigned_not_allowed(client: Any) -> None:
    from radioshaq.api.server import app

    cfg = getattr(app.state, "config", None)
    if cfg and getattr(cfg, "twilio", None):
        cfg.twilio.auth_token = None
        cfg.twilio.allow_unsigned_webhooks = False

    r = client.post(
        "/twilio/sms",
        data={
            "From": "+15551234567",
            "To": "+15557654321",
            "Body": "hello from sms",
            "MessageSid": "SMTEST789",
            "NumMedia": "0",
        },
    )
    assert r.status_code == 503


def test_twilio_webhook_403_when_invalid_signature(client: Any, monkeypatch: Any) -> None:
    from radioshaq.api.server import app

    cfg = getattr(app.state, "config", None)
    if cfg and getattr(cfg, "twilio", None):
        cfg.twilio.auth_token = "TESTTOKEN"
        cfg.twilio.allow_unsigned_webhooks = False

    # Ensure RequestValidator.validate returns False to simulate bad signature.
    from twilio import request_validator as twilio_request_validator

    class _FakeValidator:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        def validate(self, *_: Any, **__: Any) -> bool:
            return False

    monkeypatch.setattr(twilio_request_validator, "RequestValidator", _FakeValidator)

    r = client.post(
        "/twilio/sms",
        headers={"x-twilio-signature": "bad"},
        data={
            "From": "+15551234567",
            "To": "+15557654321",
            "Body": "hello from sms",
            "MessageSid": "SMTESTSIG",
            "NumMedia": "0",
        },
    )
    assert r.status_code == 403

