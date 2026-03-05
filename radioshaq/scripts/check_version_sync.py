#!/usr/bin/env python3
"""Validate version consistency across project metadata/runtime surfaces."""

from __future__ import annotations

import pathlib
import re
import sys


def extract(pattern: str, text: str, label: str) -> str:
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        raise ValueError(f"Could not find version for {label}")
    return match.group(1)


def main() -> int:
    repo = pathlib.Path(__file__).resolve().parents[2]
    pyproject = (repo / "radioshaq" / "pyproject.toml").read_text(encoding="utf-8")
    init_py = (repo / "radioshaq" / "radioshaq" / "__init__.py").read_text(encoding="utf-8")
    package_json = (repo / "radioshaq" / "web-interface" / "package.json").read_text(encoding="utf-8")
    api_server = (repo / "radioshaq" / "radioshaq" / "api" / "server.py").read_text(encoding="utf-8")

    versions = {
        "pyproject": extract(r'^version\s*=\s*"([^"]+)"\s*$', pyproject, "pyproject"),
        "__init__": extract(r'^__version__\s*=\s*"([^"]+)"\s*$', init_py, "__init__"),
        "package_json": extract(r'^\s*"version":\s*"([^"]+)",\s*$', package_json, "package_json"),
    }
    if "from radioshaq import __version__" not in api_server:
        print("API server is not deriving version from radioshaq.__version__", file=sys.stderr)
        return 1

    unique = set(versions.values())
    if len(unique) == 1:
        print(f"Version sync OK: {next(iter(unique))}")
        return 0

    print("Version mismatch detected:", file=sys.stderr)
    for name, version in versions.items():
        print(f"  {name}: {version}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
