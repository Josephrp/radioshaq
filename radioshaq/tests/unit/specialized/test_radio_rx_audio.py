"""Tests for RadioAudioReceptionAgent."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from radioshaq.config.schema import (
    AudioActivationMode,
    AudioConfig,
    ResponseMode,
    TriggerMatchMode,
)
from radioshaq.specialized.radio_rx_audio import (
    ConfirmationManager,
    RadioAudioReceptionAgent,
    TriggerFilter,
)


class _FakeProcessedSegment:
    """Minimal segment-like object to avoid importing stream_processor (heavy deps)."""

    def __init__(self, snr_db: float = 10.0) -> None:
        self.audio = b""
        self.sample_rate = 16000
        self.snr_db = snr_db
        self.transcript = None


def test_audio_config_default_activation_mode_is_session() -> None:
    """Default audio_activation_mode is SESSION for backward compatibility."""
    config = AudioConfig()
    assert config.audio_activation_mode == AudioActivationMode.SESSION


def test_audio_config_load_per_message_from_dict() -> None:
    """Loading from dict/YAML with audio_activation_mode string parses to enum."""
    config = AudioConfig(**{"audio_activation_mode": "per_message"})
    assert config.audio_activation_mode == AudioActivationMode.PER_MESSAGE
    config2 = AudioConfig(**{"audio_activation_mode": "session"})
    assert config2.audio_activation_mode == AudioActivationMode.SESSION


def test_trigger_filter_disabled() -> None:
    config = AudioConfig(trigger_enabled=False)
    f = TriggerFilter(config)
    assert f.check("any text", 0.5) is True


def test_trigger_filter_confidence_reject() -> None:
    config = AudioConfig(trigger_enabled=True, trigger_min_confidence=0.9)
    f = TriggerFilter(config)
    assert f.check("radioshaq here", 0.5) is False


def test_trigger_filter_contains() -> None:
    config = AudioConfig(
        trigger_enabled=True,
        trigger_phrases=["radioshaq"],
        trigger_match_mode=TriggerMatchMode.CONTAINS,
    )
    f = TriggerFilter(config)
    assert f.check("this is radioshaq calling", 0.8) is True
    assert f.check("hello world", 0.8) is False


@pytest.mark.asyncio
async def test_confirmation_manager_create_and_list() -> None:
    config = AudioConfig(response_timeout_seconds=30.0)
    mgr = ConfirmationManager(config)
    pending = await mgr.create_pending(
        transcript="incoming",
        proposed_message="Ack",
    )
    assert pending.id
    assert pending.status.value == "pending"
    listed = await mgr.list_pending()
    assert len(listed) == 1
    assert listed[0].id == pending.id


@pytest.mark.asyncio
async def test_radio_rx_audio_unknown_action() -> None:
    config = AudioConfig()
    agent = RadioAudioReceptionAgent(config=config)
    result = await agent.execute({"action": "unknown"})
    assert "error" in result
    assert "Unknown action" in result["error"]


@pytest.mark.asyncio
async def test_radio_rx_audio_monitor_no_capture() -> None:
    config = AudioConfig()
    agent = RadioAudioReceptionAgent(config=config, capture_service=None)
    result = await agent.execute({
        "action": "monitor",
        "frequency": 146520000,
        "duration_seconds": 1,
    })
    assert "error" in result
    assert "Audio capture not configured" in result["error"]


@pytest.mark.asyncio
async def test_radio_rx_audio_transcribe_file_no_path() -> None:
    config = AudioConfig()
    agent = RadioAudioReceptionAgent(config=config)
    result = await agent.execute({"action": "transcribe_file"})
    assert "error" in result
    assert "audio_path" in result["error"]


def _make_segment(snr_db: float = 10.0) -> _FakeProcessedSegment:
    return _FakeProcessedSegment(snr_db=snr_db)


@pytest.mark.asyncio
async def test_audio_activation_session_mode() -> None:
    """Session mode: once phrase is heard, subsequent segments are processed without phrase."""
    config = AudioConfig(
        audio_activation_enabled=True,
        audio_activation_mode=AudioActivationMode.SESSION,
        audio_activation_phrase="radioshaq",
        trigger_enabled=False,
        response_mode=ResponseMode.LISTEN_ONLY,
        min_snr_db=0.0,
    )
    agent = RadioAudioReceptionAgent(config=config, stream_processor=MagicMock())
    agent._monitoring = True
    segment = _make_segment()
    with patch("radioshaq.audio.stream_processor.ProcessedSegment", _FakeProcessedSegment):
        with patch.object(agent, "_transcribe_segment", new_callable=AsyncMock) as m_transcribe:
            m_transcribe.return_value = "hello world"
            await agent._on_segment_ready(segment)
    assert agent._audio_activated is False  # no phrase, dropped

    with patch("radioshaq.audio.stream_processor.ProcessedSegment", _FakeProcessedSegment):
        with patch.object(agent, "_transcribe_segment", new_callable=AsyncMock) as m_transcribe:
            m_transcribe.return_value = "radioshaq copy"
            await agent._on_segment_ready(segment)
    assert agent._audio_activated is True  # phrase heard, session active

    with patch("radioshaq.audio.stream_processor.ProcessedSegment", _FakeProcessedSegment):
        with patch.object(agent, "_transcribe_segment", new_callable=AsyncMock) as m_transcribe:
            m_transcribe.return_value = "any other message"
            await agent._on_segment_ready(segment)
    assert agent._audio_activated is True  # still active for session


@pytest.mark.asyncio
async def test_audio_activation_per_message_mode() -> None:
    """Per-message mode: each processed segment must contain the phrase; activation resets after process."""
    config = AudioConfig(
        audio_activation_enabled=True,
        audio_activation_mode=AudioActivationMode.PER_MESSAGE,
        audio_activation_phrase="radioshaq",
        trigger_enabled=False,
        response_mode=ResponseMode.LISTEN_ONLY,
        min_snr_db=0.0,
    )
    agent = RadioAudioReceptionAgent(config=config, stream_processor=MagicMock())
    agent._monitoring = True
    segment = _make_segment()

    with patch("radioshaq.audio.stream_processor.ProcessedSegment", _FakeProcessedSegment):
        with patch.object(agent, "_transcribe_segment", new_callable=AsyncMock) as m_transcribe:
            m_transcribe.return_value = "no phrase here"
            await agent._on_segment_ready(segment)
    assert agent._audio_activated is False  # dropped, never activated

    with patch("radioshaq.audio.stream_processor.ProcessedSegment", _FakeProcessedSegment):
        with patch.object(agent, "_transcribe_segment", new_callable=AsyncMock) as m_transcribe:
            m_transcribe.return_value = "radioshaq go"
            await agent._on_segment_ready(segment)
    assert agent._audio_activated is False  # processed then reset in per_message mode

    with patch("radioshaq.audio.stream_processor.ProcessedSegment", _FakeProcessedSegment):
        with patch.object(agent, "_transcribe_segment", new_callable=AsyncMock) as m_transcribe:
            m_transcribe.return_value = "no phrase again"
            await agent._on_segment_ready(segment)
    assert agent._audio_activated is False  # segment dropped (no phrase)

    with patch("radioshaq.audio.stream_processor.ProcessedSegment", _FakeProcessedSegment):
        with patch.object(agent, "_transcribe_segment", new_callable=AsyncMock) as m_transcribe:
            m_transcribe.return_value = "radioshaq second time"
            await agent._on_segment_ready(segment)
    assert agent._audio_activated is False  # processed and reset again


@pytest.mark.asyncio
async def test_audio_activation_per_message_confirm_first_reset() -> None:
    """Per-message mode with CONFIRM_FIRST: activation resets after create_pending."""
    config = AudioConfig(
        audio_activation_enabled=True,
        audio_activation_mode=AudioActivationMode.PER_MESSAGE,
        audio_activation_phrase="radioshaq",
        trigger_enabled=False,
        response_mode=ResponseMode.CONFIRM_FIRST,
        min_snr_db=0.0,
    )
    agent = RadioAudioReceptionAgent(config=config, stream_processor=MagicMock())
    agent._monitoring = True
    segment = _make_segment()
    with patch("radioshaq.audio.stream_processor.ProcessedSegment", _FakeProcessedSegment):
        with patch.object(agent, "_transcribe_segment", new_callable=AsyncMock) as m_transcribe:
            m_transcribe.return_value = "radioshaq request"
            await agent._on_segment_ready(segment)
    assert agent._audio_activated is False
    pending = await agent._confirmation_manager.list_pending()
    assert len(pending) == 1


@pytest.mark.asyncio
async def test_voice_store_min_length_skips_short_transcript() -> None:
    """When voice_store_transcript and voice_store_min_length=10, short transcript is not stored."""
    config = AudioConfig(trigger_enabled=False, min_snr_db=0.0)
    radio_config = MagicMock()
    radio_config.voice_store_transcript = True
    radio_config.voice_store_min_length = 10
    radio_config.voice_store_keywords = None
    storage = MagicMock(_db=MagicMock())
    storage.store = AsyncMock(return_value=1)
    agent = RadioAudioReceptionAgent(
        config=config,
        stream_processor=MagicMock(),
        radio_config=radio_config,
        transcript_storage=storage,
    )
    agent._monitoring = True
    agent._current_band = "40m"
    agent._current_frequency = 7.1e6
    agent._current_mode = "SSB"
    segment = _make_segment()
    with patch("radioshaq.audio.stream_processor.ProcessedSegment", _FakeProcessedSegment):
        with patch.object(agent, "_transcribe_segment", new_callable=AsyncMock) as m_transcribe:
            m_transcribe.return_value = "short"
            await agent._on_segment_ready(segment)
    assert storage.store.await_count == 0


@pytest.mark.asyncio
async def test_voice_store_min_length_stores_long_enough_transcript() -> None:
    """When voice_store_min_length=10, transcript of length >= 10 is stored."""
    config = AudioConfig(trigger_enabled=False, min_snr_db=0.0)
    radio_config = MagicMock()
    radio_config.voice_store_transcript = True
    radio_config.voice_store_min_length = 10
    radio_config.voice_store_keywords = None
    storage = MagicMock(_db=MagicMock())
    storage.store = AsyncMock(return_value=1)
    agent = RadioAudioReceptionAgent(
        config=config,
        stream_processor=MagicMock(),
        radio_config=radio_config,
        transcript_storage=storage,
    )
    agent._monitoring = True
    agent._current_band = "40m"
    agent._current_frequency = 7.1e6
    agent._current_mode = "SSB"
    segment = _make_segment()
    with patch("radioshaq.audio.stream_processor.ProcessedSegment", _FakeProcessedSegment):
        with patch.object(agent, "_transcribe_segment", new_callable=AsyncMock) as m_transcribe:
            m_transcribe.return_value = "this is long enough"
            await agent._on_segment_ready(segment)
    assert storage.store.await_count == 1


@pytest.mark.asyncio
async def test_voice_store_keywords_skips_when_no_match() -> None:
    """When voice_store_keywords is set, transcript without keyword is not stored."""
    config = AudioConfig(trigger_enabled=False, min_snr_db=0.0)
    radio_config = MagicMock()
    radio_config.voice_store_transcript = True
    radio_config.voice_store_min_length = 0
    radio_config.voice_store_keywords = ["relay", "copy"]
    storage = MagicMock(_db=MagicMock())
    storage.store = AsyncMock(return_value=1)
    agent = RadioAudioReceptionAgent(
        config=config,
        stream_processor=MagicMock(),
        radio_config=radio_config,
        transcript_storage=storage,
    )
    agent._monitoring = True
    agent._current_band = "40m"
    agent._current_frequency = 7.1e6
    agent._current_mode = "SSB"
    segment = _make_segment()
    with patch("radioshaq.audio.stream_processor.ProcessedSegment", _FakeProcessedSegment):
        with patch.object(agent, "_transcribe_segment", new_callable=AsyncMock) as m_transcribe:
            m_transcribe.return_value = "hello world nothing special"
            await agent._on_segment_ready(segment)
    assert storage.store.await_count == 0


@pytest.mark.asyncio
async def test_voice_store_keywords_stores_when_match() -> None:
    """When voice_store_keywords is set, transcript containing keyword is stored."""
    config = AudioConfig(trigger_enabled=False, min_snr_db=0.0)
    radio_config = MagicMock()
    radio_config.voice_store_transcript = True
    radio_config.voice_store_min_length = 0
    radio_config.voice_store_keywords = ["relay"]
    storage = MagicMock(_db=MagicMock())
    storage.store = AsyncMock(return_value=1)
    agent = RadioAudioReceptionAgent(
        config=config,
        stream_processor=MagicMock(),
        radio_config=radio_config,
        transcript_storage=storage,
    )
    agent._monitoring = True
    agent._current_band = "40m"
    agent._current_frequency = 7.1e6
    agent._current_mode = "SSB"
    segment = _make_segment()
    with patch("radioshaq.audio.stream_processor.ProcessedSegment", _FakeProcessedSegment):
        with patch.object(agent, "_transcribe_segment", new_callable=AsyncMock) as m_transcribe:
            m_transcribe.return_value = "please relay this to 2m"
            await agent._on_segment_ready(segment)
    assert storage.store.await_count == 1


@pytest.mark.asyncio
async def test_confirm_timeout_creates_pending_without_immediate_send() -> None:
    """CONFIRM_TIMEOUT queues pending response first; timeout handler sends later."""
    config = AudioConfig(
        trigger_enabled=False,
        min_snr_db=0.0,
        response_mode=ResponseMode.CONFIRM_TIMEOUT,
    )
    response_agent = MagicMock()
    response_agent.execute = AsyncMock(return_value={"success": True})
    agent = RadioAudioReceptionAgent(
        config=config,
        stream_processor=MagicMock(),
        response_agent=response_agent,
    )
    agent._monitoring = True
    segment = _make_segment()
    with patch("radioshaq.audio.stream_processor.ProcessedSegment", _FakeProcessedSegment):
        with patch.object(agent, "_transcribe_segment", new_callable=AsyncMock) as m_transcribe:
            m_transcribe.return_value = "radioshaq status check"
            await agent._on_segment_ready(segment)
    pending = await agent._confirmation_manager.list_pending()
    assert len(pending) == 1
    response_agent.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirm_timeout_auto_sends_expired_pending_with_frequency_and_mode() -> None:
    """Expired pending response in CONFIRM_TIMEOUT is auto-sent over voice TX with original freq/mode."""
    config = AudioConfig(
        trigger_enabled=False,
        min_snr_db=0.0,
        response_mode=ResponseMode.CONFIRM_TIMEOUT,
    )
    response_agent = MagicMock()
    response_agent.execute = AsyncMock(return_value={"success": True})
    agent = RadioAudioReceptionAgent(config=config, response_agent=response_agent)
    pending = await agent._confirmation_manager.create_pending(
        transcript="incoming",
        proposed_message="Ack timeout",
        frequency_hz=145_550_000.0,
        mode="FM",
    )
    pending.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    await agent._handle_pending_timeouts()

    response_agent.execute.assert_awaited_once()
    sent_task = response_agent.execute.await_args.args[0]
    assert sent_task.get("transmission_type") == "voice"
    assert sent_task.get("use_tts") is True
    assert sent_task.get("frequency") == 145_550_000.0
    assert sent_task.get("mode") == "FM"
    pending_after = await agent._confirmation_manager.get_pending(pending.id)
    assert pending_after is not None
    assert pending_after.status.value == "auto_sent"
