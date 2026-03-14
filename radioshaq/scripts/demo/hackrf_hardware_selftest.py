#!/usr/bin/env python3
"""HackRF hardware self-test for RadioShaq.

This script exercises HackRF RX (I/Q capture + analog demod) and optionally TX
using the project's SDR TX stack. It is designed for *real hardware*.

Safety:
  - TX is disabled by default. Use --tx to enable.
  - Use a dummy load / attenuator and a legal frequency for your region.
"""

from __future__ import annotations

import argparse
import asyncio
import math
import sys
import time
import wave
from pathlib import Path

import numpy as np


def _write_wav_mono_pcm16(path: Path, pcm16: bytes, sample_rate_hz: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(int(sample_rate_hz))
        wf.writeframes(pcm16)


async def rx_test(
    *,
    frequency_hz: float,
    sample_rate_hz: int,
    audio_rate_hz: int,
    bfo_hz: float,
    seconds: float,
    out_dir: Path,
) -> int:
    """Run RX for each supported analog mode and write WAVs."""
    try:
        from radioshaq.remote_receiver.backends.hackrf_backend import HackRFBackend
    except Exception as e:
        print(f"Failed to import HackRF backend: {e}", file=sys.stderr)
        return 2

    backend = HackRFBackend(device_index=0, serial_number=None, sample_rate=sample_rate_hz)
    await backend.initialize()
    await backend.set_frequency(frequency_hz)

    modes = ["nfm", "am", "usb", "lsb", "cw"]
    written = 0
    for mode in modes:
        print(f"[RX] mode={mode} freq={frequency_hz:.0f}Hz rf_rate={sample_rate_hz} audio_rate={audio_rate_hz}")
        await backend.configure(mode=mode, audio_rate_hz=audio_rate_hz, bfo_hz=bfo_hz)
        pcm = bytearray()
        start = time.time()
        async for sample in backend.receive(seconds):
            if sample.raw_data:
                pcm.extend(sample.raw_data)
            if (time.time() - start) >= seconds:
                break
        if pcm:
            wav_path = out_dir / f"rx_{int(frequency_hz)}_{mode}.wav"
            _write_wav_mono_pcm16(wav_path, bytes(pcm), audio_rate_hz)
            print(f"  wrote {wav_path} ({len(pcm)} bytes)")
            written += 1
        else:
            print("  no audio frames produced (check SciPy installed and mode supported).")

    await backend.close()
    return 0 if written else 1


def _tone(audio_rate_hz: int, hz: float, duration_sec: float) -> np.ndarray:
    n = max(1, int(audio_rate_hz * duration_sec))
    t = np.arange(n, dtype=np.float32) / float(audio_rate_hz)
    return (0.3 * np.sin(2.0 * math.pi * float(hz) * t)).astype(np.float32)


async def tx_test(
    *,
    frequency_hz: float,
    duration_sec: float,
    rf_rate_hz: int,
) -> int:
    """Transmit short bursts in multiple modes (requires explicit --tx)."""
    try:
        from radioshaq.radio.sdr_tx import HackRFTransmitter
        from radioshaq.radio.fm import nfm_modulate
        from radioshaq.radio.analog_mod import am_modulate, ssb_modulate, cw_tone_iq
    except Exception as e:
        print(f"Failed to import TX stack: {e}", file=sys.stderr)
        return 2

    tx = HackRFTransmitter(
        device_index=0,
        serial_number=None,
        max_gain=20,
        allow_bands_only=True,
        audit_log_path=None,
        restricted_region="FCC",
        band_plan_source=None,
    )

    print(f"[TX] tone {duration_sec}s @ {frequency_hz:.0f}Hz")
    await tx.transmit_tone(frequency_hz, duration_sec=duration_sec, sample_rate=rf_rate_hz)

    audio_rate = 48_000
    audio = _tone(audio_rate, 1000.0, duration_sec)

    print(f"[TX] NFM IQ {duration_sec}s @ {frequency_hz:.0f}Hz")
    iq = nfm_modulate(audio, audio_rate, rf_rate_hz, deviation_hz=2_500.0)
    await tx.transmit_iq(frequency_hz, iq, sample_rate=rf_rate_hz, occupied_bandwidth_hz=12_500.0)

    print(f"[TX] AM IQ {duration_sec}s @ {frequency_hz:.0f}Hz")
    iq = am_modulate(audio, audio_rate, rf_rate_hz)
    await tx.transmit_iq(frequency_hz, iq, sample_rate=rf_rate_hz, occupied_bandwidth_hz=10_000.0)

    print(f"[TX] USB IQ {duration_sec}s @ {frequency_hz:.0f}Hz")
    iq = ssb_modulate(audio, audio_rate, rf_rate_hz, sideband="USB")
    await tx.transmit_iq(frequency_hz, iq, sample_rate=rf_rate_hz, occupied_bandwidth_hz=3_000.0)

    print(f"[TX] LSB IQ {duration_sec}s @ {frequency_hz:.0f}Hz")
    iq = ssb_modulate(audio, audio_rate, rf_rate_hz, sideband="LSB")
    await tx.transmit_iq(frequency_hz, iq, sample_rate=rf_rate_hz, occupied_bandwidth_hz=3_000.0)

    print(f"[TX] CW carrier {duration_sec}s @ {frequency_hz:.0f}Hz")
    iq = cw_tone_iq(duration_sec=duration_sec, rf_rate_hz=rf_rate_hz)
    await tx.transmit_iq(frequency_hz, iq, sample_rate=rf_rate_hz, occupied_bandwidth_hz=500.0)

    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="HackRF RX/TX hardware self-test for RadioShaq.")
    ap.add_argument("--frequency-hz", type=float, default=145_520_000.0, help="Center frequency in Hz")
    ap.add_argument("--rf-sample-rate", type=int, default=2_000_000, help="RF sample rate for RX/TX")
    ap.add_argument("--audio-rate", type=int, default=48_000, help="Demodulated audio rate")
    ap.add_argument("--bfo-hz", type=float, default=1500.0, help="BFO frequency for USB/LSB/CW demod")
    ap.add_argument("--rx-seconds", type=float, default=2.0, help="Seconds per RX mode")
    ap.add_argument("--out-dir", default="hackrf_selftest_out", help="Directory to write RX WAVs")
    ap.add_argument("--tx", action="store_true", help="Enable TX tests (DANGEROUS; use dummy load/attenuator)")
    ap.add_argument("--tx-seconds", type=float, default=0.5, help="Seconds per TX burst")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)

    async def _run() -> int:
        rc = await rx_test(
            frequency_hz=args.frequency_hz,
            sample_rate_hz=args.rf_sample_rate,
            audio_rate_hz=args.audio_rate,
            bfo_hz=args.bfo_hz,
            seconds=args.rx_seconds,
            out_dir=out_dir,
        )
        if rc != 0:
            print("RX test did not produce WAVs; continuing to TX only if enabled.", file=sys.stderr)
        if args.tx:
            print(
                "TX ENABLED. Ensure you are legal to transmit and using a dummy load/attenuation.",
                file=sys.stderr,
            )
            trc = await tx_test(
                frequency_hz=args.frequency_hz,
                duration_sec=args.tx_seconds,
                rf_rate_hz=args.rf_sample_rate,
            )
            rc = rc or trc
        else:
            print("TX disabled (pass --tx to enable).")
        return rc

    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())

