#!/usr/bin/env python3
"""Bump or set project version and sync known version fields."""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import re
import sys


SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
PYPROJECT_VERSION_RE = re.compile(r'(?m)^version\s*=\s*"([^"]+)"\s*$')
INIT_VERSION_RE = re.compile(r'(?m)^__version__\s*=\s*"([^"]+)"\s*$')
PKG_JSON_VERSION_RE = re.compile(r'(?m)^(\s*)"version":\s*"([^"]+)",\s*$')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update project versions")
    parser.add_argument(
        "--bump",
        choices=["major", "minor", "patch"],
        help="Semantic version bump type (for stable version updates).",
    )
    parser.add_argument(
        "--set-version",
        help="Explicit version string to set (for stable or prerelease).",
    )
    parser.add_argument(
        "--nightly-from",
        help="Build prerelease from base semver (example: 1.2.3 -> 1.2.3.devYYYYMMDDHHMM).",
    )
    parser.add_argument(
        "--sync-all",
        action="store_true",
        help="Sync pyproject, package __version__, API version, and web package.json.",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Repository root path.",
    )
    return parser.parse_args()


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: pathlib.Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def split_base(version: str) -> tuple[int, int, int]:
    base = version.split(".dev", 1)[0]
    match = SEMVER_RE.match(base)
    if not match:
        raise ValueError(f"Expected semantic version X.Y.Z, got: {version}")
    major, minor, patch = (int(p) for p in match.groups())
    return major, minor, patch


def bump_semver(version: tuple[int, int, int], bump_type: str) -> tuple[int, int, int]:
    major, minor, patch = version
    if bump_type == "major":
        return major + 1, 0, 0
    if bump_type == "minor":
        return major, minor + 1, 0
    if bump_type == "patch":
        return major, minor, patch + 1
    raise ValueError(f"Unsupported bump type: {bump_type}")


def nightly_version(base: str) -> str:
    split_base(base)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M")
    return f"{base}.dev{stamp}"


def replace_single(pattern: re.Pattern[str], text: str, replacement: str, path: pathlib.Path) -> str:
    updated, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise ValueError(f"Could not update expected version field in {path}")
    return updated


def derive_new_version(
    pyproject_text: str,
    bump: str | None,
    set_version: str | None,
    nightly_from: str | None,
) -> str:
    provided = [value for value in [bump, set_version, nightly_from] if value]
    if len(provided) != 1:
        raise ValueError("Exactly one of --bump, --set-version, or --nightly-from is required.")

    if set_version:
        return set_version
    if nightly_from:
        return nightly_version(nightly_from)

    current = PYPROJECT_VERSION_RE.search(pyproject_text)
    if not current:
        raise ValueError('Could not find `version = "..."` in pyproject.toml')
    current_base = split_base(current.group(1))
    bumped = bump_semver(current_base, bump or "patch")
    return ".".join(str(p) for p in bumped)


def sync_versions(repo_root: pathlib.Path, version: str, sync_all: bool) -> None:
    pyproject = repo_root / "radioshaq" / "pyproject.toml"
    pyproject_text = read_text(pyproject)
    pyproject_text = replace_single(
        PYPROJECT_VERSION_RE,
        pyproject_text,
        f'version = "{version}"',
        pyproject,
    )
    write_text(pyproject, pyproject_text)

    if not sync_all:
        return

    init_path = repo_root / "radioshaq" / "radioshaq" / "__init__.py"
    init_text = read_text(init_path)
    init_text = replace_single(
        INIT_VERSION_RE,
        init_text,
        f'__version__ = "{version}"',
        init_path,
    )
    write_text(init_path, init_text)

    package_json = repo_root / "radioshaq" / "web-interface" / "package.json"
    package_json_text = read_text(package_json)
    package_json_text = replace_single(
        PKG_JSON_VERSION_RE,
        package_json_text,
        r'\1"version": "' + version + '",',
        package_json,
    )
    write_text(package_json, package_json_text)


def main() -> int:
    args = parse_args()
    repo_root = pathlib.Path(args.project_root).resolve()
    pyproject = repo_root / "radioshaq" / "pyproject.toml"
    if not pyproject.exists():
        print(f"File not found: {pyproject}", file=sys.stderr)
        return 1

    try:
        new_version = derive_new_version(
            pyproject_text=read_text(pyproject),
            bump=args.bump,
            set_version=args.set_version,
            nightly_from=args.nightly_from,
        )
        sync_versions(repo_root, new_version, sync_all=args.sync_all)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Set version to {new_version}", file=sys.stderr)
    print(new_version, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
