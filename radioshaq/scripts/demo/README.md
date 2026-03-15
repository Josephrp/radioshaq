# Demo scripts

All API calls (inject, relay, transcripts) require a **Bearer JWT**. The demo scripts obtain a token automatically when you pass `--subject` (or `--token`). See [docs/auth.md](../../docs/auth.md) for full auth details.

## Authentication (exact commands)

**No auth** is required to obtain a token; use `POST /auth/token` with a subject and role.

**Bash (save token for curl):**

```bash
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/token?subject=op1&role=field&station_id=STATION-01" | jq -r .access_token)
# Use: curl -H "Authorization: Bearer $TOKEN" ...
```

**PowerShell:**

```powershell
$r = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/auth/token?subject=op1&role=field&station_id=STATION-01"
$TOKEN = $r.access_token
# Use: -Headers @{ Authorization = "Bearer $TOKEN" }
```

**For a remote API**, replace `localhost:8000` with the remote base URL (e.g. `http://REMOTE:8000`).

| Service / script | How it gets a token |
| --- | --- |
| **run_demo.py** | Calls `/auth/token` with `subject=demo-op1`, `role=field`, `station_id=DEMO-01`. No flags needed. |
| **inject_audio.py** | Pass `--subject op1` (and optional `--role field`, `--station-id STATION-01`). Script calls `/auth/token` then uses the token for inject/relay. For **TTS-only** (no inject), no token needed. |
| **curl / manual** | Call `POST /auth/token?...` once, then set `Authorization: Bearer <access_token>` on every request. |
| **stream_receiver_ws.py** | Gets token from `--hq-url` (or use `--token`) to connect to receiver WebSocket. |

---

## Full HackRF demo (HQ + receiver + live stream)

For a **complete demo** with your HackRF: HQ stores receiver uploads, receiver streams from the SDR, and inject/relay/transcripts all work. Step-by-step:

**[docs/demo-hackrf-full.md](../../docs/demo-hackrf-full.md)** — Prerequisites, database, HQ config (`receiver_upload_store` / `receiver_upload_inject`), starting the receiver with `HQ_TOKEN`, then triggering a live stream and optionally running inject/relay.

**stream_receiver_ws.py** — Connects to the remote receiver’s WebSocket so the HackRF actually runs and uploads to HQ:

```bash
uv run python scripts/demo/stream_receiver_ws.py --hq-url http://localhost:8000 --receiver-url http://localhost:8765 --frequency 145000000 --duration 30
```

If the receiver is started with `RECEIVER_MODE=nfm`, you can also record demodulated audio:

```bash
uv run python scripts/demo/stream_receiver_ws.py --frequency 145000000 --duration 30 --wav-out out.wav
```

---

## Quick run (full demo)

With the API running (e.g. in another terminal):

```bash
# Terminal 1
uv run python -m radioshaq.api.server

# Terminal 2 (script obtains token automatically)
uv run python scripts/demo/run_demo.py
```

This will: check health, get token (subject `demo-op1`), inject a message on 40m, relay it to 2m, then poll `/transcripts`. With Postgres running and migrated, you get stored transcript IDs and counts; without DB, inject and relay still succeed and poll returns 0.

---

## inject_audio.py – user injection for audio/message

Injects a message into the RadioShaq RX path (in-memory queue) for demo without hardware. Optionally relays the message to another band and stores both transcripts.

**Requires:** `httpx` (included in project deps; use `uv run`).

**Auth:** Use `--subject op1` so the script can get a token from the API. For a remote API, add `--base-url http://REMOTE:8000`. You can pass an existing token with `--token $TOKEN` instead of `--subject`.

**Examples:**

```bash
# Inject (script gets token via --subject)
uv run python scripts/demo/inject_audio.py --subject op1 --role field --text "K5ABC de W1XYZ emergency" --band 40m --source-callsign K5ABC

# Inject and relay to 2m; remote API
uv run python scripts/demo/inject_audio.py --base-url http://REMOTE:8000 --subject op1 --text "Relay to 2m" --band 40m --relay-to-band 2m --source-callsign K5ABC --destination-callsign W1XYZ

# ASR then inject (token via --subject)
uv sync --extra audio
uv run python scripts/demo/inject_audio.py --subject op1 --audio-path recording.wav --stt --asr voxtral --band 40m

# TTS only (no token required)
uv run python scripts/demo/inject_audio.py --text "K5ABC de W1XYZ" --tts elevenlabs --tts-out output.mp3
```

See [docs/demo-two-local-one-remote.md](../../docs/demo-two-local-one-remote.md) for full demo topology and band-translation scenario.

---

## Digital bridges (FLDIGI / FT8 / APRS)

For comprehensive mode support, RadioShaq integrates with standard modem software rather than re-implementing full PHY stacks in-process:

- `docs/digital-bridges.md`
- `scripts/demo/ft8_decode_wav.py` (FT8 decode via WSJT-X `jt9`)

---

## HackRF hardware self-test (RX + optional TX)

To exercise HackRF hardware end-to-end (I/Q RX + analog demod WAVs, and optionally TX tone + AM/NFM/USB/LSB/CW IQ), run:

```bash
uv run python scripts/demo/hackrf_hardware_selftest.py --frequency-hz 145520000 --rx-seconds 2
```

TX is **off by default**. Only enable it with a dummy load/attenuator and a legal frequency:

```bash
uv run python scripts/demo/hackrf_hardware_selftest.py --frequency-hz 145520000 --rx-seconds 2 --tx --tx-seconds 0.5
```

---

## Full live demo (Option C: inject recordings, test SMS/WhatsApp, test HackRF TX via API)

If you only have one HackRF and no second receiver, you can still live-test the deployed HQ API end-to-end by uploading prerecorded WAVs (ASR + transcript storage + inject), relaying via SMS/WhatsApp (Twilio), and transmitting one of your WAVs via HackRF through the real `/radio` endpoints.

### What “whitelisting” means in this repo (and why it matters)

There are two related concepts:

- **Callsign registry / allowlist (hard gate)**: many endpoints require `source_callsign` (and sometimes `destination_callsign`) to be “allowed”. The effective allowlist is:
  - `radio.allowed_callsigns` from config (static), plus
  - callsigns registered in the DB via `POST /callsigns/register`.

  If `radio.callsign_registry_required=true` and the allowlist is empty, store/relay calls will be rejected (no one allowed).

- **WhitelistAgent (LLM evaluation)**: `/messages/whitelist-request` runs an LLM policy check and may register a callsign. This is optional and requires your LLM provider to be configured.

For the Option C demo, it’s simplest to **register your demo callsigns** up front (`FLABC-1`, `F1XYZ-1`) so audio uploads and relay won’t be blocked.

### Register demo callsigns

```bash
# Get a token
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/token?subject=op1&role=field&station_id=DEMO-01" | jq -r .access_token)

# Register callsigns (DB-backed)
curl -s -X POST "http://localhost:8000/callsigns/register" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"callsign":"FLABC-1","source":"api"}'

curl -s -X POST "http://localhost:8000/callsigns/register" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"callsign":"F1XYZ-1","source":"api"}'
```

If you want notify-on-relay (SMS/WhatsApp when a message is left for a callsign), set contact preferences:

```bash
curl -s -X PATCH "http://localhost:8000/callsigns/registered/F1XYZ-1/contact-preferences" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"notify_on_relay":true,"notify_sms_phone":"+33685789865","notify_whatsapp_phone":"+33685789865","consent_source":"api","consent_confirmed":true}'
```

### Prepare recordings

Put your WAV files in a folder. The live demo script uploads every `*.wav` in the folder using `/messages/from-audio`.

Suggested scripts + filenames:

- `scripts/demo/option-c-recording-scripts.md`

Prereqs:

- HQ API running at `http://localhost:8000`
- Postgres migrated (recommended)
- `RADIOSHAQ_BUS_CONSUMER_ENABLED=1` if you want the outbound dispatcher to send SMS/WhatsApp
- Twilio configured (see config `twilio.*`)
- HackRF connected + `radio.sdr_tx_enabled: true` for SDR transmit

Run:

```bash
uv run python scripts/demo/run_full_live_demo_option_c.py --recordings-dir path/to/recordings --sms-to +15551234567 --whatsapp-to +15551234567
#
# Example with your WhatsApp number:
# uv run python scripts/demo/run_full_live_demo_option_c.py --recordings-dir path/to/recordings --whatsapp-to +33685789865
```
