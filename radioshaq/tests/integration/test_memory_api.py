"""Integration tests for memory API routes.

Requires app with memory tables migrated; memory_manager in app.state or 503.
Auth: path callsign must match token station_id/sub (403 otherwise).
"""

from __future__ import annotations

import pytest

from fastapi.testclient import TestClient


def test_memory_blocks_503_or_200(client: TestClient, auth_headers_callsign: dict) -> None:
    """GET /memory/{callsign}/blocks returns 503 if memory not available, else 200."""
    r = client.get("/memory/W1ABC/blocks", headers=auth_headers_callsign)
    # 503 when memory_manager is None (e.g. no DB); 200 when available
    assert r.status_code in (200, 503), r.text
    if r.status_code == 200:
        data = r.json()
        assert isinstance(data, dict)
        assert "system_instructions" in data or "user" in data or "identity" in data


def test_memory_blocks_403_wrong_callsign(client: TestClient, auth_headers_callsign: dict) -> None:
    """GET /memory/{other}/blocks with token for W1ABC returns 403."""
    r = client.get("/memory/OTHER/blocks", headers=auth_headers_callsign)
    assert r.status_code == 403


def test_memory_blocks_401_no_auth(client: TestClient) -> None:
    """GET /memory/W1ABC/blocks without Bearer returns 401."""
    r = client.get("/memory/W1ABC/blocks")
    assert r.status_code == 401


def test_memory_summaries_503_or_200(client: TestClient, auth_headers_callsign: dict) -> None:
    """GET /memory/{callsign}/summaries returns 503 or 200."""
    r = client.get("/memory/W1ABC/summaries?days=7", headers=auth_headers_callsign)
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        assert isinstance(r.json(), list)
