"""GPL-2.0-only acceptance gate for official entrypoints."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

ACCEPTANCE_VERSION = "gpl-2.0-only-v1"
ACCEPTANCE_ENV_VAR = "RADIOSHAQ_LICENSE_ACCEPTED"
ACCEPTANCE_FILE = Path.home() / ".radioshaq" / "license_acceptance.json"


def _license_path() -> str:
    """Best-effort path or URL for the GPL license text.

    Prefers a repo-local LICENSE for editable installs (monorepo root, then
    radioshaq dir), then falls back to the wheel's dist-info license file when
    available, and finally a canonical URL.
    """
    base = Path(__file__).resolve().parent.parent
    # Monorepo root (e.g. .../monorepo/LICENSE.md)
    repo_root_candidate = base.parent / "LICENSE.md"
    if repo_root_candidate.exists():
        return str(repo_root_candidate)
    # Radioshaq package dir (e.g. .../monorepo/radioshaq/LICENSE.md)
    pkg_candidate = base / "LICENSE.md"
    if pkg_candidate.exists():
        return str(pkg_candidate)

    # Regular wheel install: LICENSE.md is included via license-files in dist-info
    try:
        dist = metadata.distribution("radioshaq")
        dist_candidate = dist.locate_file("LICENSE.md")
        if Path(dist_candidate).is_file():
            return str(dist_candidate)
    except metadata.PackageNotFoundError:
        # Fall through to canonical URL
        pass

    # Fallback to canonical GitHub URL if we can't find a local file
    return "https://github.com/josephrp/radioshaq/blob/main/LICENSE.md"


def is_license_accepted() -> bool:
    """Return True when GPL acceptance has already been recorded."""
    env_value = os.environ.get(ACCEPTANCE_ENV_VAR, "").strip().lower()
    if env_value in {"1", "true", "yes"}:
        return True

    if not ACCEPTANCE_FILE.exists():
        return False

    try:
        payload = json.loads(ACCEPTANCE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False

    return payload.get("acceptance_version") == ACCEPTANCE_VERSION


def record_license_acceptance() -> None:
    """Persist acceptance state for future CLI sessions."""
    ACCEPTANCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "acceptance_version": ACCEPTANCE_VERSION,
        "accepted_at": datetime.now(timezone.utc).isoformat(),
    }
    ACCEPTANCE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def ensure_license_accepted() -> None:
    """Raise RuntimeError unless GPL terms are accepted."""
    if is_license_accepted():
        return

    is_non_interactive = (
        not sys.stdin.isatty()
        or os.environ.get("CI", "").strip().lower() in {"1", "true", "yes"}
    )
    if is_non_interactive:
        raise RuntimeError(
            "RadioShaq requires GPL-2.0-only acceptance before use. "
            f"Read {_license_path()} and either run an interactive CLI session once "
            f"or set {ACCEPTANCE_ENV_VAR}=1 for non-interactive environments."
        )

    print("RadioShaq is licensed under GPL-2.0-only.")
    print(f"Read the full license at: {_license_path()}")
    print("To continue, type: ACCEPT")
    response = input("> ").strip()
    if response != "ACCEPT":
        raise RuntimeError("License not accepted. Exiting.")

    record_license_acceptance()
