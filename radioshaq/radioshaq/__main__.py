"""Entry point for running SHAKODS as a module."""

from __future__ import annotations

import sys

from radioshaq.cli import app

if __name__ == "__main__":
    sys.exit(app())
