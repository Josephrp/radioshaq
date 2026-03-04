"""Radio reception agent with ASR integration and human-in-the-loop controls."""

from __future__ import annotations

import asyncio
import tempfile
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from radioshaq.config.schema import (
    AudioActivationMode,
    AudioConfig,
    PendingResponse,
    PendingResponseStatus,
    ResponseMode,
    TriggerMatchMode,
)
from radioshaq.middleware.upstream import UpstreamEvent
from radioshaq.specialized.base import SpecializedAgent


class TriggerFilter:
    """Filters transcripts based on trigger phrases and callsign."""

    def __init__(self, config: AudioConfig) -> None:
        self.config = config

    def check(self, transcript: str, confidence: float) -> bool:
        """Return True if the message should be processed."""
        if not self.config.trigger_enabled:
            return True
        if confidence < self.config.trigger_min_confidence:
            return False
        transcript_lower = transcript.lower()
        if self.config.trigger_callsign:
            if self.config.trigger_callsign.lower() not in transcript_lower:
                return False
        if not self.config.trigger_phrases:
            return True
        for phrase in self.config.trigger_phrases:
            phrase_lower = phrase.lower()
            match self.config.trigger_match_mode:
                case TriggerMatchMode.EXACT:
                    if phrase_lower == transcript_lower:
                        return True
                case TriggerMatchMode.CONTAINS:
                    if phrase_lower in transcript_lower:
                        return True
                case TriggerMatchMode.STARTS_WITH:
                    if transcript_lower.startswith(phrase_lower):
                        return True
                case TriggerMatchMode.FUZZY:
                    try:
                        from rapidfuzz import fuzz
                        if fuzz.partial_ratio(phrase_lower, transcript_lower) >= 80:
                            return True
                    except ImportError:
                        pass
        return False


class ConfirmationManager:
    """Manages pending responses awaiting human confirmation."""

    def __init__(self, config: AudioConfig) -> None:
        self.config = config
        self._pending: dict[str, PendingResponse] = {}
        self._callbacks: list[Callable[[PendingResponse], Awaitable[None]]] = []
        self._lock = asyncio.Lock()

    def add_callback(
        self,
        callback: Callable[[PendingResponse], Awaitable[None]],
    ) -> None:
        self._callbacks.append(callback)

    async def create_pending(
        self,
        transcript: str,
        proposed_message: str,
        frequency_hz: float | None = None,
        mode: str | None = None,
        incoming_audio_path: str | None = None,
    ) -> PendingResponse:
        expires = datetime.now(timezone.utc) + timedelta(
            seconds=self.config.response_timeout_seconds
        )
        pending = PendingResponse(
            expires_at=expires,
            incoming_transcript=transcript,
            proposed_message=proposed_message,
            frequency_hz=frequency_hz,
            mode=mode,
            incoming_audio_path=incoming_audio_path,
        )
        async with self._lock:
            self._pending[pending.id] = pending
        await self._notify_change(pending)
        return pending

    async def approve(
        self, pending_id: str, operator: str | None = None
    ) -> PendingResponse | None:
        async with self._lock:
            if pending_id not in self._pending:
                return None
            pending = self._pending[pending_id]
            pending.status = PendingResponseStatus.APPROVED
            pending.responded_at = datetime.now(timezone.utc)
            pending.responded_by = operator
        await self._notify_change(pending)
        return pending

    async def reject(
        self,
        pending_id: str,
        operator: str | None = None,
        notes: str | None = None,
    ) -> PendingResponse | None:
        async with self._lock:
            if pending_id not in self._pending:
                return None
            pending = self._pending[pending_id]
            pending.status = PendingResponseStatus.REJECTED
            pending.responded_at = datetime.now(timezone.utc)
            pending.responded_by = operator
            pending.notes = notes
        await self._notify_change(pending)
        return pending

    async def get_pending(self, pending_id: str) -> PendingResponse | None:
        async with self._lock:
            return self._pending.get(pending_id)

    async def list_pending(self) -> list[PendingResponse]:
        async with self._lock:
            now = datetime.now(timezone.utc)
            for p in self._pending.values():
                if p.expires_at < now and p.status == PendingResponseStatus.PENDING:
                    p.status = PendingResponseStatus.EXPIRED
            return [
                p for p in self._pending.values()
                if p.status == PendingResponseStatus.PENDING
            ]

    async def _notify_change(self, pending: PendingResponse) -> None:
        for callback in self._callbacks:
            try:
                await callback(pending)
            except Exception as e:
                logger.warning("Confirmation callback error: %s", e)


class RadioAudioReceptionAgent(SpecializedAgent):
    """
    Radio reception agent with ASR integration, trigger filtering,
    and human-in-the-loop confirmation.
    """

    name = "radio_rx_audio"
    description = "Monitors radio audio with ASR, triggers, and human confirmation"
    capabilities = [
        "voice_monitoring",
        "speech_recognition",
        "audio_triggered_response",
        "human_in_the_loop",
    ]

    def __init__(
        self,
        config: AudioConfig,
        rig_manager: Any = None,
        capture_service: Any = None,
        stream_processor: Any = None,
        response_agent: Any = None,
        message_bus: Any = None,
        radio_config: Any = None,
        transcript_storage: Any = None,
    ) -> None:
        self.config = config
        self.rig_manager = rig_manager
        self.capture_service = capture_service
        self.stream_processor = stream_processor
        self.response_agent = response_agent
        self._message_bus = message_bus
        self._radio_config = radio_config
        self._transcript_storage = transcript_storage
        self._monitoring = False
        self._audio_activated = False  # Reset when monitoring starts/stops if audio_activation_enabled
        self._trigger_filter = TriggerFilter(config)
        self._confirmation_manager = ConfirmationManager(config)
        self._last_response_time: datetime | None = None
        self._cooldown_lock = asyncio.Lock()
        self._confirmation_task: asyncio.Task[None] | None = None
        self._whisper_model: Any = None
        # Current monitor context for bus metadata (set in _action_monitor)
        self._current_frequency: float | None = None
        self._current_band: str | None = None
        self._current_mode: str = "FM"

        if self.stream_processor:
            self.stream_processor.set_segment_callback(self._on_segment_ready)

    async def execute(
        self,
        task: dict[str, Any],
        upstream_callback: Callable[[UpstreamEvent], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        action = task.get("action", "monitor")
        if action == "monitor":
            return await self._action_monitor(task, upstream_callback)
        if action == "transcribe_file":
            return await self._action_transcribe_file(task, upstream_callback)
        if action == "approve_response":
            return await self._action_approve_response(task)
        if action == "reject_response":
            return await self._action_reject_response(task)
        if action == "list_pending":
            return await self._action_list_pending()
        if action == "get_pending":
            return await self._action_get_pending(task)
        return {"error": f"Unknown action: {action}"}

    async def _action_monitor(
        self,
        task: dict[str, Any],
        upstream_callback: Callable[[UpstreamEvent], Awaitable[None]] | None,
    ) -> dict[str, Any]:
        frequency = task.get("frequency")
        duration_seconds = int(task.get("duration_seconds", 300))
        mode = task.get("mode", "FM")

        if not self.capture_service or not self.stream_processor:
            return {"error": "Audio capture not configured", "frequency": frequency}

        if self.rig_manager and frequency is not None:
            await self.rig_manager.set_frequency(frequency)
            await self.rig_manager.set_mode(mode)

        # Set context for message bus metadata (band, frequency, mode)
        self._current_frequency = float(frequency) if frequency is not None else None
        self._current_mode = mode or "FM"
        if self._current_frequency and self._current_frequency > 0:
            from radioshaq.radio.bands import get_band_for_frequency
            self._current_band = get_band_for_frequency(self._current_frequency)
        else:
            rc = self._radio_config
            self._current_band = (
                getattr(rc, "default_band", None)
                or (getattr(rc, "listen_bands", None) or [None])[0]
            )

        self._monitoring = True
        self._confirmation_task = asyncio.create_task(
            self._confirmation_watcher(upstream_callback)
        )
        await self.emit_progress(
            upstream_callback, "monitoring_started", frequency=frequency, mode=mode
        )

        try:
            await self.capture_service.start()
            await asyncio.sleep(duration_seconds)
        finally:
            self._monitoring = False
            self._audio_activated = False
            self._current_frequency = None
            self._current_band = None
            await self.capture_service.stop()
            if self._confirmation_task and not self._confirmation_task.done():
                self._confirmation_task.cancel()
                try:
                    await self._confirmation_task
                except asyncio.CancelledError:
                    pass

        return {
            "frequency": frequency,
            "duration": duration_seconds,
            "mode": mode,
            "transcripts_captured": 0,
        }

    async def _on_segment_ready(self, segment: Any) -> None:
        if not self._monitoring:
            return
        from radioshaq.audio.stream_processor import ProcessedSegment
        if not isinstance(segment, ProcessedSegment):
            return
        if segment.snr_db is not None and segment.snr_db < self.config.min_snr_db:
            return
        transcript = await self._transcribe_segment(segment)
        if not transcript:
            return
        segment.transcript = transcript
        # Optional audio activation: require phrase before processing.
        if getattr(self.config, "audio_activation_enabled", False):
            phrase = getattr(self.config, "audio_activation_phrase", "radioshaq") or "radioshaq"
            mode = getattr(
                self.config, "audio_activation_mode", AudioActivationMode.SESSION
            ) or AudioActivationMode.SESSION
            if mode == AudioActivationMode.SESSION:
                if not self._audio_activated:
                    if phrase.lower() not in transcript.lower():
                        return
                    self._audio_activated = True
            else:
                # PER_MESSAGE: this segment must contain the phrase
                if phrase.lower() not in transcript.lower():
                    return
        confidence = getattr(segment, "transcript_confidence", None) or 0.8
        if not self._trigger_filter.check(transcript, confidence):
            return

        # Optionally store voice transcript (band, source=voice_listener) for GET /transcripts and relay
        if getattr(self._radio_config, "voice_store_transcript", False) and self._transcript_storage and getattr(self._transcript_storage, "_db", None):
            min_len = getattr(self._radio_config, "voice_store_min_length", 0) or 0
            keywords = getattr(self._radio_config, "voice_store_keywords", None) or []
            stripped = transcript.strip()
            if min_len > 0 and len(stripped) < min_len:
                pass  # skip store: too short
            elif keywords and not any(k.lower() in stripped.lower() for k in keywords if k):
                pass  # skip store: no keyword match
            else:
                try:
                    import uuid
                    source = (getattr(self.config, "voice_source_callsign_default", None) or "UNKNOWN").strip().upper()
                    session_id = f"voice-{self._current_band or 'unknown'}-{uuid.uuid4().hex[:8]}"
                    await self._transcript_storage.store(
                        session_id=session_id,
                        source_callsign=source,
                        frequency_hz=self._current_frequency or 0.0,
                        mode=self._current_mode,
                        transcript_text=transcript,
                        destination_callsign=None,
                        metadata={"band": self._current_band or "unknown", "source": "voice_listener"},
                    )
                except Exception as e:
                    logger.warning("Voice transcript store failed: %s", e)

        # Publish to MessageBus so orchestrator can process (default capture path)
        if getattr(self.config, "voice_publish_to_bus", True) and self._message_bus and hasattr(self._message_bus, "publish_inbound"):
            try:
                from radioshaq.orchestrator.radio_ingestion import radio_received_to_inbound
                source = (getattr(self.config, "voice_source_callsign_default", None) or "UNKNOWN").strip().upper()
                inbound = radio_received_to_inbound(
                    text=transcript,
                    band=self._current_band,
                    frequency_hz=self._current_frequency or 0.0,
                    source_callsign=source,
                    destination_callsign=None,
                    mode=self._current_mode,
                )
                ok = await self._message_bus.publish_inbound(inbound)
                if not ok:
                    logger.debug("Voice segment dropped (bus full)")
            except Exception as e:
                logger.warning("Voice publish_inbound failed: %s", e)

        response_text = await self._generate_response_text(transcript)
        if self.config.response_mode == ResponseMode.LISTEN_ONLY:
            self._maybe_reset_activation_per_message()
            return
        if self.config.response_mode == ResponseMode.CONFIRM_FIRST:
            await self._confirmation_manager.create_pending(
                transcript=transcript, proposed_message=response_text
            )
            self._maybe_reset_activation_per_message()
            return
        if self.config.response_mode == ResponseMode.AUTO_RESPOND:
            await self._send_response(response_text)
            self._maybe_reset_activation_per_message()

    async def _confirmation_watcher(
        self,
        upstream_callback: Callable[[UpstreamEvent], Awaitable[None]] | None,
    ) -> None:
        async def on_change(pending: PendingResponse) -> None:
            if pending.status == PendingResponseStatus.APPROVED:
                await self._send_response(pending.proposed_message)
                await self.emit_result(
                    upstream_callback,
                    {
                        "type": "response_sent_confirmed",
                        "pending_id": pending.id,
                        "response": pending.proposed_message,
                    },
                )

        self._confirmation_manager.add_callback(on_change)
        while self._monitoring:
            await asyncio.sleep(1)

    def _maybe_reset_activation_per_message(self) -> None:
        """In per-message mode, reset activation after processing a segment."""
        if not getattr(self.config, "audio_activation_enabled", False):
            return
        mode = getattr(
            self.config, "audio_activation_mode", AudioActivationMode.SESSION
        ) or AudioActivationMode.SESSION
        if mode == AudioActivationMode.PER_MESSAGE:
            self._audio_activated = False

    def _get_whisper_model(self) -> Any:
        """Load Whisper model once and cache for reuse."""
        if self._whisper_model is None:
            import whisper
            self._whisper_model = whisper.load_model("base")
        return self._whisper_model

    async def _transcribe_segment(self, segment: Any) -> str | None:
        try:
            import soundfile as sf
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                sf.write(f.name, segment.audio, segment.sample_rate)
                temp_path = f.name
            try:
                if self.config.asr_model == "voxtral":
                    from radioshaq.audio.asr import transcribe_audio_voxtral
                    out = transcribe_audio_voxtral(
                        temp_path, language=self.config.asr_language
                    )
                else:
                    model = self._get_whisper_model()
                    result = model.transcribe(temp_path)
                    out = result.get("text", "")
                return (out or "").strip() or None
            finally:
                Path(temp_path).unlink(missing_ok=True)
        except Exception as e:
            logger.exception("ASR failed: %s", e)
            return None

    async def _generate_response_text(self, incoming_message: str) -> str:
        return f"Acknowledged: {incoming_message[:50]}... Standing by."

    async def _send_response(self, message: str) -> bool:
        if not self.response_agent:
            return False
        # Responses to radio are always sent as audio (TTS) on radio out.
        task = {
            "transmission_type": "voice",
            "message": message,
            "use_tts": True,
        }
        try:
            result = await self.response_agent.execute(task)
            return result.get("success", False)
        except Exception as e:
            logger.exception("Response send failed: %s", e)
            return False

    async def _action_transcribe_file(
        self,
        task: dict[str, Any],
        upstream_callback: Callable[[UpstreamEvent], Awaitable[None]] | None,
    ) -> dict[str, Any]:
        audio_path = task.get("audio_path")
        if not audio_path:
            return {"error": "audio_path required"}
        await self.emit_progress(upstream_callback, "transcribing", audio_path=audio_path)
        try:
            if self.config.asr_model == "voxtral":
                from radioshaq.audio.asr import transcribe_audio_voxtral
                transcript = transcribe_audio_voxtral(
                    audio_path, language=self.config.asr_language
                )
            else:
                model = self._get_whisper_model()
                result = model.transcribe(audio_path)
                transcript = result.get("text", "").strip()
            await self.emit_result(
                upstream_callback,
                {"type": "transcription", "transcript": transcript, "audio_path": audio_path},
            )
            return {
                "transcript": transcript,
                "audio_path": audio_path,
                "model": self.config.asr_model,
            }
        except Exception as e:
            logger.exception("ASR failed: %s", e)
            await self.emit_error(upstream_callback, str(e))
            return {"error": str(e), "audio_path": audio_path}

    async def _action_approve_response(self, task: dict[str, Any]) -> dict[str, Any]:
        pending_id = task.get("pending_id")
        operator = task.get("operator")
        if not pending_id:
            return {"error": "pending_id required"}
        pending = await self._confirmation_manager.approve(pending_id, operator)
        if not pending:
            return {"error": "Pending response not found"}
        return {"success": True, "pending": pending.model_dump()}

    async def _action_reject_response(self, task: dict[str, Any]) -> dict[str, Any]:
        pending_id = task.get("pending_id")
        operator = task.get("operator")
        notes = task.get("notes")
        if not pending_id:
            return {"error": "pending_id required"}
        pending = await self._confirmation_manager.reject(pending_id, operator, notes)
        if not pending:
            return {"error": "Pending response not found"}
        return {"success": True, "pending": pending.model_dump()}

    async def _action_list_pending(self) -> dict[str, Any]:
        pending = await self._confirmation_manager.list_pending()
        return {
            "pending_responses": [p.model_dump() for p in pending],
            "count": len(pending),
        }

    async def _action_get_pending(self, task: dict[str, Any]) -> dict[str, Any]:
        pending_id = task.get("pending_id")
        pending = await self._confirmation_manager.get_pending(pending_id)
        if not pending:
            return {"error": "Not found"}
        return {"pending": pending.model_dump()}
