"""Unit tests for contact preferences (get_contact_preferences, set_contact_preferences, record_opt_out)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("geoalchemy2", reason="PostGIS tests require geoalchemy2")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_contact_preferences_returns_none_for_unknown_callsign():
    """get_contact_preferences returns None when callsign is not in registry."""
    from radioshaq.database.postgres_gis import PostGISManager
    from sqlalchemy import select
    from radioshaq.database.models import RegisteredCallsign

    manager = PostGISManager("postgresql+asyncpg://localhost/test")
    mock_session = MagicMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=result_mock)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=None)
    manager.async_session = MagicMock(return_value=cm)

    prefs = await manager.get_contact_preferences("N0CALL")
    assert prefs is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_contact_preferences_returns_dict_when_found():
    """get_contact_preferences returns dict with notify_* fields when callsign is registered."""
    from radioshaq.database.postgres_gis import PostGISManager
    from radioshaq.database.models import RegisteredCallsign

    manager = PostGISManager("postgresql+asyncpg://localhost/test")
    row = MagicMock(spec=RegisteredCallsign)
    row.callsign = "K5ABC"
    row.notify_sms_phone = "+15551234567"
    row.notify_whatsapp_phone = None
    row.notify_on_relay = True
    row.notify_consent_at = datetime(2026, 3, 7, 12, 0, 0, tzinfo=timezone.utc)
    row.notify_consent_source = "api"
    row.notify_opt_out_at = None
    row.notify_opt_out_at_sms = None
    row.notify_opt_out_at_whatsapp = None

    mock_session = MagicMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = row
    mock_session.execute = AsyncMock(return_value=result_mock)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=None)
    manager.async_session = MagicMock(return_value=cm)

    prefs = await manager.get_contact_preferences("K5ABC")
    assert prefs is not None
    assert prefs["callsign"] == "K5ABC"
    assert prefs["notify_sms_phone"] == "+15551234567"
    assert prefs["notify_on_relay"] is True
    assert prefs["notify_consent_source"] == "api"
    assert prefs["notify_opt_out_at"] is None
    assert prefs["notify_opt_out_at_sms"] is None
    assert prefs["notify_opt_out_at_whatsapp"] is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_set_contact_preferences_returns_false_for_unknown_callsign():
    """set_contact_preferences returns False when callsign is not in registry."""
    from radioshaq.database.postgres_gis import PostGISManager

    manager = PostGISManager("postgresql+asyncpg://localhost/test")
    mock_session = MagicMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=result_mock)
    mock_session.commit = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=None)
    manager.async_session = MagicMock(return_value=cm)

    ok = await manager.set_contact_preferences(
        "N0CALL",
        notify_on_relay=True,
        consent_at=datetime.now(timezone.utc),
        consent_source="api",
    )
    assert ok is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_record_opt_out_clears_phone_and_sets_opt_out_at():
    """record_opt_out sets per-channel notify_opt_out_at_* and clears that channel's phone."""
    from radioshaq.database.postgres_gis import PostGISManager
    from radioshaq.database.models import RegisteredCallsign

    manager = PostGISManager("postgresql+asyncpg://localhost/test")
    row = MagicMock(spec=RegisteredCallsign)
    row.notify_sms_phone = "+15551234567"
    row.notify_whatsapp_phone = None
    row.notify_opt_out_at = None
    row.notify_opt_out_at_sms = None
    row.notify_opt_out_at_whatsapp = None

    mock_session = MagicMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = row
    mock_session.execute = AsyncMock(return_value=result_mock)
    mock_session.commit = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=None)
    manager.async_session = MagicMock(return_value=cm)

    ok = await manager.record_opt_out("K5ABC", "sms")
    assert ok is True
    assert row.notify_opt_out_at_sms is not None
    assert row.notify_sms_phone is None
