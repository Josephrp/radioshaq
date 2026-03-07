#!/usr/bin/env python3
"""
User injection script for RadioShaq demo: inject message (and optional audio path) into the RX path.

Use for:
- Two local machines + one remote: simulate one user "emitting" so another can receive.
- Audio pipeline: run STT on an audio file, then pass the text (and optional audio_path) here.

Usage:
  # Inject text only (no audio file)
  python scripts/demo/inject_audio.py --base-url http://localhost:8000 --text "K5ABC de W1XYZ emergency" --band 40m --source-callsign K5ABC

  # With audio file path (stored in transcript metadata)
  python scripts/demo/inject_audio.py --base-url http://localhost:8000 --text "Transcribed message" --band 40m --audio-path /path/to/recording.wav

  # Inject and then relay to another band (store both)
  python scripts/demo/inject_audio.py --base-url http://localhost:8000 --text "Relay this to 2m" --band 40m --relay-to-band 2m --source-callsign K5ABC --destination-callsign W1XYZ

  # Get token by subject/role (no existing token)
  python scripts/demo/inject_audio.py --base-url http://REMOTE:8000 --subject op1 --role field --text "Hello" --band 2m

  # ASR: transcribe with Voxtral (RadioShaq HF model) then inject (uv sync --extra audio)
  python scripts/demo/inject_audio.py --base-url http://localhost:8000 --subject op1 --audio-path recording.wav --stt --asr voxtral --band 40m

  # TTS: generate speech from text with ElevenLabs and save (set ELEVENLABS_API_KEY)
  python scripts/demo/inject_audio.py --text "K5ABC de W1XYZ" --tts elevenlabs --tts-out output.mp3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    httpx = None


def transcribe_audio_whisper(audio_path: str) -> str:
    """Return transcribed text using Whisper (fallback when voxtral not used)."""
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(audio_path)
    try:
        import whisper
        model = whisper.load_model("base")
        result = model.transcribe(str(path), fp16=False)
        return (result.get("text") or "").strip()
    except ImportError:
        raise RuntimeError(
            "Install whisper: pip install openai-whisper. Or use --asr voxtral with uv sync --extra audio."
        ) from None


def transcribe_audio(audio_path: str, asr: str = "voxtral") -> str:
    """Return transcribed text. asr: voxtral (RadioShaq Voxtral ASR) or whisper."""
    if asr == "voxtral":
        try:
            from radioshaq.audio.asr import transcribe_audio_voxtral
            return transcribe_audio_voxtral(audio_path, language="en")
        except ImportError:
            raise RuntimeError(
                "Install ASR deps: uv sync --extra audio (transformers, peft, mistral-common[audio])."
            ) from None
    return transcribe_audio_whisper(audio_path)


def get_token(base_url: str, subject: str, role: str = "field", station_id: str | None = None) -> str:
    r = httpx.post(
        f"{base_url.rstrip('/')}/auth/token",
        params={"subject": subject, "role": role, "station_id": station_id or ""},
        timeout=10.0,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def inject_message(
    base_url: str,
    token: str,
    text: str,
    band: str | None = None,
    frequency_hz: float = 0.0,
    mode: str = "PSK31",
    source_callsign: str | None = None,
    destination_callsign: str | None = None,
    audio_path: str | None = None,
) -> dict:
    url = f"{base_url.rstrip('/')}/inject/message"
    payload = {
        "text": text,
        "mode": mode,
        "frequency_hz": frequency_hz,
    }
    if band:
        payload["band"] = band
    if source_callsign:
        payload["source_callsign"] = source_callsign
    if destination_callsign:
        payload["destination_callsign"] = destination_callsign
    if audio_path:
        payload["audio_path"] = audio_path
    r = httpx.post(url, json=payload, headers={"Authorization": f"Bearer {token}"}, timeout=10.0)
    r.raise_for_status()
    return r.json()


def relay_message(
    base_url: str,
    token: str,
    message: str,
    source_band: str,
    target_band: str,
    source_frequency_hz: float = 0.0,
    target_frequency_hz: float = 0.0,
    source_callsign: str = "UNKNOWN",
    destination_callsign: str | None = None,
) -> dict:
    url = f"{base_url.rstrip('/')}/messages/relay"
    payload = {
        "message": message,
        "source_band": source_band,
        "target_band": target_band,
        "source_callsign": source_callsign,
    }
    if source_frequency_hz > 0:
        payload["source_frequency_hz"] = source_frequency_hz
    if target_frequency_hz > 0:
        payload["target_frequency_hz"] = target_frequency_hz
    if destination_callsign:
        payload["destination_callsign"] = destination_callsign
    r = httpx.post(url, json=payload, headers={"Authorization": f"Bearer {token}"}, timeout=10.0)
    r.raise_for_status()
    return r.json()


# Default frequencies (Hz) per band if not provided
BAND_DEFAULT_FREQ = {
    "40m": 7.215e6,
    "20m": 14.1e6,
    "2m": 146.52e6,
    "70cm": 446.0e6,
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Inject message (and optional audio) for RadioShaq demo")
    ap.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    ap.add_argument("--token", help="Bearer token (if not using --subject)")
    ap.add_argument("--subject", help="User subject for /auth/token")
    ap.add_argument("--role", default="field", help="Role for token")
    ap.add_argument("--station-id", default=None, help="Station ID for token")
    ap.add_argument("--text", "-t", default=None, help="Message text to inject (required unless --audio-path + --stt)")
    ap.add_argument("--band", "-b", default=None, help="Band (e.g. 40m, 2m)")
    ap.add_argument("--frequency-hz", type=float, default=0, help="Frequency in Hz")
    ap.add_argument("--mode", default="PSK31", help="Mode")
    ap.add_argument("--source-callsign", default=None, help="Source callsign")
    ap.add_argument("--destination-callsign", default=None, help="Destination callsign")
    ap.add_argument("--audio-path", default=None, help="Path to audio file (stored with transcript)")
    ap.add_argument("--stt", action="store_true", help="Transcribe --audio-path and use as message text")
    ap.add_argument("--asr", choices=("voxtral", "whisper"), default="voxtral", help="ASR: voxtral (RadioShaq Voxtral) or whisper")
    ap.add_argument("--tts", choices=("elevenlabs",), default=None, help="TTS: generate speech with ElevenLabs from text")
    ap.add_argument("--tts-voice-id", default="21m00Tcm4TlvDq8ikWAM", help="ElevenLabs voice ID (default: Rachel)")
    ap.add_argument("--tts-out", default=None, help="Output path for TTS audio (e.g. output.mp3)")
    ap.add_argument("--tts-model", default="eleven_multilingual_v2", help="ElevenLabs model id")
    ap.add_argument("--relay-to-band", default=None, help="After inject, relay message to this band and store both")
    ap.add_argument("--relay-target-freq", type=float, default=0, help="Target frequency for relay (Hz)")
    args = ap.parse_args()

    if not httpx:
        print("pip install httpx", file=sys.stderr)
        return 1

    token = args.token
    if not token and args.subject:
        token = get_token(args.base_url, args.subject, args.role, args.station_id)

    text = args.text
    if args.audio_path and args.stt:
        print(f"Transcribing audio with {args.asr}...", file=sys.stderr)
        text = transcribe_audio(args.audio_path, asr=args.asr)
        print(f"Transcribed: {text[:80]}...", file=sys.stderr)
    if not text:
        print("Provide --text or --audio-path with --stt", file=sys.stderr)
        return 1

    # TTS with ElevenLabs (optional; can run without token for TTS-only)
    if args.tts == "elevenlabs":
        try:
            from radioshaq.audio.tts import text_to_speech_elevenlabs
            out_path = args.tts_out or "tts_output.mp3"
            text_to_speech_elevenlabs(text, voice_id=args.tts_voice_id, model_id=args.tts_model, output_path=out_path)
            print(f"TTS saved: {out_path}", file=sys.stderr)
        except Exception as e:
            print(f"TTS failed: {e}", file=sys.stderr)
            return 1
        if not token:
            return 0  # TTS-only, no inject

    if not token:
        print("Provide --token or --subject for inject/relay", file=sys.stderr)
        return 1

    freq = args.frequency_hz or (BAND_DEFAULT_FREQ.get(args.band or "") or 0)

    # Inject
    out = inject_message(
        args.base_url,
        token,
        text,
        band=args.band,
        frequency_hz=freq,
        mode=args.mode,
        source_callsign=args.source_callsign,
        destination_callsign=args.destination_callsign,
        audio_path=args.audio_path,
    )
    print("Inject:", out)

    if args.relay_to_band and args.band:
        relay_out = relay_message(
            args.base_url,
            token,
            text,
            source_band=args.band,
            target_band=args.relay_to_band,
            source_frequency_hz=freq,
            target_frequency_hz=args.relay_target_freq or BAND_DEFAULT_FREQ.get(args.relay_to_band, 0),
            source_callsign=args.source_callsign or "UNKNOWN",
            destination_callsign=args.destination_callsign,
        )
        print("Relay:", relay_out)

    return 0


if __name__ == "__main__":
    sys.exit(main())
