"""Integration test: relay tool registered and execute returns success.

When app has db and tool_registry is created with app=app, relay_message_between_bands
tool is registered. We assert tool_registry.execute("relay_message_between_bands", {...})
returns a success message (Relayed or no_storage). When DB is unavailable the relay tool
may not be registered; test skips.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest


@pytest.mark.integration
def test_relay_tool_execute_via_registry(client: Any) -> None:
    """Trigger lifespan, then execute relay tool and assert success or no_storage."""
    # Ensure lifespan has run (tool_registry and optionally relay tool registered)
    r = client.get("/health")
    assert r.status_code in (200, 404)  # health may not exist
    from radioshaq.api.server import app

    registry = getattr(app.state, "tool_registry", None)
    if registry is None:
        pytest.skip("Tool registry not available")
    if "relay_message_between_bands" not in registry.tool_names:
        pytest.skip("Relay tool not registered (requires db and app)")
    params = {
        "message": "Hello from integration test",
        "source_band": "40m",
        "target_band": "2m",
        "source_callsign": "K5ABC",
        "destination_callsign": "W1XYZ",
    }
    result = asyncio.run(registry.execute("relay_message_between_bands", params))
    assert isinstance(result, str)
    assert "Relayed" in result or "no storage" in result or "no DB" in result.lower()
    if result.startswith("Error"):
        assert "not found" not in result
