"""Integration tests: API serves bundled web UI when web_ui is present."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from radioshaq.api.server import app, _web_ui_dir


@pytest.mark.integration
def test_web_ui_root_served_when_bundle_present(client: TestClient) -> None:
    """When web_ui dir exists, GET / returns 200 and serves index with expected content."""
    if _web_ui_dir() is None:
        pytest.skip("web_ui not built (run: cd web-interface && npm run build && cp -r dist ../radioshaq/web_ui)")
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    body = r.text
    assert "root" in body, "Expected SPA root div in served HTML"
    assert (
        "radioshaq" in body.lower()
    ), "Expected app name (RadioShaq) in served HTML"


@pytest.mark.integration
def test_web_ui_assets_served_when_bundle_present(client: TestClient) -> None:
    """When web_ui exists, GET / returns index that references an asset (script)."""
    if _web_ui_dir() is None:
        pytest.skip("web_ui not built")
    r = client.get("/")
    assert r.status_code == 200
    body = r.text
    assert "/assets/" in body or "assets/" in body, "Expected asset reference in index.html"
