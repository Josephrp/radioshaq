#!/usr/bin/env python3
"""Whitelist + callsign registry demo: register callsigns, submit whitelist-request.

Uses POST /callsigns/register and POST /messages/whitelist-request.
Requires HQ with orchestrator and LLM configured. Exits 0 if steps return 2xx.
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
    post_callsign_register,
    post_whitelist_request,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Whitelist + registry demo.")
    ap.add_argument("--base-url", default="http://localhost:8000", help="HQ API base URL")
    ap.add_argument("--callsigns", nargs="+", default=["FLABC-1", "F1XYZ-1"], help="Callsigns to register")
    ap.add_argument("--whitelist-text", default="I am requesting to be whitelisted for cross band relay. Over.", help="Text for whitelist-request")
    ap.add_argument("--whitelist-callsign", default=None, help="Callsign to pass to whitelist-request (default: first of --callsigns)")
    ap.add_argument("--subject", default="demo-op1", help="JWT subject")
    ap.add_argument("--role", default="field", help="JWT role")
    ap.add_argument("--station-id", default="DEMO-01", help="station_id for JWT")
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    print("Whitelist + registry demo")
    print("------------------------")
    print(f"Base URL: {base}")
    print(f"Callsigns to register: {args.callsigns}")
    print()

    try:
        token = get_token(base, args.subject, args.role, args.station_id)
    except Exception as e:
        print(f"[fail] Auth failed: {e}", file=sys.stderr)
        return 1
    print("[ok] Got token")

    for callsign in args.callsigns:
        r = post_callsign_register(base, token, callsign, timeout=API_TIMEOUT)
        if expect_status(r, 200, f"POST /callsigns/register {callsign}"):
            try:
                print(" ", r.json())
            except Exception:
                pass
        else:
            return 2

    cs = args.whitelist_callsign or (args.callsigns[0] if args.callsigns else None)
    r = post_whitelist_request(
        base, token, args.whitelist_text,
        callsign=cs,
        timeout=API_TIMEOUT,
    )
    # 503 if orchestrator unavailable
    if r.status_code not in (200, 503):
        expect_status(r, 200, "POST /messages/whitelist-request", on_fail="stderr")
        return 3
    print("[ok] POST /messages/whitelist-request:", r.status_code)
    try:
        print("Response:", json.dumps(r.json(), indent=2))
    except Exception:
        print(r.text[:300])

    print("\nSummary: register OK, whitelist-request OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
