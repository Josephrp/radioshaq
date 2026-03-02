# SHAKODS Remote Receiver

Remote receiver station: SDR interface, JWT auth, and HQ upload. Deploy on Raspberry Pi or similar.

## Setup

```bash
uv sync
# Optional SDR support: uv sync --extra sdr
```

## Run

```bash
uv run uvicorn receiver.server:app --host 0.0.0.0 --port 8765
```

Set `JWT_SECRET`, `STATION_ID`, `HQ_URL` (and optionally `RTLSDR_INDEX`).
