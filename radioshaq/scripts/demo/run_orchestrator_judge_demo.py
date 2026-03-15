#!/usr/bin/env python3
"""Orchestrator + Judge demo: send several messages via POST /messages/process.

Verifies orchestrator responds with 200. Does not assert which agents run; check HQ logs.
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
    ap = argparse.ArgumentParser(description="Orchestrator + Judge demo.")
    ap.add_argument("--base-url", default="http://localhost:8000", help="HQ API base URL")
    ap.add_argument("--subject", default="demo-op1", help="JWT subject")
    ap.add_argument("--role", default="field", help="JWT role")
    ap.add_argument("--station-id", default="DEMO-01", help="station_id for JWT")
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    print("Orchestrator + Judge demo")
    print("------------------------")
    print(f"Base URL: {base}")
    print()

    try:
        token = get_token(base, args.subject, args.role, args.station_id)
    except Exception as e:
        print(f"[fail] Auth failed: {e}", file=sys.stderr)
        return 1
    print("[ok] Got token")

    # Messages that may trigger different agents (scheduler, gis/propagation, simple reply)
    messages = [
        "Hello, can you confirm you are online?",
        "Schedule a call for FLABC-1 with F1XYZ-1 at 1600 UTC on 40m.",
    ]

    for i, msg in enumerate(messages):
        r = post_process(base, token, msg, timeout=API_TIMEOUT)
        if r.status_code == 503:
            print(f"[warn] POST /messages/process #{i+1}: 503 (orchestrator not available)")
            continue
        if not expect_status(r, 200, f"POST /messages/process #{i+1}"):
            return 2
        try:
            data = r.json()
            print(" Reply:", (data.get("message") or "")[:80])
        except Exception:
            pass

    print("\nSummary: process requests completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
