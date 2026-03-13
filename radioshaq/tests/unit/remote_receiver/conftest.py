"""Fixtures for remote receiver unit tests: ensure app has test state without lifespan."""

from __future__ import annotations

import pytest

from radioshaq.remote_receiver.server import app, ensure_test_state


@pytest.fixture(autouse=True)
def ensure_remote_receiver_test_state() -> None:
    """Ensure app.state has receiver / hackrf_broker for tests that use app without lifespan."""
    ensure_test_state(app)
