from __future__ import annotations

from radioshaq.config.schema import Config
from radioshaq.orchestrator.factory import _create_sdr_transmitter
from radioshaq.radio.sdr_tx import HackRFServiceClient


def test_remote_sdr_tx_uses_service_token_for_auth() -> None:
    base = {
        "mode": "field",
        "radio": {
            "sdr_tx_enabled": True,
            "sdr_tx_backend": "hackrf",
            "sdr_tx_mode": "remote",
            "sdr_tx_service_base_url": "http://example",
            "sdr_tx_service_token": "TESTTOKEN",
        },
    }
    cfg = Config(**base)
    tx = _create_sdr_transmitter(cfg)
    assert isinstance(tx, HackRFServiceClient)
    # Internal auth token should match the configured service token.
    assert getattr(tx, "_auth_token", None) == "TESTTOKEN"

