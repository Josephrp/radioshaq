"""Integration tests: inject/relay then poll transcripts with band and destination_only.

Requires app with DB and transcripts table (migrations applied). When DB is unavailable,
relay returns no_storage and search returns empty; tests accept 200 and skip assertions
that require stored data.
"""

from __future__ import annotations

import pytest

from fastapi.testclient import TestClient


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    r = client.post(
        "/auth/token",
        params={"subject": "relay-test", "role": "field", "station_id": "W1XYZ"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
def test_relay_then_poll_by_destination_and_band(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Relay a message to 2m for W1XYZ, then poll with destination_only=true and band=2m."""
    relay_body = {
        "message": "Integration test message for W1XYZ on 2m",
        "source_band": "40m",
        "target_band": "2m",
        "source_callsign": "K5ABC",
        "destination_callsign": "W1XYZ",
    }
    r_relay = client.post("/messages/relay", headers=auth_headers, json=relay_body)
    assert r_relay.status_code == 200
    data_relay = r_relay.json()
    if data_relay.get("relay") == "no_storage":
        pytest.skip("No DB: relay accepted but not stored")
    assert "source_transcript_id" in data_relay
    assert "relayed_transcript_id" in data_relay

    r_search = client.get(
        "/transcripts",
        headers=auth_headers,
        params={"callsign": "W1XYZ", "destination_only": "true", "band": "2m", "limit": 20},
    )
    assert r_search.status_code == 200
    search_data = r_search.json()
    assert "transcripts" in search_data
    assert "count" in search_data
    transcripts = search_data["transcripts"]
    # At least the relayed message we just stored
    assert search_data["count"] >= 1
    for t in transcripts:
        assert t.get("destination_callsign") == "W1XYZ"
        extra = t.get("extra_data") or {}
        assert extra.get("band") == "2m"
