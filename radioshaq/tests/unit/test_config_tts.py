"""Unit tests for TTS config schema (TTSConfig and Config.tts)."""

from __future__ import annotations

import pytest

from radioshaq.config.schema import Config, TTSConfig


def test_tts_config_has_provider_and_backend_fields():
    """TTSConfig includes provider and all elevenlabs/kokoro options."""
    t = TTSConfig()
    assert t.provider == "elevenlabs"
    assert t.elevenlabs_voice_id == "21m00Tcm4TlvDq8ikWAM"
    assert t.elevenlabs_model_id == "eleven_multilingual_v2"
    assert t.elevenlabs_output_format == "mp3_44100_128"
    assert t.kokoro_voice == "af_heart"
    assert t.kokoro_lang_code == "a"
    assert t.kokoro_speed == 1.0


def test_tts_config_accepts_kokoro_provider():
    """TTSConfig accepts provider='kokoro'."""
    t = TTSConfig(provider="kokoro")
    assert t.provider == "kokoro"


def test_config_has_tts_section():
    """Top-level Config has tts with TTSConfig defaults."""
    # Load minimal config (no file) so tts gets default
    cfg = Config()
    assert hasattr(cfg, "tts")
    assert isinstance(cfg.tts, TTSConfig)
    assert cfg.tts.provider in ("elevenlabs", "kokoro")
