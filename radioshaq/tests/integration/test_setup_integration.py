"""Integration tests for radioshaq setup.

Tests run_setup --no-input and CLI invocation; does not start Docker or API.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from radioshaq.setup import run_setup
from radioshaq.config.schema import load_config


def test_setup_no_input_produces_loadable_config(tmp_path: Path) -> None:
    """run_setup --no-input writes .env and config.yaml that load_config can load."""
    exit_code = run_setup(
        interactive=False,
        no_input=True,
        config_dir=tmp_path,
        mode="field",
        db_url="postgresql://u:p@localhost:5434/rs",
    )
    assert exit_code == 0
    assert (tmp_path / ".env").exists()
    assert (tmp_path / "config.yaml").exists()

    config = load_config(tmp_path / "config.yaml")
    assert config.mode.value == "field"
    assert "localhost" in config.database.postgres_url
    assert "5434" in config.database.postgres_url


def test_setup_cli_no_input_exit_zero(tmp_path: Path) -> None:
    """CLI 'radioshaq setup --no-input --mode field' exits 0 and creates files."""
    env = os.environ.copy()
    env["RADIOSHAQ_LICENSE_ACCEPTED"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "radioshaq.cli", "setup", "--no-input", "--mode", "field", "--config-dir", str(tmp_path)],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert (tmp_path / "config.yaml").exists()
    assert (tmp_path / ".env").exists()
