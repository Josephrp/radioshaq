"""Unit tests for API routes (health, auth, radio, messages)."""

import pytest

from fastapi.testclient import TestClient


@pytest.mark.unit
def test_health(client: TestClient):
    """Health endpoint returns 200 and status ok."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.unit
def test_health_ready(client: TestClient):
    """Readiness endpoint returns 200."""
    r = client.get("/health/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


@pytest.mark.unit
def test_auth_token(client: TestClient):
    """POST /auth/token returns access_token."""
    r = client.post(
        "/auth/token",
        params={"subject": "test", "role": "field", "station_id": "ST-1"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data.get("token_type") == "bearer"


@pytest.mark.unit
def test_auth_me_requires_token(client: TestClient):
    """GET /auth/me without token returns 401."""
    r = client.get("/auth/me")
    assert r.status_code == 401


@pytest.mark.unit
def test_auth_me_with_token(
    client: TestClient, auth_headers: dict[str, str]
):
    """GET /auth/me with valid token returns claims."""
    r = client.get("/auth/me", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data.get("sub") == "test-user"
    assert "role" in data


@pytest.mark.unit
def test_radio_bands_requires_auth(client: TestClient):
    """GET /radio/bands without token returns 401."""
    r = client.get("/radio/bands")
    assert r.status_code == 401


@pytest.mark.unit
def test_radio_bands_with_token(
    client: TestClient, auth_headers: dict[str, str]
):
    """GET /radio/bands with token returns bands list."""
    r = client.get("/radio/bands", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "bands" in data
    assert isinstance(data["bands"], list)


@pytest.mark.unit
def test_messages_process_requires_auth(client: TestClient):
    """POST /messages/process without token returns 401."""
    r = client.post("/messages/process", json={"message": "hello"})
    assert r.status_code == 401
