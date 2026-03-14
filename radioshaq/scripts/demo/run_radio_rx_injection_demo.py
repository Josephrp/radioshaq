#!/usr/bin/env python3
"""Radio RX injection demo: inject messages via /inject/message and /messages/inject-and-store.

Verifies injections return 200 and optional transcript storage. No RF hardware required.
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
    get_transcripts,
    post_inject_and_store,
    post_inject_message,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Radio RX injection demo.")
    ap.add_argument("--base-url", default="http://localhost:8000", help="HQ API base URL")
    ap.add_argument("--subject", default="demo-op1", help="JWT subject")
    ap.add_argument("--role", default="field", help="JWT role")
    ap.add_argument("--station-id", default="DEMO-01", help="station_id for JWT")
    ap.add_argument("--injections", type=int, default=5, help="Number of messages to inject")
    ap.add_argument("--store", action="store_true", help="Use inject-and-store for last half of injections")
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    print("Radio RX injection demo")
    print("----------------------")
    print(f"Base URL: {base}")
    print(f"Injections: {args.injections}")
    print()

    try:
        token = get_token(base, args.subject, args.role, args.station_id)
    except Exception as e:
        print(f"[fail] Auth failed: {e}", file=sys.stderr)
        return 1
    print("[ok] Got token")

    bands = ["40m", "2m", "40m", "2m", "40m"]
    source_callsigns = ["K5ABC", "W1XYZ", "FLABC-1", "F1XYZ-1", "K5ABC"]
    dest_callsigns = ["W1XYZ", "K5ABC", "F1XYZ-1", "FLABC-1", "W1XYZ"]
    ok_count = 0

    for i in range(args.injections):
        band = bands[i % len(bands)]
        src = source_callsigns[i % len(source_callsigns)]
        dst = dest_callsigns[i % len(dest_callsigns)]
        text = f"Injection {i+1} on {band} from {src} to {dst}."

        if args.store and i >= args.injections // 2:
            r = post_inject_and_store(
                base, token, text,
                band=band, source_callsign=src, destination_callsign=dst,
                timeout=API_TIMEOUT,
            )
            kind = "inject-and-store"
        else:
            r = post_inject_message(
                base, token, text,
                band=band, source_callsign=src, destination_callsign=dst,
                timeout=API_TIMEOUT,
            )
            kind = "inject/message"

        if r.status_code == 200:
            ok_count += 1
            print(f"[ok] {kind} #{i+1} band={band}")
        else:
            print(f"[fail] {kind} #{i+1}: HTTP {r.status_code}", file=sys.stderr)

    if ok_count != args.injections:
        print(f"[fail] {ok_count}/{args.injections} injections succeeded", file=sys.stderr)
        return 2

    r = get_transcripts(base, token, limit=50, timeout=API_TIMEOUT)
    transcript_count = 0
    if r.status_code == 200:
        try:
            transcript_count = r.json().get("count", 0)
        except Exception:
            pass
    summary = {"injections_ok": ok_count, "transcript_count": transcript_count}
    print("\nSummary:", json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
