"""Minimal loguru stub for environments without the real dependency.

This stub provides a drop-in `logger` object with no-op methods so that
code importing `from loguru import logger` continues to run in test and
development environments where loguru is not installed.
"""

from __future__ import annotations

from typing import Any


class _Logger:
    def __getattr__(self, name: str):
        def _noop(*args: Any, **kwargs: Any) -> None:
            return None

        return _noop

    def __call__(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - trivial
        return None


logger = _Logger()

