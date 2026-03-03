#!/usr/bin/env python3
"""Run Alembic with script_location set to absolute path (avoids 'Failed to canonicalize script path' on Windows).

Usage from radioshaq directory:
  python infrastructure/local/run_alembic.py revision --autogenerate -m "add_foo"
  python infrastructure/local/run_alembic.py upgrade head
  python infrastructure/local/run_alembic.py current
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Project root = radioshaq (parent of infrastructure)
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent.parent
os.chdir(_project_root)
sys.path.insert(0, str(_project_root))

from alembic.config import Config
from alembic import command

_CONFIG_PATH = _script_dir / "alembic.ini"
_SCRIPT_LOCATION = _script_dir / "alembic"


def main() -> None:
    alembic_cfg = Config(str(_CONFIG_PATH))
    alembic_cfg.set_main_option("script_location", str(_SCRIPT_LOCATION))

    if len(sys.argv) < 2:
        command.current(alembic_cfg)
        return

    cmd = sys.argv[1].lower()
    args = sys.argv[2:]

    if cmd == "revision":
        autogenerate = "--autogenerate" in args
        msg = None
        for i, a in enumerate(args):
            if a in ("-m", "--message") and i + 1 < len(args):
                msg = args[i + 1]
                break
        command.revision(alembic_cfg, message=msg or "revision", autogenerate=autogenerate)
    elif cmd == "upgrade":
        revision = args[0] if args else "head"
        command.upgrade(alembic_cfg, revision)
    elif cmd == "downgrade":
        revision = args[0] if args else "-1"
        command.downgrade(alembic_cfg, revision)
    elif cmd == "current":
        command.current(alembic_cfg)
    elif cmd == "history":
        command.history(alembic_cfg)
    else:
        # Fallback: run revision with all args (e.g. --autogenerate -m "msg")
        autogenerate = "--autogenerate" in sys.argv
        msg = None
        for i, a in enumerate(sys.argv):
            if a in ("-m", "--message") and i + 1 < len(sys.argv):
                msg = sys.argv[i + 1]
                break
        command.revision(alembic_cfg, message=msg, autogenerate=autogenerate)


if __name__ == "__main__":
    main()
