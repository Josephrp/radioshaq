"""Unit tests for callsigns, messages/from-audio, messages/inject-and-store, transcripts by id/play, radio/send-tts."""

from __future__ import annotations

import io
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import pytest

from fastapi.testclient import TestClient


# ----- Auth required -----


@pytest.mark.unit
def test_callsigns_list_requires_auth(client: TestClient) -> None:
    r = client.get("/callsigns")
    assert r.status_code == 401


@pytest.mark.unit
def test_callsigns_register_requires_auth(client: TestClient) -> None:
    r = client.post("/callsigns/register", json={"callsign": "K5ABC", "source": "api"})
    assert r.status_code == 401


@pytest.mark.unit
def test_callsigns_unregister_requires_auth(client: TestClient) -> None:
    r = client.delete("/callsigns/registered/K5ABC")
    assert r.status_code == 401


@pytest.mark.unit
def test_messages_from_audio_requires_auth(client: TestClient) -> None:
    r = client.post(
        "/messages/from-audio",
        data={"source_callsign": "K5ABC", "inject": "false"},
        files={"file": ("x.wav", io.BytesIO(b"\x00" * 100), "audio/wav")},
    )
    assert r.status_code == 401


@pytest.mark.unit
def test_messages_inject_and_store_requires_auth(client: TestClient) -> None:
    r = client.post("/messages/inject-and-store", json={"text": "hello", "source_callsign": "K5ABC"})
    assert r.status_code == 401


@pytest.mark.unit
def test_transcripts_by_id_requires_auth(client: TestClient) -> None:
    r = client.get("/transcripts/1")
    assert r.status_code == 401


@pytest.mark.unit
def test_transcripts_play_requires_auth(client: TestClient) -> None:
    r = client.post("/transcripts/1/play")
    assert r.status_code == 401


@pytest.mark.unit
def test_radio_send_tts_requires_auth(client: TestClient) -> None:
    r = client.post("/radio/send-tts", json={"message": "test"})
    assert r.status_code == 401


@pytest.mark.unit
def test_whitelist_request_requires_auth(client: TestClient) -> None:
    """POST /messages/whitelist-request without token returns 401."""
    r = client.post(
        "/messages/whitelist-request",
        json={"text": "I need access for messaging between bands.", "callsign": "K5ABC"},
    )
    assert r.status_code == 401


# ----- Callsigns (with auth) -----


@pytest.mark.unit
def test_callsigns_list_with_auth_returns_200(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    r = client.get("/callsigns", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "registered" in data
    assert "count" in data
    assert isinstance(data["registered"], list)


@pytest.mark.unit
def test_callsigns_register_invalid_callsign_returns_4xx(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    r = client.post(
        "/callsigns/register",
        headers=auth_headers,
        json={"callsign": "X", "source": "api"},
    )
    assert r.status_code in (400, 422)


@pytest.mark.unit
def test_callsigns_register_valid_returns_ok_or_503(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    r = client.post(
        "/callsigns/register",
        headers=auth_headers,
        json={"callsign": "K5ABC", "source": "api"},
    )
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        assert r.json().get("ok") is True
        assert r.json().get("callsign") == "K5ABC"
    else:
        assert "not available" in r.json().get("detail", "").lower() or "database" in r.json().get("detail", "").lower()


@pytest.mark.unit
def test_callsigns_unregister_returns_503_or_404(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    r = client.delete("/callsigns/registered/K5ABC", headers=auth_headers)
    assert r.status_code in (503, 404)


# ----- Messages inject-and-store (with auth) -----


@pytest.mark.unit
def test_messages_inject_and_store_with_auth_returns_200(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    r = client.post(
        "/messages/inject-and-store",
        headers=auth_headers,
        json={
            "text": "test message",
            "source_callsign": "K5ABC",
            "band": "40m",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert "qsize" in data


# ----- Transcripts (with auth) -----


@pytest.mark.unit
def test_transcripts_search_with_auth_returns_200(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    r = client.get("/transcripts", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "transcripts" in data
    assert "count" in data


@pytest.mark.unit
def test_transcripts_search_accepts_band_and_destination_only(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """GET /transcripts with band and destination_only returns 200 and response shape."""
    r = client.get(
        "/transcripts",
        headers=auth_headers,
        params={"callsign": "W1XYZ", "band": "2m", "destination_only": "true"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "transcripts" in data
    assert "count" in data
    assert isinstance(data["transcripts"], list)
    assert isinstance(data["count"], int)


@pytest.mark.unit
def test_transcripts_get_by_id_no_db_returns_503(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    r = client.get("/transcripts/1", headers=auth_headers)
    assert r.status_code in (503, 404)


@pytest.mark.unit
def test_transcripts_play_no_db_or_no_agent_returns_503_or_404(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    r = client.post("/transcripts/1/play", headers=auth_headers)
    assert r.status_code in (503, 404)


# ----- Receiver upload -----


@pytest.mark.unit
def test_receiver_upload_requires_auth(client: TestClient) -> None:
    """POST /receiver/upload without token returns 401."""
    r = client.post(
        "/receiver/upload",
        json={
            "station_id": "RECV1",
            "operator_id": "op1",
            "timestamp": "2026-03-04T12:00:00Z",
            "frequency_hz": 7.15e6,
            "signal_strength_db": -10.0,
            "decoded_text": "test",
            "mode": "FM",
        },
    )
    assert r.status_code == 401


@pytest.mark.unit
def test_receiver_upload_with_auth_returns_200(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """POST /receiver/upload with auth returns 200 and status ok (store/inject depend on config)."""
    r = client.post(
        "/receiver/upload",
        headers=auth_headers,
        json={
            "station_id": "RECV1",
            "operator_id": "op1",
            "timestamp": "2026-03-04T12:00:00Z",
            "frequency_hz": 7.15e6,
            "signal_strength_db": -10.0,
            "decoded_text": "hello 40m",
            "mode": "FM",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"
    assert data.get("received") == "RECV1"


# ----- Radio send-tts (with auth) -----


@pytest.mark.unit
def test_radio_send_tts_without_agent_or_on_failure_returns_5xx(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    r = client.post(
        "/radio/send-tts",
        headers=auth_headers,
        json={"message": "hello"},
    )
    assert r.status_code in (503, 500)


@pytest.mark.unit
def test_radio_send_tts_passes_frequency_to_radio_tx(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """POST /radio/send-tts forwards frequency_hz as radio_tx 'frequency' task field."""
    app = client.app
    old_registry = getattr(app.state, "agent_registry", None)

    tx = MagicMock()
    tx.execute = AsyncMock(return_value={"success": True})

    class _Registry:
        def get_agent(self, name: str):
            return tx if name == "radio_tx" else None

    app.state.agent_registry = _Registry()
    try:
        r = client.post(
            "/radio/send-tts",
            headers=auth_headers,
            json={"message": "hello", "frequency_hz": 145550000.0, "mode": "FM"},
        )
        assert r.status_code == 200
        tx.execute.assert_awaited_once()
        sent_task = tx.execute.await_args.args[0]
        assert sent_task.get("frequency") == 145550000.0
        assert sent_task.get("mode") == "FM"
    finally:
        app.state.agent_registry = old_registry


# ----- Messages from-audio (validation only with auth) -----


@pytest.mark.unit
def test_messages_from_audio_rejects_non_audio_with_auth(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    r = client.post(
        "/messages/from-audio",
        headers=auth_headers,
        data={"source_callsign": "K5ABC", "inject": "false"},
        files={"file": ("x.txt", io.BytesIO(b"not audio"), "text/plain")},
    )
    assert r.status_code == 400
    assert "audio" in r.json().get("detail", "").lower()


@pytest.mark.unit
def test_messages_from_audio_missing_source_callsign_returns_422(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    r = client.post(
        "/messages/from-audio",
        headers=auth_headers,
        data={"inject": "false"},
        files={"file": ("x.wav", io.BytesIO(b"\x00" * 100), "audio/wav")},
    )
    assert r.status_code == 422


# ----- Whitelist request (with auth) -----


@pytest.mark.unit
def test_whitelist_request_missing_text_returns_400(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """POST /messages/whitelist-request with empty body or no text/message returns 400."""
    r = client.post(
        "/messages/whitelist-request",
        headers=auth_headers,
        json={},
    )
    assert r.status_code == 400
    assert "text" in r.json().get("detail", "").lower() or "required" in r.json().get("detail", "").lower()


@pytest.mark.unit
def test_whitelist_request_invalid_content_type_returns_400(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """POST /messages/whitelist-request with unsupported Content-Type returns 400."""
    r = client.post(
        "/messages/whitelist-request",
        headers={**auth_headers, "Content-Type": "text/plain"},
        content="just raw text",
    )
    assert r.status_code == 400
    assert "content-type" in r.json().get("detail", "").lower() or "application/json" in r.json().get("detail", "").lower()


@pytest.mark.unit
def test_whitelist_request_json_with_auth_returns_200_or_503(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """POST /messages/whitelist-request with valid JSON returns 200 (or 503 if orchestrator unavailable)."""
    r = client.post(
        "/messages/whitelist-request",
        headers=auth_headers,
        json={
            "text": "I need access for messaging between bands.",
            "callsign": "K5ABC",
            "send_audio_back": False,
        },
    )
    assert r.status_code in (200, 503)
    data = r.json()
    if r.status_code == 200:
        assert "success" in data
        assert "message" in data
        assert "task_id" in data
        assert "approved" in data
        assert "audio_sent" in data
    else:
        assert "orchestrator" in data.get("detail", "").lower() or "not available" in data.get("detail", "").lower()


@pytest.mark.unit
def test_whitelist_request_send_audio_back_includes_frequency_and_mode(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Whitelist request uses provided frequency_hz/mode when sending TTS over radio."""
    app = client.app
    old_orchestrator = getattr(app.state, "orchestrator", None)
    old_registry = getattr(app.state, "agent_registry", None)

    class _Orchestrator:
        async def process_request(self, request: str, callsign: str | None = None):
            return SimpleNamespace(
                success=True,
                message="Approved. You are registered.",
                state=SimpleNamespace(task_id="t-1", completed_tasks=[]),
            )

    tx = MagicMock()
    tx.execute = AsyncMock(return_value={"success": True})

    class _Registry:
        def get_agent(self, name: str):
            return tx if name == "radio_tx" else None

    app.state.orchestrator = _Orchestrator()
    app.state.agent_registry = _Registry()

    try:
        r = client.post(
            "/messages/whitelist-request",
            headers=auth_headers,
            json={
                "text": "please whitelist me",
                "callsign": "K5ABC",
                "send_audio_back": True,
                "frequency_hz": 146520000.0,
                "mode": "FM",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("audio_sent") is True
        tx.execute.assert_awaited_once()
        sent_task = tx.execute.await_args.args[0]
        assert sent_task.get("frequency") == 146520000.0
        assert sent_task.get("mode") == "FM"
    finally:
        app.state.orchestrator = old_orchestrator
        app.state.agent_registry = old_registry
