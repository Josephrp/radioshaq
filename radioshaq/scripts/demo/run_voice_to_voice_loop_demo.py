#!/usr/bin/env python3
"""Voice-to-voice loop demo: from-audio upload then send-tts with reply message.

Uploads a WAV via POST /messages/from-audio (inject=true), then sends a reply
via POST /radio/send-tts. No Twilio. Exits 0 if both steps succeed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from demo_utils import (
    API_TIMEOUT,
    UPLOAD_TIMEOUT,
    check_hq_hackrf_tx_available,
    expect_status,
    get_token,
    post_from_audio,
    post_send_tts,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Voice-to-voice loop demo (from-audio + send-tts).")
    ap.add_argument("--base-url", default="http://localhost:8000", help="HQ API base URL")
    ap.add_argument("--wav", required=True, help="Path to WAV file (inbound)")
    ap.add_argument("--reply-message", default="Acknowledged. Standing by.", help="Text to send via TTS on air")
    ap.add_argument("--tx-frequency-hz", type=float, default=145_520_000.0, help="TX frequency (Hz)")
    ap.add_argument("--tx-mode", default="NFM", help="TX mode")
    ap.add_argument("--source-callsign", default="FLABC-1", help="Source callsign for from-audio")
    ap.add_argument("--dest-callsign", default="F1XYZ-1", help="Destination callsign for from-audio")
    ap.add_argument("--band", default="40m", help="Band for from-audio")
    ap.add_argument("--subject", default="demo-op1", help="JWT subject")
    ap.add_argument("--role", default="field", help="JWT role")
    ap.add_argument("--station-id", default="DEMO-01", help="station_id for JWT")
    ap.add_argument("--require-hardware", action="store_true", help="Exit non-zero if HackRF SDR TX not configured (real hardware)")
    args = ap.parse_args()

    wav = Path(args.wav)
    if not wav.exists():
        print(f"[fail] WAV not found: {wav}", file=sys.stderr)
        return 2

    base = args.base_url.rstrip("/")
    print("Voice-to-voice loop demo")
    print("------------------------")
    print(f"Base URL: {base}")
    print(f"WAV: {wav}")
    print(f"Reply: {args.reply_message[:50]}...")
    print()

    try:
        token = get_token(base, args.subject, args.role, args.station_id)
    except Exception as e:
        print(f"[fail] Auth failed: {e}", file=sys.stderr)
        return 1
    print("[ok] Got token")

    r = post_from_audio(
        base, token, wav,
        source_callsign=args.source_callsign,
        destination_callsign=args.dest_callsign,
        band=args.band,
        inject=True,
        timeout=UPLOAD_TIMEOUT,
    )
    if not expect_status(r, 200, "POST /messages/from-audio"):
        return 3
    try:
        payload = r.json()
        print("[from-audio] transcript_id={} injected={}".format(
            payload.get("transcript_id"), payload.get("injected")))
    except Exception:
        pass

    if args.require_hardware:
        if not check_hq_hackrf_tx_available(base, token):
            print(
                "[fail] HackRF SDR TX not configured. Set RADIOSHAQ_RADIO__SDR_TX_ENABLED=true and attach HackRF.",
                file=sys.stderr,
            )
            return 6
        print("[ok] HackRF SDR TX configured (real hardware expected)")

    r = post_send_tts(
        base, token, args.reply_message,
        frequency_hz=args.tx_frequency_hz,
        mode=args.tx_mode,
        timeout=UPLOAD_TIMEOUT,
    )
    if not expect_status(r, 200, "POST /radio/send-tts"):
        return 4
    try:
        data = r.json()
        success = data.get("success", False)
        print("Response:", json.dumps(data, indent=2))
        if not success:
            print("[fail] send-tts reported success=false", file=sys.stderr)
            return 5
    except Exception:
        pass

    print("\nSummary: from-audio OK, send-tts OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
