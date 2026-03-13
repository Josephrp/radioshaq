#!/usr/bin/env python3
"""Full live demo runner (Option C: no RF RX hardware validation).

This script drives the *deployed* HQ API via HTTP and exercises:
- Auth/token
- Health
- Band listing + propagation endpoint
- Audio ingestion: POST /messages/from-audio (your prerecorded WAVs)
- Inject-and-store (text path)
- Relay: radio + SMS + WhatsApp (requires bus consumer + Twilio configured)
- HackRF TX via deployed API: POST /radio/send-audio and /radio/send-tts
- Transcript search

Prereqs:
  - HQ API running (uv run radioshaq run-api)
  - Postgres migrated (for transcript storage) recommended
  - For SMS/WhatsApp sending:
      RADIOSHAQ_BUS_CONSUMER_ENABLED=1
      Twilio config present (RADIOSHAQ_TWILIO__ACCOUNT_SID, __AUTH_TOKEN, __FROM_NUMBER, __WHATSAPP_FROM)
  - For HackRF SDR TX:
      config.radio.sdr_tx_enabled=true and HackRF connected
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx


def _token(base_url: str, subject: str, role: str, station_id: str) -> str:
    r = httpx.post(
        f"{base_url.rstrip('/')}/auth/token",
        params={"subject": subject, "role": role, "station_id": station_id},
        timeout=15.0,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _print_step(title: str) -> None:
    print(f"\n=== {title} ===")


def main() -> int:
    ap = argparse.ArgumentParser(description="Run full live demo via HQ API (Option C).")
    ap.add_argument("--base-url", default="http://localhost:8000", help="HQ API base URL")
    ap.add_argument("--subject", default="demo-op1", help="JWT subject for /auth/token")
    ap.add_argument("--role", default="field", help="JWT role for /auth/token")
    ap.add_argument("--station-id", default="DEMO-01", help="station_id for /auth/token")
    ap.add_argument("--recordings-dir", required=True, help="Folder containing WAV recordings to upload")
    ap.add_argument("--source-callsign", default="K5ABC", help="Source callsign for from-audio uploads")
    ap.add_argument("--dest-callsign", default="W1XYZ", help="Destination callsign for some flows")
    ap.add_argument("--band", default="40m", help="Band label to store with from-audio transcripts")
    ap.add_argument("--sms-to", default="", help="Destination phone (E.164) for SMS relay test")
    ap.add_argument("--whatsapp-to", default="", help="Destination phone (E.164) for WhatsApp relay test")
    ap.add_argument("--tx-frequency-hz", type=float, default=145_520_000.0, help="HackRF TX center frequency (Hz)")
    ap.add_argument("--tx-mode", default="NFM", help="HackRF TX mode (NFM/AM/USB/LSB/CW)")
    ap.add_argument("--tx-wav", default="", help="Specific WAV file (in recordings-dir) to transmit via /radio/send-audio")
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    rec_dir = Path(args.recordings_dir)
    if not rec_dir.exists():
        print(f"[setup][error] recordings-dir not found: {rec_dir}", file=sys.stderr)
        return 2

    print("RadioShaq full live demo (Option C)")
    print("-----------------------------------")
    print(f"HQ base URL:         {base}")
    print(f"Recordings dir:      {rec_dir}")
    print(f"Source callsign:     {args.source_callsign}")
    print(f"Destination callsign:{args.dest_callsign}")
    print(f"Band label:          {args.band}")
    if args.sms_to:
        print(f"SMS relay target:    {args.sms_to}")
    else:
        print("SMS relay target:    (skipped – no --sms-to provided)")
    if args.whatsapp_to:
        print(f"WhatsApp relay tgt:  {args.whatsapp_to}")
    else:
        print("WhatsApp relay tgt:  (skipped – no --whatsapp-to provided)")
    print(f"HackRF TX freq:      {args.tx_frequency_hz:.0f} Hz (~{args.tx_frequency_hz / 1e6:.3f} MHz)")
    print(f"HackRF TX mode:      {args.tx_mode}")
    print()

    _print_step("Auth")
    token = _token(base, args.subject, args.role, args.station_id)
    print("[auth] Got token from /auth/token.")

    _print_step("Health")
    r = httpx.get(f"{base}/health", timeout=10.0)
    try:
        print("[health] Response:", r.json())
    except Exception:
        print(f"[health] status={r.status_code} body={r.text[:200]}")

    _print_step("Radio bands")
    r = httpx.get(f"{base}/radio/bands", headers=_h(token), timeout=15.0)
    r.raise_for_status()
    bands_payload = r.json()
    bands = bands_payload.get("bands", [])
    print(f"[bands] bands={len(bands)}")
    if bands:
        print("[bands] sample:", bands[0])

    _print_step("Radio status (pre-flight)")
    r = httpx.get(f"{base}/radio/status", headers=_h(token), timeout=15.0)
    if r.status_code == 200:
        status = r.json()
        print("[radio/status]", status)
        if not status.get("connected", False):
            reason = status.get("reason", "unknown")
            print(
                "[radio/status][warn] connected=False "
                f"(reason={reason!r}). HackRF SDR TX will be used only if SDR TX "
                "is enabled (config.radio.sdr_tx_enabled=true or "
                "RADIOSHAQ_RADIO__SDR_TX_ENABLED=1) and hardware is attached.",
                file=sys.stderr,
            )
    else:
        print(f"[radio/status][error] HTTP {r.status_code}: {r.text[:200]}", file=sys.stderr)

    _print_step("Propagation (sample)")
    r = httpx.get(
        f"{base}/radio/propagation",
        headers=_h(token),
        params={"lat_origin": 37.7749, "lon_origin": -122.4194, "lat_dest": 34.0522, "lon_dest": -118.2437},
        timeout=30.0,
    )
    if r.status_code == 200:
        print("[propagation] OK (sample request succeeded).")
    else:
        print(f"[propagation][warn] status={r.status_code} (may require DB/GIS deps or config).")

    _print_step("Upload recordings (from-audio) + store transcripts")
    wavs = sorted([p for p in rec_dir.iterdir() if p.suffix.lower() in ('.wav', '.wave')])
    if not wavs:
        print(f"[from-audio][error] No .wav files found in {rec_dir}", file=sys.stderr)
        return 3
    uploaded_ids: list[int] = []
    for p in wavs:
        with p.open("rb") as f:
            files = {"file": (p.name, f, "audio/wav")}
            data = {
                "source_callsign": args.source_callsign,
                "destination_callsign": args.dest_callsign,
                "band": args.band,
                "mode": "NFM",
                "frequency_hz": "0",
                "inject": "true",
            }
            rr = httpx.post(
                f"{base}/messages/from-audio",
                headers=_h(token),
                files=files,
                data=data,
                timeout=120.0,
            )
        rr.raise_for_status()
        payload = rr.json()
        tid = int(payload.get("transcript_id") or 0)
        uploaded_ids.append(tid)
        print(
            "[from-audio] uploaded "
            f"{p.name} -> transcript_id={tid} injected={payload.get('injected')}"
        )
    print(f"[from-audio] Total uploaded transcripts: {len(uploaded_ids)}")

    _print_step("Inject-and-store (text path)")
    body = {
        "text": "DEMO inject-and-store: message should appear in transcripts and RX queue.",
        "band": args.band,
        "mode": "PSK31",
        "source_callsign": args.source_callsign,
        "destination_callsign": args.dest_callsign,
        "metadata": {"demo": True, "path": "inject-and-store"},
    }
    r = httpx.post(f"{base}/messages/inject-and-store", headers=_h(token), json=body, timeout=30.0)
    r.raise_for_status()
    print("[inject-and-store]", r.json())

    _print_step("Relay (radio)")
    relay_body = {
        "message": "DEMO relay: 40m -> 2m (radio path).",
        "source_band": "40m",
        "target_band": "2m",
        "source_callsign": args.source_callsign,
        "destination_callsign": args.dest_callsign,
        "target_channel": "radio",
    }
    r = httpx.post(f"{base}/messages/relay", headers=_h(token), json=relay_body, timeout=30.0)
    r.raise_for_status()
    print("[relay][radio]", r.json())

    if args.sms_to.strip():
        _print_step("Relay (SMS) via outbound dispatcher")
        relay_sms = {
            "message": "DEMO SMS relay: this should be sent via Twilio if configured.",
            "source_band": "40m",
            "target_band": None,
            "source_callsign": args.source_callsign,
            "destination_callsign": args.dest_callsign,
            "target_channel": "sms",
            "destination_phone": args.sms_to.strip(),
        }
        r = httpx.post(f"{base}/messages/relay", headers=_h(token), json=relay_sms, timeout=30.0)
        r.raise_for_status()
        print("[relay][sms]", r.json())
        print("[relay][sms] Waiting 3s for outbound dispatcher to pick up message...")
        time.sleep(3)
    else:
        print("[relay][sms] Skipped (no --sms-to provided).")

    if args.whatsapp_to.strip():
        _print_step("Relay (WhatsApp) via outbound dispatcher")
        relay_wa = {
            "message": "DEMO WhatsApp relay: this should be sent via Twilio if configured.",
            "source_band": "40m",
            "target_band": None,
            "source_callsign": args.source_callsign,
            "destination_callsign": args.dest_callsign,
            "target_channel": "whatsapp",
            "destination_phone": args.whatsapp_to.strip(),
        }
        r = httpx.post(f"{base}/messages/relay", headers=_h(token), json=relay_wa, timeout=30.0)
        r.raise_for_status()
        print("[relay][whatsapp]", r.json())
        print("[relay][whatsapp] Waiting 3s for outbound dispatcher to pick up message...")
        time.sleep(3)
    else:
        print("[relay][whatsapp] Skipped (no --whatsapp-to provided).")

    _print_step("HackRF TX (send-audio via deployed API)")
    tx_wav = Path(args.tx_wav) if args.tx_wav else wavs[0]
    if not tx_wav.is_absolute():
        tx_wav = rec_dir / tx_wav
    if not tx_wav.exists():
        print(f"[send-audio][error] TX WAV not found: {tx_wav}", file=sys.stderr)
        return 4
    with tx_wav.open("rb") as f:
        files = {"file": (tx_wav.name, f, "audio/wav")}
        params = {"frequency_hz": str(args.tx_frequency_hz), "mode": args.tx_mode}
        r = httpx.post(f"{base}/radio/send-audio", headers=_h(token), files=files, params=params, timeout=120.0)
    if r.status_code >= 400:
        print(f"[send-audio][error] HTTP {r.status_code}: {r.text[:200]}", file=sys.stderr)
    else:
        print("[send-audio]", r.json())

    _print_step("HackRF TX (send-tts via deployed API)")
    r = httpx.post(
        f"{base}/radio/send-tts",
        headers=_h(token),
        json={"message": "RadioShaq live demo. This is TTS over the radio path.", "frequency_hz": args.tx_frequency_hz, "mode": args.tx_mode},
        timeout=120.0,
    )
    print(f"[send-tts] status={r.status_code}")
    if r.status_code < 400:
        print("[send-tts]", r.json())
    else:
        print("[send-tts][error]", r.text[:200])

    _print_step("Transcripts (recent)")
    r = httpx.get(f"{base}/transcripts", headers=_h(token), params={"limit": 20}, timeout=30.0)
    r.raise_for_status()
    data = r.json()
    summary = {
        "count": data.get("count"),
        "ids": [t.get("id") for t in data.get("transcripts", [])[:5]],
    }
    print("[transcripts] summary:", json.dumps(summary, indent=2))

    print(
        "\nDemo run complete.\n"
        "You should now be able to:\n"
        "  - See uploaded and injected transcripts in /transcripts and the web UI\n"
        "  - Confirm SMS/WhatsApp deliveries (if configured)\n"
        "  - Hear HackRF TX activity on the configured frequency.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

