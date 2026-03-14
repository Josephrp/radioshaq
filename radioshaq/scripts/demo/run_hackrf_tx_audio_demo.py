#!/usr/bin/env python3
"""HackRF TX audio demo: POST /radio/send-audio with a WAV file.

Requires HQ with radio.sdr_tx_enabled=true and real HackRF hardware connected.
Use --require-hardware to exit non-zero if SDR TX is not configured (ensures live demos use real hardware).
Exits 0 on HTTP 200 and success=true in response; non-zero otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from demo_utils import (
    UPLOAD_TIMEOUT,
    check_hq_hackrf_tx_available,
    expect_status,
    get_token,
    post_send_audio,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="HackRF TX audio demo (send-audio).")
    ap.add_argument("--base-url", default="http://localhost:8000", help="HQ API base URL")
    ap.add_argument("--wav", required=True, help="Path to WAV file")
    ap.add_argument("--frequency-hz", type=float, default=145_520_000.0, help="TX frequency (Hz)")
    ap.add_argument("--mode", default="NFM", help="TX mode (NFM, AM, USB, LSB, CW)")
    ap.add_argument("--subject", default="demo-op1", help="JWT subject")
    ap.add_argument("--role", default="field", help="JWT role")
    ap.add_argument("--station-id", default="DEMO-01", help="station_id for JWT")
    ap.add_argument("--require-hardware", action="store_true", help="Exit non-zero if HackRF SDR TX is not configured (ensures real hardware)")
    args = ap.parse_args()

    wav = Path(args.wav)
    if not wav.exists():
        print(f"[fail] WAV not found: {wav}", file=sys.stderr)
        return 2

    base = args.base_url.rstrip("/")
    print("HackRF TX audio demo")
    print("-------------------")
    print(f"Base URL: {base}")
    print(f"WAV: {wav}")
    print(f"Frequency: {args.frequency_hz:.0f} Hz")
    print(f"Mode: {args.mode}")
    print()

    try:
        token = get_token(base, args.subject, args.role, args.station_id)
    except Exception as e:
        print(f"[fail] Auth failed: {e}", file=sys.stderr)
        return 1
    print("[ok] Got token")

    if args.require_hardware:
        if not check_hq_hackrf_tx_available(base, token):
            print(
                "[fail] HackRF SDR TX is not configured. Set RADIOSHAQ_RADIO__SDR_TX_ENABLED=true, "
                "attach HackRF, and ensure pyhackrf2 is installed (uv sync --extra hackrf).",
                file=sys.stderr,
            )
            return 5
        print("[ok] HackRF SDR TX configured (real hardware expected)")

    r = post_send_audio(
        base, token, wav,
        frequency_hz=args.frequency_hz,
        mode=args.mode,
        timeout=UPLOAD_TIMEOUT,
    )

    if not expect_status(r, 200, "POST /radio/send-audio"):
        return 3

    try:
        data = r.json()
        success = data.get("success", False)
        notes = data.get("notes", "")
        print("Response:", json.dumps(data, indent=2))
        if not success:
            print(f"[fail] TX reported success=false: {notes}", file=sys.stderr)
            return 4
    except Exception as e:
        print(f"[warn] Could not parse response: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
