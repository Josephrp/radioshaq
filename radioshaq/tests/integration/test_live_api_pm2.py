"""Integration tests against a live API (e.g. started with PM2).

Run with BASE_URL set to the API base (e.g. http://127.0.0.1:8001) when using
scripts/run_integration_tests_with_pm2.sh or run_integration_tests_with_pm2.ps1.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from typing import Any

import pytest
import httpx


def _base_url() -> str | None:
    return os.environ.get("BASE_URL", "").rstrip("/") or None


def _wait_for_api(base_url: str, timeout: float = 30.0, interval: float = 0.5) -> bool:
    """Wait until GET {base_url}/health returns 200."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{base_url}/health", timeout=2.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False


@pytest.fixture(scope="module")
def live_base_url() -> str | None:
    """Base URL for live API (from BASE_URL env)."""
    return _base_url()


@pytest.fixture(scope="module")
def live_client(live_base_url: str | None) -> Iterator[httpx.Client | None]:
    """HTTP client for live API if BASE_URL is set."""
    if not live_base_url:
        yield None
        return
    with httpx.Client(base_url=live_base_url, timeout=10.0) as client:
        yield client


@pytest.mark.live_api
@pytest.mark.integration
def test_live_health(live_base_url: str | None, live_client: httpx.Client | None):
    """Live API /health returns 200."""
    if live_base_url is None or live_client is None:
        pytest.skip("BASE_URL not set (run with PM2 script)")
    r = live_client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


@pytest.mark.live_api
@pytest.mark.integration
def test_live_auth_token(live_base_url: str | None, live_client: httpx.Client | None):
    """Live API POST /auth/token returns access_token."""
    if live_base_url is None or live_client is None:
        pytest.skip("BASE_URL not set (run with PM2 script)")
    r = live_client.post(
        "/auth/token",
        params={"subject": "pm2-test", "role": "field", "station_id": "PM2-01"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data.get("token_type") == "bearer"


@pytest.mark.live_api
@pytest.mark.integration
def test_live_radio_bands(live_base_url: str | None, live_client: httpx.Client | None):
    """Live API GET /radio/bands with token returns bands."""
    if live_base_url is None or live_client is None:
        pytest.skip("BASE_URL not set (run with PM2 script)")
    r = live_client.post(
        "/auth/token",
        params={"subject": "pm2-test", "role": "field"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    r2 = live_client.get("/radio/bands", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert "bands" in r2.json()
    assert isinstance(r2.json()["bands"], list)


@pytest.mark.live_api
@pytest.mark.integration
def test_live_health_ready(live_base_url: str | None, live_client: httpx.Client | None):
    """Live API /health/ready returns 200."""
    if live_base_url is None or live_client is None:
        pytest.skip("BASE_URL not set (run with PM2 script)")
    r = live_client.get("/health/ready")
    assert r.status_code == 200
    assert r.json().get("status") == "ready"
