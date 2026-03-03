"""Run Alembic commands with the local infrastructure config."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Project root (radioshaq/)
ROOT = Path(__file__).resolve().parent.parent.parent
ALEMBIC_INI = ROOT / "infrastructure" / "local" / "alembic.ini"


def _run(args: list[str]) -> int:
    """Run alembic with local config from project root."""
    cmd = [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), *args]
    return subprocess.run(cmd, cwd=ROOT, env=os.environ).returncode


def upgrade() -> int:
    """Run: alembic -c infrastructure/local/alembic.ini upgrade head."""
    return _run(["upgrade", "head"])


def upgrade_sql() -> int:
    """Run: alembic -c infrastructure/local/alembic.ini upgrade head --sql."""
    return _run(["upgrade", "head", "--sql"])


def current() -> int:
    """Run: alembic -c infrastructure/local/alembic.ini current."""
    return _run(["current"])


def main_upgrade() -> None:
    """Entry: uv run alembic-upgrade -> upgrade head."""
    sys.exit(upgrade())


def main_upgrade_sql() -> None:
    """Entry: uv run alembic-upgrade-sql -> upgrade head --sql."""
    sys.exit(upgrade_sql())


def main_current() -> None:
    """Entry: uv run alembic-current -> current."""
    sys.exit(current())
