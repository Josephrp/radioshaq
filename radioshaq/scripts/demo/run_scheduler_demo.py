#!/usr/bin/env python3
"""Scheduler demo: send a scheduling request via POST /messages/process.

Orchestrator should route to SchedulerAgent; coordination event may be stored if DB is configured.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from demo_utils import (
    API_TIMEOUT,
    expect_status,
    get_token,
    post_process,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Scheduler demo.")
    ap.add_argument("--base-url", default="http://localhost:8000", help="HQ API base URL")
    ap.add_argument("--message", default="Schedule a call for FLABC-1 with F1XYZ-1 at 1600 UTC on 40m.", help="Process message (scheduling request)")
    ap.add_argument("--subject", default="demo-op1", help="JWT subject")
    ap.add_argument("--role", default="field", help="JWT role")
    ap.add_argument("--station-id", default="DEMO-01", help="station_id for JWT")
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    print("Scheduler demo")
    print("-------------")
    print(f"Base URL: {base}")
    print(f"Message: {args.message[:60]}...")
    print()

    try:
        token = get_token(base, args.subject, args.role, args.station_id)
    except Exception as e:
        print(f"[fail] Auth failed: {e}", file=sys.stderr)
        return 1
    print("[ok] Got token")

    r = post_process(base, token, args.message, timeout=API_TIMEOUT)
    if r.status_code == 503:
        print("[warn] POST /messages/process: 503 (orchestrator not available)")
        return 0
    if not expect_status(r, 200, "POST /messages/process"):
        return 2
    try:
        print("Response:", json.dumps(r.json(), indent=2))
    except Exception:
        print(r.text[:300])
    print("\nSummary: scheduler demo completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
