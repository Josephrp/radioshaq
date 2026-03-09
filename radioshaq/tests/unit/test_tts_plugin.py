"""Unit tests for TTS plugin: registry, synthesize_speech, ElevenLabs and Kokoro backends."""

from __future__ import annotations

import sys
import types
from unittest.mock import patch

import pytest

from radioshaq.audio.tts_plugin import get_tts_backend, register_tts_backend, synthesize_speech


def test_get_tts_backend_elevenlabs():
    """ElevenLabs backend is registered."""
    b = get_tts_backend("elevenlabs")
    assert b is not None


def test_get_tts_backend_unknown():
    """Unknown provider returns None."""
    assert get_tts_backend("unknown_provider") is None


def test_synthesize_speech_unknown_provider_raises():
    """synthesize_speech with unknown provider raises RuntimeError."""
    with pytest.raises(RuntimeError, match="not available"):
        synthesize_speech("hello", "nonexistent_provider")


def test_elevenlabs_backend_requires_api_key():
    """ElevenLabs backend raises when no API key."""
    b = get_tts_backend("elevenlabs")
    assert b is not None
    with pytest.raises(RuntimeError, match="ELEVENLABS_API_KEY"):
        b.synthesize("hello")


def test_elevenlabs_backend_synthesize():
    """ElevenLabs backend returns bytes when API key and mocked HTTP response."""
    from unittest.mock import MagicMock, patch
    mock_response = MagicMock()
    mock_response.content = b"fake_mp3_bytes"
    mock_response.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.post.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    with patch("httpx.Client", return_value=mock_client):
        b = get_tts_backend("elevenlabs")
        assert b is not None
        out = b.synthesize("hello", api_key="test_key")
        assert out == b"fake_mp3_bytes"


def test_kokoro_backend_optional():
    """Kokoro backend may or may not be registered (optional extra)."""
    b = get_tts_backend("kokoro")
    if b is not None:
        with pytest.raises((RuntimeError, Exception)):
            b.synthesize("hello")  # may fail without kokoro deps or with empty text edge case
    # If kokoro not installed, backend is simply not registered
    assert get_tts_backend("elevenlabs") is not None


def test_kokoro_backend_raises_helpful_message_when_kokoro_not_installed():
    """Kokoro backend raises RuntimeError mentioning tts_kokoro when kokoro is not importable."""
    from radioshaq.audio.tts_plugin.backends.kokoro import KokoroTTSBackend

    kokoro_mod = types.ModuleType("kokoro")

    def getattr_raiser(name: str):
        raise ImportError("No module named 'kokoro'")

    kokoro_mod.__getattr__ = getattr_raiser
    with patch.dict(sys.modules, {"kokoro": kokoro_mod}):
        backend = KokoroTTSBackend()
        with pytest.raises(RuntimeError) as exc_info:
            backend.synthesize("hi")
    assert "tts_kokoro" in str(exc_info.value).lower()


def test_kokoro_backend_raises_helpful_message_when_soundfile_not_installed():
    """Kokoro backend raises RuntimeError mentioning soundfile when soundfile is not importable."""
    import numpy as np

    from radioshaq.audio.tts_plugin.backends.kokoro import KokoroTTSBackend

    kokoro_mod = types.ModuleType("kokoro")

    class MockKPipeline:
        def __init__(self, lang_code: str = "a") -> None:
            pass

        def __call__(self, text: str, voice: str = "af_heart", speed: float = 1.0, split_pattern: str = ""):
            yield (None, None, np.zeros(24000, dtype=np.float32))

    kokoro_mod.KPipeline = MockKPipeline
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object):
        if name == "soundfile":
            raise ImportError("No module named 'soundfile'")
        return real_import(name, *args, **kwargs)

    with patch.dict(sys.modules, {"kokoro": kokoro_mod}), patch(
        "builtins.__import__", side_effect=fake_import
    ):
        backend = KokoroTTSBackend()
        with pytest.raises(RuntimeError) as exc_info:
            backend.synthesize("hi")
    assert "soundfile" in str(exc_info.value).lower() or "tts_kokoro" in str(exc_info.value).lower()
