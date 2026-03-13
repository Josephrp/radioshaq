#!/usr/bin/env python3
"""
Connect to the remote receiver WebSocket to stream live from the HackRF (or RTL-SDR).

The receiver tunes to the given frequency and streams signal samples. Each sample
is also uploaded to HQ when HQ_URL and HQ_TOKEN are set on the receiver. Use this
script to trigger a live SDR stream and see signal strength in real time.

Prerequisites:
  - HQ (main API) running and receiver service running with SDR_TYPE=hackrf (or rtlsdr).
  - Same JWT_SECRET on HQ and receiver. Receiver needs HQ_URL and HQ_TOKEN to upload.

Usage:
  # Get token from HQ, stream 145 MHz for 60 seconds (receiver at localhost:8765)
  uv run python scripts/demo/stream_receiver_ws.py --hq-url http://localhost:8000 --receiver-url http://localhost:8765 --frequency 145000000 --duration 60

  # Stream 2m calling frequency, 30 seconds
  uv run python scripts/demo/stream_receiver_ws.py --frequency 145520000 --duration 30

  # Use an existing token (e.g. for receiver that verifies tokens from HQ)
  uv run python scripts/demo/stream_receiver_ws.py --token $TOKEN --receiver-url http://localhost:8765 --frequency 145000000 --duration 20
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import wave
from urllib.parse import urlparse

try:
    import httpx
except ImportError:
    httpx = None
try:
    import websockets
except ImportError:
    websockets = None


def get_token(base_url: str, subject: str = "demo-op1", role: str = "field", station_id: str = "DEMO-01") -> str:
    if not httpx:
        raise RuntimeError("httpx required; install with uv sync")
    r = httpx.post(
        f"{base_url.rstrip('/')}/auth/token",
        params={"subject": subject, "role": role, "station_id": station_id},
        timeout=10.0,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def receiver_ws_url(receiver_url: str, token: str, frequency_hz: int, duration_seconds: int) -> str:
    parsed = urlparse(receiver_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    netloc = parsed.netloc or parsed.path
    base = f"{scheme}://{netloc}"
    path = "/ws/stream"
    q = f"token={token}&frequency_hz={frequency_hz}&duration_seconds={duration_seconds}"
    return f"{base}{path}?{q}"


async def run_stream(ws_url: str, duration_seconds: int) -> None:
    if not websockets:
        raise RuntimeError("websockets required; install with uv sync")
    print(f"\n[stream] Connecting to receiver stream for {duration_seconds}s ...")
    print(
        "[stream] Each line below is one received signal sample: "
        "timestamp, signal_strength (dB), and any decoded text."
    )
    print(
        "[stream] If the receiver is configured with HQ_URL + HQ_TOKEN, "
        "each sample is also uploaded to HQ (/receiver/upload)."
    )
    count = 0
    error_count = 0
    async with websockets.connect(ws_url, close_timeout=2) as ws:
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=duration_seconds + 5)
                if isinstance(msg, str):
                    import json
                    data = json.loads(msg)
                else:
                    continue
                if data.get("type") == "error":
                    error_count += 1
                    print(f"[stream][error] {data.get('message', data)}")
                    break
                if data.get("type") == "audio":
                    # handled in main() when wav writer is enabled; ignore here
                    continue
                if data.get("type") == "signal":
                    count += 1
                    ss = data.get("signal_strength", data.get("signal_strength_db"))
                    dec = data.get("decoded", data.get("decoded_text")) or ""
                    ts = data.get("timestamp", "")
                    line = f"[stream][{count}] ts={ts}  signal_strength={ss} dB  decoded={dec!r}"
                    print(line)
        except asyncio.TimeoutError:
            print("[stream] Timed out waiting for more data from receiver.")
        except websockets.exceptions.ConnectionClosed as e:
            print(f"[stream] Connection closed by receiver: {e}")
    if count == 0:
        print(
            "\n[stream] Stream ended but no signal samples were received.\n"
            "        Check that the receiver process is running, the frequency is valid, "
            "and that your HQ/receiver configuration matches the demo instructions."
        )
    else:
        print(f"\n[stream] Stream ended. Received {count} signal samples total.")
    if error_count:
        print(f"[stream] Encountered {error_count} error message(s) from receiver.")


async def run_stream_to_wav(ws_url: str, duration_seconds: int, wav_out: str) -> None:
    if not websockets:
        raise RuntimeError("websockets required; install with uv sync")
    print(
        f"\n[stream+wav] Connecting to receiver stream for {duration_seconds}s, "
        f"writing demodulated audio to {wav_out!r} ..."
    )
    print(
        "[stream+wav] You should also see periodic signal_strength lines with the "
        "approximate audio duration written so far."
    )
    frames = 0
    sample_rate = 48_000
    error_count = 0
    with wave.open(wav_out, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # int16
        wf.setframerate(sample_rate)
        async with websockets.connect(ws_url, close_timeout=2) as ws:
            try:
                while True:
                    msg = await asyncio.wait_for(ws.recv(), timeout=duration_seconds + 5)
                    if not isinstance(msg, str):
                        continue
                    import json
                    data = json.loads(msg)
                    if data.get("type") == "error":
                        error_count += 1
                        print(f"[stream+wav][error] {data.get('message', data)}")
                        break
                    if data.get("type") == "audio":
                        import base64
                        sr = int(data.get("sample_rate_hz", sample_rate))
                        if sr != sample_rate:
                            # WAV headers cannot be updated safely mid-stream; keep first rate.
                            # If the receiver is configured differently, re-run with consistent settings.
                            sr = sample_rate
                        b = base64.b64decode(data.get("audio_b64", "") or b"")
                        if b:
                            wf.writeframes(b)
                            frames += len(b) // 2
                        continue
                    if data.get("type") == "signal":
                        ss = data.get("signal_strength", data.get("signal_strength_db"))
                        ts = data.get("timestamp", "")
                        if frames and frames % (sample_rate * 1) < 960:  # roughly once/sec
                            print(
                                "[stream+wav] "
                                f"ts={ts}  signal_strength={ss} dB  "
                                f"audio_written={(frames / sample_rate):.1f}s"
                            )
            except asyncio.TimeoutError:
                print("[stream+wav] Timed out waiting for more data from receiver.")
            except websockets.exceptions.ConnectionClosed as e:
                print(f"[stream+wav] Connection closed by receiver: {e}")
    print(
        f"\n[stream+wav] Stream ended. "
        f"Wrote ~{(frames / sample_rate):.1f}s audio to {wav_out!r}."
    )
    if error_count:
        print(f"[stream+wav] Encountered {error_count} error message(s) from receiver.")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Stream from remote receiver (HackRF/RTL-SDR) via WebSocket; triggers uploads to HQ."
    )
    ap.add_argument("--hq-url", default="http://localhost:8000", help="HQ API base URL (to get token)")
    ap.add_argument("--receiver-url", default="http://localhost:8765", help="Receiver service base URL")
    ap.add_argument("--frequency", type=int, default=145_000_000, help="Frequency in Hz (e.g. 145000000 for 145 MHz)")
    ap.add_argument("--duration", type=int, default=60, help="Stream duration in seconds")
    ap.add_argument("--mode", default="", help="Receiver demod mode: nfm|am|usb|lsb|cw (optional)")
    ap.add_argument("--token", default="", help="Use this token instead of fetching from HQ")
    ap.add_argument("--subject", default="demo-op1", help="Subject for token request")
    ap.add_argument("--role", default="field", help="Role for token request")
    ap.add_argument("--station-id", default="DEMO-01", help="Station ID for token request")
    ap.add_argument("--wav-out", default="", help="If set, write received audio frames to this WAV file")
    args = ap.parse_args()

    if not websockets:
        print("pip install websockets (or uv sync)", file=sys.stderr)
        return 1

    print("Remote receiver live stream demo")
    print("-------------------------------")
    print(f"HQ URL:        {args.hq_url}")
    print(f"Receiver URL:  {args.receiver_url}")
    print(f"Frequency:     {args.frequency} Hz (~{args.frequency / 1e6:.3f} MHz)")
    print(f"Duration:      {args.duration} s")
    if args.mode:
        print(f"Mode override: {args.mode}")
    if args.wav_out:
        print(f"WAV output:    {args.wav_out}")
    print()

    token = args.token
    if not token and httpx:
        try:
            token = get_token(args.hq_url, args.subject, args.role, args.station_id)
            print("Fetched demo token from HQ via /auth/token.")
        except Exception as e:
            print(f"Failed to get token from HQ: {e}", file=sys.stderr)
            return 1
    if not token:
        if not httpx:
            print(
                "Provide --token explicitly, or install httpx so the script can "
                "fetch a token from HQ (uv sync).",
                file=sys.stderr,
            )
        else:
            print("Provide --token or ensure --hq-url is reachable to get a token.", file=sys.stderr)
        return 1
    if args.token:
        print("Using token provided via --token.")

    ws_url = receiver_ws_url(args.receiver_url, token, args.frequency, args.duration)
    if args.mode:
        ws_url = ws_url + f"&mode={args.mode}"
    # Do not print the full URL since it contains the bearer token; just confirm target host.
    parsed = urlparse(args.receiver_url)
    host_display = parsed.netloc or parsed.path or args.receiver_url
    print(f"Receiver WebSocket target: {host_display} (/ws/stream)")
    print("Starting stream; watch below for signal_strength lines and, if configured, HQ uploads.\n")
    if args.wav_out:
        asyncio.run(run_stream_to_wav(ws_url, args.duration, args.wav_out))
    else:
        asyncio.run(run_stream(ws_url, args.duration))
    print(
        "\nTip: In a separate terminal, you can call /transcripts on HQ to verify that "
        "receiver uploads were stored and injected when receiver_upload_store/inject are enabled."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
