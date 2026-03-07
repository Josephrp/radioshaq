"""Unit tests for GIS API routes: POST/GET location, GET operators-nearby."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


def _stored_location(id_: int, callsign: str, lat: float, lon: float, timestamp: str = "2025-03-07T12:00:00+00:00"):
    return {
        "id": id_,
        "callsign": callsign,
        "latitude": lat,
        "longitude": lon,
        "source": "user_disclosed",
        "timestamp": timestamp,
    }


@pytest.fixture
def mock_db():
    """PostGISManager mock with store_operator_location, get_latest_location_decoded, find_operators_nearby."""
    db = MagicMock()
    db.store_operator_location = AsyncMock(return_value=_stored_location(1, "K5ABC", 48.8566, 2.3522))
    db.get_latest_location_decoded = AsyncMock(return_value=None)
    db.find_operators_nearby = AsyncMock(return_value=[])
    # Lifespan teardown awaits db.close(); must be async.
    db.close = AsyncMock(return_value=None)
    return db


@pytest.fixture
def client_with_gis_db(client, mock_db):
    """Test client with app.state.db set to mock_db so get_db returns it."""
    client.app.state.db = mock_db
    return client


@pytest.mark.unit
def test_post_location_success(client_with_gis_db, auth_headers, mock_db):
    """POST /gis/location with valid lat/lon returns 200 and stored record (no refetch, no TOCTOU)."""
    mock_db.store_operator_location.return_value = _stored_location(1, "K5ABC", 48.8566, 2.3522)
    r = client_with_gis_db.post(
        "/gis/location",
        json={"callsign": "K5ABC", "latitude": 48.8566, "longitude": 2.3522},
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["callsign"] == "K5ABC"
    assert data["latitude"] == 48.8566
    assert data["longitude"] == 2.3522
    assert data["source"] == "user_disclosed"
    assert "id" in data
    assert data.get("confidence") == 1.0


@pytest.mark.unit
def test_post_location_zero_coords(client_with_gis_db, auth_headers, mock_db):
    """POST /gis/location with 0.0, 0.0 is valid and stored."""
    mock_db.store_operator_location.return_value = _stored_location(1, "W0ZERO", 0.0, 0.0)
    r = client_with_gis_db.post(
        "/gis/location",
        json={"callsign": "W0ZERO", "latitude": 0.0, "longitude": 0.0},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["latitude"] == 0.0
    assert r.json()["longitude"] == 0.0


@pytest.mark.unit
def test_post_location_text_only_returns_400(client_with_gis_db, auth_headers):
    """POST /gis/location with only location_text returns 400 (v1 strict)."""
    r = client_with_gis_db.post(
        "/gis/location",
        json={"callsign": "K5ABC", "location_text": "Lyon"},
        headers=auth_headers,
    )
    assert r.status_code == 400
    detail = r.json().get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error") == "ambiguous_location"


@pytest.mark.unit
def test_get_location_success(client_with_gis_db, auth_headers, mock_db):
    """GET /gis/location/{callsign} returns 200 with lat/lon when stored."""
    mock_db.get_latest_location_decoded.return_value = {
        "id": 1,
        "callsign": "K5ABC",
        "latitude": 48.8566,
        "longitude": 2.3522,
        "source": "user_disclosed",
        "timestamp": "2025-03-07T12:00:00+00:00",
        "altitude_meters": None,
        "accuracy_meters": None,
        "session_id": None,
    }
    r = client_with_gis_db.get("/gis/location/K5ABC", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["callsign"] == "K5ABC"
    assert data["latitude"] == 48.8566
    assert data["longitude"] == 2.3522


@pytest.mark.unit
def test_get_location_404(client_with_gis_db, auth_headers, mock_db):
    """GET /gis/location/{callsign} returns 404 when no location."""
    mock_db.get_latest_location_decoded.return_value = None
    r = client_with_gis_db.get("/gis/location/N0CALL", headers=auth_headers)
    assert r.status_code == 404


@pytest.mark.unit
def test_get_operators_nearby_success(client_with_gis_db, auth_headers, mock_db):
    """GET /gis/operators-nearby returns 200 and list from db."""
    mock_db.find_operators_nearby.return_value = [
        {"callsign": "K5ABC", "distance_meters": 1000, "timestamp": "2025-03-07T12:00:00+00:00"},
    ]
    r = client_with_gis_db.get(
        "/gis/operators-nearby",
        params={"latitude": 40.0, "longitude": -74.0, "radius_meters": 50000},
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "operators" in data
    assert data["count"] == 1
    assert data["operators"][0]["callsign"] == "K5ABC"


@pytest.mark.unit
def test_gis_routes_require_auth(client):
    """GIS routes return 401 without Bearer token."""
    r = client.post("/gis/location", json={"callsign": "K5ABC", "latitude": 48.0, "longitude": 2.0})
    assert r.status_code == 401
    r = client.get("/gis/location/K5ABC")
    assert r.status_code == 401
    r = client.get("/gis/operators-nearby", params={"latitude": 40.0, "longitude": -74.0})
    assert r.status_code == 401
