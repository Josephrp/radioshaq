"""Live E2E workflows that require a running API and real provider keys."""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Iterator

import httpx
import pytest


_LIVE_KEY_ENV_VARS = (
    "RADIOSHAQ_LLM__MISTRAL_API_KEY",
    "RADIOSHAQ_LLM__OPENAI_API_KEY",
    "RADIOSHAQ_LLM__ANTHROPIC_API_KEY",
    "RADIOSHAQ_LLM__GEMINI_API_KEY",
    "MISTRAL_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
)


def _base_url() -> str | None:
    return os.environ.get("BASE_URL", "").rstrip("/") or None


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _has_live_key() -> bool:
    return any(os.environ.get(name, "").strip() for name in _LIVE_KEY_ENV_VARS)


@pytest.fixture(scope="module")
def live_base_url() -> str:
    base_url = _base_url()
    if not base_url:
        pytest.skip("BASE_URL not set")
    if not _truthy("RUN_LIVE_E2E"):
        pytest.skip("RUN_LIVE_E2E is not enabled")
    if not _has_live_key():
        pytest.skip("No real provider API key found in environment")
    return base_url


@pytest.fixture(scope="module")
def live_client(live_base_url: str) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=live_base_url, timeout=30.0) as client:
        yield client


def _auth_headers(client: httpx.Client) -> dict[str, str]:
    r = client.post(
        "/auth/token",
        params={"subject": "live-e2e", "role": "field", "station_id": "LIVE-E2E-01"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
@pytest.mark.live_api
@pytest.mark.live_e2e
def test_live_process_message_with_real_llm(live_client: httpx.Client) -> None:
    """End-to-end live orchestrator request must return a normal response payload."""
    headers = _auth_headers(live_client)
    prompt = "Reply with one short tactical acknowledgement for station LIVE-E2E-01."

    r = live_client.post("/messages/process", headers=headers, json={"message": prompt})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "success" in data
    assert isinstance(data.get("message"), str)
    assert data["message"].strip()
    assert isinstance(data.get("task_id"), str)
    assert data["task_id"].strip()


@pytest.mark.integration
@pytest.mark.live_api
@pytest.mark.live_e2e
def test_live_relay_and_transcript_poll_workflow(live_client: httpx.Client) -> None:
    """Relay a live message and verify transcript search returns the relayed item."""
    headers = _auth_headers(live_client)
    run_id = uuid.uuid4().hex[:8].upper()
    destination = f"W1E2E{run_id[:3]}"
    payload = {
        "message": f"LIVE-E2E relay workflow {run_id}",
        "source_band": "40m",
        "target_band": "2m",
        "source_callsign": "K1LIVE",
        "destination_callsign": destination,
    }

    relay = live_client.post("/messages/relay", headers=headers, json=payload)
    assert relay.status_code == 200, relay.text
    relay_data = relay.json()
    if relay_data.get("relay") == "no_storage":
        pytest.skip("Relay accepted but transcript storage is unavailable")

    deadline = time.monotonic() + 10.0
    matched = False
    while time.monotonic() < deadline:
        search = live_client.get(
            "/transcripts",
            headers=headers,
            params={"callsign": destination, "destination_only": "true", "band": "2m", "limit": 100},
        )
        assert search.status_code == 200, search.text
        search_data = search.json()
        assert "transcripts" in search_data
        transcripts = search_data["transcripts"]
        assert isinstance(transcripts, list)
        matched = any(
            isinstance(t, dict)
            and t.get("destination_callsign") == destination
            and run_id in str(t.get("transcript_text", ""))
            for t in transcripts
        )
        if matched:
            break
        time.sleep(0.5)

    assert matched, f"Transcript for destination={destination!r} run_id={run_id!r} not found within 10 s"
