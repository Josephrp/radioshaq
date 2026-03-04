"""Unit tests for transcript storage retention (delete_transcripts_older_than)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("boto3", reason="radioshaq.database package requires boto3")
from radioshaq.database.transcripts import TranscriptStorage


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transcript_storage_delete_older_than_no_backend_returns_zero() -> None:
    """When _db is None, delete_transcripts_older_than returns 0."""
    storage = TranscriptStorage(db=None)
    cutoff = datetime.now(timezone.utc)
    n = await storage.delete_transcripts_older_than(cutoff)
    assert n == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transcript_storage_delete_older_than_delegates_to_backend() -> None:
    """When _db has delete_transcripts_older_than, it is called and result returned."""
    backend = MagicMock()
    backend.delete_transcripts_older_than = AsyncMock(return_value=5)
    storage = TranscriptStorage(db=backend)
    cutoff = datetime.now(timezone.utc)
    n = await storage.delete_transcripts_older_than(cutoff, source="voice_listener", limit=1000)
    assert n == 5
    backend.delete_transcripts_older_than.assert_awaited_once_with(
        cutoff, source="voice_listener", limit=1000
    )
