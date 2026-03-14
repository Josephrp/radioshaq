# HackRF TX audio demo (send-audio only)

This demo exercises the **SDR TX path** only: `POST /radio/send-audio` with a WAV file, compliance checks, and **real HackRF** transmission. No Twilio, no from-audio pipeline. Live runs require **real HackRF hardware** (no stub).

## What you get

- **Compliance**: `is_tx_allowed` and `is_tx_spectrum_allowed` run before TX; out-of-band or restricted frequencies are rejected.
- **NFM/AM/USB/LSB/CW**: Mode is passed through to the TX agent; NFM is typical for voice.
- **HackRF**: Real RF output when `radio.sdr_tx_enabled=true` and a HackRF device is attached (use dummy load or antenna on a legal frequency). Use `--require-hardware` so the script exits non-zero if SDR TX is not configured.

## Prerequisites

- **HQ API** running with:
  - `radio.sdr_tx_enabled=true`, `radio.sdr_tx_backend=hackrf`.
  - HackRF connected (e.g. via WSL + usbipd when on Windows).
- **voice_tx extra**: `uv sync --extra voice_tx` (for WAV read and modulation).
- **Legal frequency**: Use an amateur band or other allowed frequency in your region; default in script is 145.52 MHz (2 m).
- **JWT** via `POST /auth/token`.

## Steps

### 1. Configure and start HQ

```bash
export RADIOSHAQ_RADIO__SDR_TX_ENABLED=true
export RADIOSHAQ_RADIO__SDR_TX_BACKEND=hackrf
uv run radioshaq run-api
```

### 2. Run the TX audio demo script

Provide a WAV file (e.g. from [option-c-recording-scripts.md](option-c-recording-scripts.md) `05_tx_payload.wav`).

```bash
cd radioshaq
uv run python scripts/demo/run_hackrf_tx_audio_demo.py \
  --base-url http://localhost:8000 \
  --wav scripts/demo/recordings/05_tx_payload.wav \
  --frequency-hz 145520000 \
  --mode NFM \
  --require-hardware
```

- **Expected**: Script calls `POST /radio/send-audio`; response includes `success: true` and notes (e.g. "SDR NFM voice (HackRF)").
- **Success criteria**: HTTP 200 and `success: true` in JSON. With `--require-hardware`, the script first checks `GET /radio/status` for `sdr_tx_available` and exits non-zero if HackRF is not configured. If frequency is disallowed, you get 200 with `success: false` and a compliance note.

### 3. Safety

- Use a **dummy load** or known-safe antenna.
- Ensure **frequency and mode** are legal in your jurisdiction.
- Script does not key the transmitter indefinitely; it sends the WAV once.

## See also

- [demo-hackrf-full.md](demo-hackrf-full.md) — Full RX + TX + receiver.
- [coverage-matrix.md](coverage-matrix.md) — HackRF TX row.
