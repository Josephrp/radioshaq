#!/usr/bin/env python3
"""Voice RX audio demo: verify voice listener config and poll transcripts/pending.

Requires HQ running with radio.audio_input_enabled and radio.voice_listener_enabled
(or audio_monitoring_enabled). Runs for --duration seconds then prints a summary.
Exits 0 if health and config are OK; non-zero if API unreachable or critical failure.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Allow importing demo_utils when run as: uv run python scripts/demo/run_voice_rx_audio_demo.py
sys.path.insert(0, str(Path(__file__).resolve().parent))

from demo_utils import (
    API_TIMEOUT,
    expect_status,
    get_audio_config,
    get_audio_pending,
    get_health,
    get_token,
    get_transcripts,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Voice RX audio demo (poll config + transcripts + pending).")
    ap.add_argument("--base-url", default="http://localhost:8000", help="HQ API base URL")
    ap.add_argument("--subject", default="demo-op1", help="JWT subject")
    ap.add_argument("--role", default="field", help="JWT role")
    ap.add_argument("--station-id", default="DEMO-01", help="station_id for JWT")
    ap.add_argument("--duration", type=int, default=30, help="Seconds to run before sampling transcripts/pending")
    ap.add_argument("--require-transcript", action="store_true", help="Exit non-zero if no transcripts after duration")
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    print("Voice RX audio demo")
    print("-------------------")
    print(f"Base URL: {base}")
    print(f"Duration: {args.duration}s")
    print()

    # Health
    try:
        r = get_health(base, timeout=10.0)
    except Exception as e:
        print(f"[fail] Health check failed: {e}", file=sys.stderr)
        return 1
    if not expect_status(r, 200, "GET /health"):
        return 1

    # Token
    try:
        token = get_token(base, args.subject, args.role, args.station_id)
    except Exception as e:
        print(f"[fail] Auth failed: {e}", file=sys.stderr)
        return 1
    print("[ok] Got token")

    # Audio config (optional; 503 if audio not configured)
    r = get_audio_config(base, token, timeout=API_TIMEOUT)
    if r.status_code == 200:
        print("[ok] GET /config/audio available")
    else:
        print(f"[warn] GET /config/audio: {r.status_code} (voice_rx may not be configured)")

    # Run for duration
    print(f"[run] Waiting {args.duration}s for voice activity...")
    time.sleep(args.duration)

    # Pending responses
    r = get_audio_pending(base, token, timeout=API_TIMEOUT)
    pending_count = 0
    if r.status_code == 200:
        try:
            data = r.json()
            pending_count = data.get("count", len(data.get("pending_responses", [])))
        except Exception:
            pass
        print(f"[pending] count={pending_count}")
    else:
        print(f"[warn] GET /audio/pending: {r.status_code}")

    # Transcripts
    r = get_transcripts(base, token, limit=50, timeout=API_TIMEOUT)
    transcript_count = 0
    if r.status_code == 200:
        try:
            data = r.json()
            transcript_count = data.get("count", 0)
        except Exception:
            pass
        print(f"[transcripts] count={transcript_count}")
    else:
        expect_status(r, 200, "GET /transcripts", on_fail="stderr")

    summary = {
        "pending_responses": pending_count,
        "transcript_count": transcript_count,
        "duration_seconds": args.duration,
    }
    print("\nSummary:", json.dumps(summary, indent=2))

    if args.require_transcript and transcript_count == 0 and pending_count == 0:
        print("[fail] No transcripts or pending responses (--require-transcript)", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
