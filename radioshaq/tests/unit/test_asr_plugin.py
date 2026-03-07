"""Unit tests for ASR plugin: registry, transcribe_audio, backends."""

from __future__ import annotations

import pytest

from radioshaq.audio.asr_plugin import get_asr_backend, transcribe_audio


def test_get_asr_backend_voxtral_or_scribe():
    """At least one of voxtral or scribe is registered (scribe is always present)."""
    assert get_asr_backend("scribe") is not None


def test_get_asr_backend_unknown():
    """Unknown model_id returns None."""
    assert get_asr_backend("unknown_asr") is None


def test_transcribe_audio_unknown_model_raises(tmp_path):
    """transcribe_audio with unknown model_id raises RuntimeError."""
    (tmp_path / "fake.wav").write_bytes(b"fake")
    with pytest.raises(RuntimeError, match="not available"):
        transcribe_audio(str(tmp_path / "fake.wav"), model_id="nonexistent_asr")


def test_scribe_backend_requires_api_key(tmp_path):
    """Scribe backend raises when no API key."""
    (tmp_path / "a.wav").write_bytes(b"fake")
    b = get_asr_backend("scribe")
    assert b is not None
    with pytest.raises(RuntimeError, match="ELEVENLABS_API_KEY"):
        b.transcribe(str(tmp_path / "a.wav"))


def test_scribe_backend_transcribe_mock(tmp_path):
    """Scribe backend returns text when API key and mocked HTTP response."""
    from unittest.mock import MagicMock, patch
    (tmp_path / "a.wav").write_bytes(b"fake")
    mock_response = MagicMock()
    mock_response.json.return_value = {"text": "hello world"}
    mock_response.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.post.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    with patch("httpx.Client", return_value=mock_client):
        b = get_asr_backend("scribe")
        assert b is not None
        out = b.transcribe(str(tmp_path / "a.wav"), api_key="test_key")
        assert out == "hello world"
        mock_response.json.assert_called_once()
