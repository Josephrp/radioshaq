"""Unit tests for PostGIS manager: store_coordination_event 0.0 fix, get_latest_location_decoded."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("geoalchemy2", reason="PostGIS tests require geoalchemy2")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_store_coordination_event_accepts_zero_coordinates():
    """store_coordination_event with latitude=0.0, longitude=0.0 stores a non-null location (0.0 is valid)."""
    from radioshaq.database.postgres_gis import PostGISManager

    manager = PostGISManager("postgresql+asyncpg://localhost/test")
    mock_session = MagicMock()
    mock_session.commit = AsyncMock()

    def add_side_effect(obj):
        obj.id = 1

    mock_session.add = MagicMock(side_effect=add_side_effect)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=None)
    manager.async_session = MagicMock(return_value=cm)

    event_id = await manager.store_coordination_event(
        event_type="schedule",
        initiator_callsign="K5ABC",
        latitude=0.0,
        longitude=0.0,
    )

    assert event_id == 1
    mock_session.add.assert_called_once()
    event = mock_session.add.call_args[0][0]
    assert event.location is not None
    assert "POINT(0.0 0.0)" in str(event.location) or "POINT(0 0)" in str(event.location)
