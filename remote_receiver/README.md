# SHAKODS Remote Receiver

Remote receiver station: SDR interface, JWT auth, and HQ upload. Deploy on Raspberry Pi or similar.

## Setup

```bash
uv sync
# RTL-SDR: uv sync --extra sdr
# HackRF:  uv sync --extra hackrf
```

## Environment

| Variable | Description | Default |
|----------|-------------|---------|
| `SDR_TYPE` | Backend: `rtlsdr` or `hackrf` | `rtlsdr` |
| `RTLSDR_INDEX` | RTL-SDR device index | `0` |
| `RTLSDR_SAMPLE_RATE` | RTL-SDR sample rate (Hz) | `2400000` |
| `HACKRF_INDEX` | HackRF device index (when `SDR_TYPE=hackrf`) | `0` |
| `HACKRF_SERIAL` | HackRF serial number (optional) | — |
| `HACKRF_SAMPLE_RATE` | HackRF sample rate (Hz) | `10000000` |
| `JWT_SECRET` | Secret for JWT auth | — |
| `STATION_ID` | Unique ID for this receiver | — |
| `HQ_URL` | SHAKODS HQ API base URL | — |
| `HQ_TOKEN` | Optional JWT/API token for HQ uploads | — |

## Run

```bash
uv run uvicorn receiver.server:app --host 0.0.0.0 --port 8765
```
