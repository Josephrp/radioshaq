"""Transcript storage: store, search, and retrieve radio transcripts.

Delegates to PostGISManager when available; provides a single interface
for the API and orchestrator.
"""

from __future__ import annotations

from typing import Any, Protocol


class TranscriptStoreProtocol(Protocol):
    """Protocol for transcript storage backends."""

    async def store_transcript(
        self,
        session_id: str,
        source_callsign: str,
        frequency_hz: float,
        mode: str,
        transcript_text: str,
        destination_callsign: str | None = None,
        signal_quality: float | None = None,
        operator_location_id: int | None = None,
        metadata: dict | None = None,
        raw_audio_path: str | None = None,
    ) -> int:
        ...
    async def search_transcripts(
        self,
        callsign: str | None = None,
        frequency_min: float | None = None,
        frequency_max: float | None = None,
        mode: str | None = None,
        since: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        ...


class TranscriptStorage:
    """
    Transcript storage facade.
    Wraps PostGISManager (or any TranscriptStoreProtocol) for store and search.
    """

    def __init__(self, db: TranscriptStoreProtocol | None = None):
        self._db = db

    async def store(
        self,
        session_id: str,
        source_callsign: str,
        frequency_hz: float,
        mode: str,
        transcript_text: str,
        destination_callsign: str | None = None,
        signal_quality: float | None = None,
        operator_location_id: int | None = None,
        metadata: dict | None = None,
        raw_audio_path: str | None = None,
    ) -> int:
        """Store a transcript. Returns record ID or 0 if no backend."""
        if not self._db:
            return 0
        return await self._db.store_transcript(
            session_id=session_id,
            source_callsign=source_callsign,
            frequency_hz=frequency_hz,
            mode=mode,
            transcript_text=transcript_text,
            destination_callsign=destination_callsign,
            signal_quality=signal_quality,
            operator_location_id=operator_location_id,
            metadata=metadata,
            raw_audio_path=raw_audio_path,
        )

    async def search(
        self,
        callsign: str | None = None,
        frequency_min: float | None = None,
        frequency_max: float | None = None,
        mode: str | None = None,
        since: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Search transcripts. Returns empty list if no backend."""
        if not self._db:
            return []
        return await self._db.search_transcripts(
            callsign=callsign,
            frequency_min=frequency_min,
            frequency_max=frequency_max,
            mode=mode,
            since=since,
            limit=limit,
        )
