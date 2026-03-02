#!/usr/bin/env python3
"""
End-to-end demo: inject message on one band, relay to another, poll transcripts.

Prerequisites:
  - API running (e.g. uv run python -m shakods.api.server)
  - Postgres running and migrated (for transcript storage)

Usage:
  uv run python scripts/demo/run_demo.py
  uv run python scripts/demo/run_demo.py --base-url http://REMOTE:8000
"""

from __future__ import annotations

import argparse
import sys
import time

try:
    import httpx
except ImportError:
    httpx = None


def get_token(base_url: str, subject: str = "demo-op1", role: str = "field", station_id: str = "DEMO-01") -> str:
    r = httpx.post(
        f"{base_url.rstrip('/')}/auth/token",
        params={"subject": subject, "role": role, "station_id": station_id},
        timeout=10.0,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def inject(base_url: str, token: str, text: str, band: str, source: str, dest: str | None) -> dict:
    r = httpx.post(
        f"{base_url.rstrip('/')}/inject/message",
        json={
            "text": text,
            "band": band,
            "frequency_hz": 7.215e6 if band == "40m" else 146.52e6,
            "mode": "PSK31",
            "source_callsign": source,
            "destination_callsign": dest,
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )
    r.raise_for_status()
    return r.json()


def relay(base_url: str, token: str, message: str, source_band: str, target_band: str, source: str, dest: str | None) -> dict:
    payload = {
        "message": message,
        "source_band": source_band,
        "target_band": target_band,
        "source_callsign": source,
        "source_frequency_hz": 7.215e6 if source_band == "40m" else 146.52e6,
        "target_frequency_hz": 146.52e6 if target_band == "2m" else 7.215e6,
    }
    if dest:
        payload["destination_callsign"] = dest
    r = httpx.post(
        f"{base_url.rstrip('/')}/messages/relay",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )
    r.raise_for_status()
    return r.json()


def search_transcripts(base_url: str, token: str, band: str | None = None, callsign: str | None = None, limit: int = 20) -> dict:
    params = {"limit": limit}
    if band:
        params["band"] = band
    if callsign:
        params["callsign"] = callsign
    r = httpx.get(
        f"{base_url.rstrip('/')}/transcripts",
        params=params,
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )
    r.raise_for_status()
    return r.json()


def main() -> int:
    ap = argparse.ArgumentParser(description="Run inject → relay → poll transcripts demo")
    ap.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    ap.add_argument("--no-relay", action="store_true", help="Only inject, do not relay")
    ap.add_argument("--no-poll", action="store_true", help="Do not poll /transcripts at end")
    args = ap.parse_args()

    if not httpx:
        print("pip install httpx", file=sys.stderr)
        return 1

    base = args.base_url.rstrip("/")
    print(f"Base URL: {base}")
    print("0. Checking API health...")
    try:
        r = httpx.get(f"{base}/health", timeout=5.0)
        r.raise_for_status()
    except Exception as e:
        print(f"   API not reachable: {e}. Start with: uv run python -m shakods.api.server", file=sys.stderr)
        return 1
    print("   OK")
    print("1. Getting token...")
    token = get_token(base, "demo-op1", "field", "DEMO-01")
    print("   OK")

    message = "K5ABC de W1XYZ emergency traffic need relay to 2m"
    source_callsign = "K5ABC"
    dest_callsign = "W1XYZ"

    print("2. Injecting message (as received on 40m)...")
    inj = inject(base, token, message, "40m", source_callsign, dest_callsign)
    print(f"   {inj}")

    if not args.no_relay:
        print("3. Relaying 40m -> 2m (store both transcripts)...")
        rel = relay(base, token, message, "40m", "2m", source_callsign, dest_callsign)
        sid, rid = rel.get("source_transcript_id"), rel.get("relayed_transcript_id")
        if sid is not None and rid is not None:
            print(f"   source_transcript_id={sid} relayed_transcript_id={rid}")
        else:
            print("   (no DB: relay accepted but not stored - start Postgres + migrations for storage)")
    else:
        print("3. Skipping relay (--no-relay)")
        rel = None

    if not args.no_poll and (rel or args.no_relay):
        print("4. Polling /transcripts (band=2m, then callsign=W1XYZ)...")
        time.sleep(0.3)
        if not args.no_relay:
            by_band = search_transcripts(base, token, band="2m")
            print(f"   Transcripts on 2m: {by_band.get('count', 0)}")
            for t in (by_band.get("transcripts") or [])[:3]:
                print(f"     - [{t.get('extra_data', {}).get('band')}] {t.get('source_callsign')} -> {t.get('destination_callsign')}: {t.get('transcript_text', '')[:60]}...")
        by_callsign = search_transcripts(base, token, callsign=dest_callsign)
        print(f"   Transcripts for {dest_callsign}: {by_callsign.get('count', 0)}")
        for t in (by_callsign.get("transcripts") or [])[:3]:
            print(f"     - id={t.get('id')} band={t.get('extra_data', {}).get('band')} relay_from={t.get('extra_data', {}).get('relay_from_transcript_id')} text={t.get('transcript_text', '')[:50]}...")
    else:
        print("4. Skipping poll (--no-poll)")

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
