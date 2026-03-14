"""Integration tests that mirror the live demo flows (stubbed hardware, no Twilio).

These tests exercise the same API endpoints and success criteria as the scripts in
scripts/demo/ (run_radio_rx_injection_demo, run_whitelist_flow_demo, Option C no-Twilio,
send-audio/send-tts with stub). They use the test client and fixtures (no real HackRF,
no real LLM/Twilio). Mark as integration so CI can skip if DB or app unavailable.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest


@pytest.fixture
def demo_auth_headers(client):
    """JWT for demo-style tests (subject demo-op1, station DEMO-01)."""
    r = client.post(
        "/auth/token",
        params={"subject": "demo-op1", "role": "field", "station_id": "DEMO-01"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
def test_demo_like_inject_and_transcripts(
    client, demo_auth_headers
) -> None:
    """Mirror run_radio_rx_injection_demo: inject messages, then GET /transcripts."""
    # Inject (queue only)
    r = client.post(
        "/inject/message",
        headers=demo_auth_headers,
        json={
            "text": "K5ABC de W1XYZ test 40m",
            "band": "40m",
            "source_callsign": "K5ABC",
            "destination_callsign": "W1XYZ",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True

    # Inject-and-store
    r2 = client.post(
        "/messages/inject-and-store",
        headers=demo_auth_headers,
        json={
            "text": "Stored inject demo",
            "band": "40m",
            "source_callsign": "K5ABC",
            "destination_callsign": "W1XYZ",
        },
    )
    assert r2.status_code == 200

    # Transcripts (may be 0 if DB not storing)
    r3 = client.get("/transcripts", headers=demo_auth_headers, params={"limit": 20})
    assert r3.status_code == 200
    out = r3.json()
    assert "count" in out
    assert "transcripts" in out


@pytest.mark.integration
def test_demo_like_relay_radio(
    client, demo_auth_headers
) -> None:
    """Mirror Option C relay (radio path): POST /messages/relay target_channel=radio."""
    body = {
        "message": "Demo relay 40m -> 2m",
        "source_band": "40m",
        "target_band": "2m",
        "source_callsign": "K5ABC",
        "destination_callsign": "W1XYZ",
        "target_channel": "radio",
    }
    r = client.post("/messages/relay", headers=demo_auth_headers, json=body)
    assert r.status_code == 200
    data = r.json()
    # With DB: source_transcript_id, relayed_transcript_id; without: relay may still return 200
    assert "relay" in data or "source_transcript_id" in data or "relayed_transcript_id" in data or data.get("relay") == "no_storage"


@pytest.mark.integration
def test_demo_like_callsign_register(
    client, demo_auth_headers
) -> None:
    """Mirror run_whitelist_flow_demo: POST /callsigns/register."""
    r = client.post(
        "/callsigns/register",
        headers=demo_auth_headers,
        json={"callsign": "FLABC-1", "source": "api"},
    )
    assert r.status_code == 200


@pytest.mark.integration
def test_demo_like_whitelist_request(
    client, demo_auth_headers
) -> None:
    """Mirror run_whitelist_flow_demo: POST /messages/whitelist-request (may 503 if no orchestrator)."""
    r = client.post(
        "/messages/whitelist-request",
        headers=demo_auth_headers,
        json={
            "text": "I am requesting to be whitelisted for cross band relay. Over.",
            "callsign": "FLABC-1",
        },
    )
    assert r.status_code in (200, 503)


@pytest.mark.integration
def test_demo_like_process(
    client, demo_auth_headers
) -> None:
    """Mirror run_orchestrator_judge_demo: POST /messages/process (may 503 if no orchestrator)."""
    r = client.post(
        "/messages/process",
        headers=demo_auth_headers,
        json={"message": "Hello, confirm you are online."},
    )
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        data = r.json()
        assert "success" in data
        assert "message" in data


@pytest.mark.integration
def test_demo_like_send_tts(
    client, demo_auth_headers
) -> None:
    """Mirror send-tts leg of voice-to-voice / Option C: POST /radio/send-tts (stub OK)."""
    r = client.post(
        "/radio/send-tts",
        headers=demo_auth_headers,
        json={
            "message": "RadioShaq demo TTS.",
            "frequency_hz": 145_520_000.0,
            "mode": "NFM",
        },
    )
    # 200 with success true/false, or 503 if radio_tx not available
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        data = r.json()
        assert "success" in data


@pytest.mark.integration
def test_demo_like_send_audio(
    client, demo_auth_headers
) -> None:
    """Mirror run_hackrf_tx_audio_demo: POST /radio/send-audio with a tiny WAV (stub OK)."""
    # Minimal WAV: 1 channel, 8 kHz, 0.1 s silence (bytes from a valid WAV header + data)
    wav_header = (
        b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80\x1f\x00\x00\x00\x3e\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    )
    r = client.post(
        "/radio/send-audio",
        headers=demo_auth_headers,
        files={"file": ("demo.wav", io.BytesIO(wav_header), "audio/wav")},
        data={"frequency_hz": "145520000", "mode": "NFM"},
    )
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        data = r.json()
        assert "success" in data


@pytest.mark.integration
def test_demo_like_from_audio(
    client, demo_auth_headers
) -> None:
    """Mirror Option C / voice-to-voice: POST /messages/from-audio with tiny WAV."""
    wav_header = (
        b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80\x1f\x00\x00\x00\x3e\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    )
    r = client.post(
        "/messages/from-audio",
        headers=demo_auth_headers,
        files={"file": ("tiny.wav", io.BytesIO(wav_header), "audio/wav")},
        data={
            "source_callsign": "K5ABC",
            "destination_callsign": "W1XYZ",
            "band": "40m",
            "mode": "NFM",
            "frequency_hz": "0",
            "inject": "true",
        },
    )
    # 200 with transcript_id; 400 if no speech; 422 validation; 503 if ASR unavailable
    assert r.status_code in (200, 400, 422, 503)
    if r.status_code == 200:
        data = r.json()
        assert "transcript_id" in data or "injected" in data
