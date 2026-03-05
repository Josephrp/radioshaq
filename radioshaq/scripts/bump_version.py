#!/usr/bin/env python3
"""Bump semantic version in pyproject.toml [project].version."""

from __future__ import annotations

import argparse
import pathlib
import re
import sys


VERSION_PATTERN = re.compile(r'(?m)^version\s*=\s*"(\d+)\.(\d+)\.(\d+)"\s*$')


def bump_semver(version: tuple[int, int, int], bump_type: str) -> tuple[int, int, int]:
    major, minor, patch = version
    if bump_type == "major":
        return major + 1, 0, 0
    if bump_type == "minor":
        return major, minor + 1, 0
    if bump_type == "patch":
        return major, minor, patch + 1
    raise ValueError(f"Unsupported bump type: {bump_type}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bump version in pyproject.toml")
    parser.add_argument("--file", default="radioshaq/pyproject.toml", help="Path to pyproject.toml")
    parser.add_argument(
        "--bump",
        choices=["major", "minor", "patch"],
        required=True,
        help="Semantic version bump type",
    )
    args = parser.parse_args()

    path = pathlib.Path(args.file)
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 1

    text = path.read_text(encoding="utf-8")
    match = VERSION_PATTERN.search(text)
    if not match:
        print("Could not find [project].version = \"X.Y.Z\" in pyproject.toml", file=sys.stderr)
        return 1

    old_version = tuple(int(p) for p in match.groups())
    new_version = bump_semver(old_version, args.bump)
    new_version_str = ".".join(str(p) for p in new_version)
    updated = VERSION_PATTERN.sub(f'version = "{new_version_str}"', text, count=1)
    path.write_text(updated, encoding="utf-8")

    print(new_version_str)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
