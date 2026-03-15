# Full HackRF demo (HQ + receiver + live stream + inject/relay)

This walkthrough configures a **complete demo**: HackRF as a remote receiver streaming to HQ, with transcripts stored and inject/relay so you can see end-to-end flow in the API and (optionally) the web UI.

## What you get

1. **HQ (main API)** — Stores receiver uploads as transcripts and injects them into the RX path; serves web UI and `/transcripts`, `/inject`, `/messages/relay`.
2. **Remote receiver** — Your HackRF tunes to a frequency and streams I/Q → signal strength; each sample is uploaded to HQ when a client is connected via WebSocket.
3. **Stream client** — A script connects to the receiver’s WebSocket so the HackRF actually runs and uploads to HQ.
4. **Inject + relay demo** — Optional: inject a message on 40m, relay to 2m, poll transcripts so you see the full band-translation scenario.

## Prerequisites

- **HackRF** connected and working (`hackrf_info` shows the device).
- **pyhackrf2** installed (see below for WSL; `uv sync --extra hackrf`; on Windows the project skips it — use WSL for real device).
- **PostgreSQL** (Docker on 5434 or existing; used for transcript storage).
- **Same JWT secret** on HQ and receiver (so the receiver can verify tokens issued by HQ).

---

## Using WSL

If the receiver logs **"pyhackrf2 not installed"** and you only see **signal_strength=-100 dB** and no audio, the app is in stub mode. To use the **actual HackRF** you must:

1. Attach the physical HackRF to **WSL** using **usbipd-win** on Windows.
2. Install **libhackrf** and **pyhackrf2** inside WSL.
3. Run **HQ + receiver + demo scripts entirely inside WSL** with a WSL‑only venv.

### 1. Open WSL and create a WSL-only venv

In **WSL Ubuntu**:

```bash
cd /mnt/c/Users/MeMyself/repo/radioshaq/radioshaq #change this path 

python3 -m venv .venv-wsl
source .venv-wsl/bin/activate

pip install --upgrade pip uv
uv sync
uv sync --extra hackrf      # HackRF + pyhackrf2
uv sync --extra voice_tx    # HackRF TX from HQ
uv sync --extra audio       # ASR (local), optional
uv sync --extra tts_kokoro  # Kokoro TTS (local), optional
```

You will re-use this venv in every WSL terminal via:

```bash
source .venv-wsl/bin/activate
```

### 2. Install libhackrf from source (WSL, once)

Ubuntu’s packaged `libhackrf` may be old; **pyhackrf2** only needs the library at runtime. For best compatibility, build and install the latest from Great Scott Gadgets:

```bash
# In WSL (Ubuntu)
sudo apt update
sudo apt install -y build-essential cmake libusb-1.0-0-dev pkg-config

cd ~
git clone https://github.com/greatscottgadgets/hackrf.git
cd hackrf/host
mkdir build && cd build
cmake ..
make -j"$(nproc)"
sudo make install
sudo ldconfig

hackrf_info   # should run (device may not appear yet)
```

If `hackrf_info` prints “No HackRF boards found.” here, that is expected until you attach the device to WSL in the next step.

### 3. Attach HackRF to WSL (Windows host with usbipd-win)

All `usbipd` commands are run on **Windows PowerShell as Administrator**, not inside WSL.

1. Install [usbipd-win](https://github.com/dorssel/usbipd-win/releases) if needed:

   ```powershell
   winget install usbipd
   ```

2. List USB devices and find the HackRF **BUSID** (e.g. `2-3`):

   ```powershell
   usbipd list
   ```

3. Bind and attach the HackRF to your WSL distro:

   ```powershell
   # Share the device (safe if already shared)
   usbipd bind --busid 2-3

   # Attach it to WSL (optionally specify distro by name)
   usbipd attach --wsl --busid 2-3
   # or: usbipd attach --wsl --busid 2-3 --distribution <YourDistroName>
   ```

   If it was previously attached to a different distro, detach and reattach:

   ```powershell
   usbipd detach --busid 2-3
   usbipd attach --wsl --busid 2-3
   ```

4. Back in **WSL**, confirm the device is visible:

   ```bash
   lsusb | grep -i hackrf || lsusb
   hackrf_info
   ```

   You should now see board information and a serial number. If not, repeat the `usbipd attach` step and make sure no Windows SDR application is currently using the HackRF.

### 4. Configure env vars for HQ (Mistral, ElevenLabs, Twilio) in WSL

In **WSL**, with `.venv-wsl` activated and working directory `radioshaq/`:

```bash
cd /mnt/c/Users/MeMyself/monorepo/radioshaq
source .venv-wsl/bin/activate

# JWT: HQ + receiver must share this secret
export RADIOSHAQ_JWT__SECRET_KEY="demo-secret-change-me"

# Receiver uploads: store + inject into RX path
export RADIOSHAQ_RADIO__RECEIVER_UPLOAD_STORE=true
export RADIOSHAQ_RADIO__RECEIVER_UPLOAD_INJECT=true

# Enable MessageBus inbound consumer + outbound dispatcher (radio/SMS/WhatsApp)
export RADIOSHAQ_BUS_CONSUMER_ENABLED=1

# LLM: Mistral
export MISTRAL_API_KEY="sk-your-mistral-key"
export RADIOSHAQ_LLM__MISTRAL_API_KEY="$MISTRAL_API_KEY"

# ElevenLabs: ASR (Scribe) + TTS
export ELEVENLABS_API_KEY="sk-your-elevenlabs-key"

# Twilio for SMS/WhatsApp relay
export RADIOSHAQ_TWILIO__ACCOUNT_SID="ACXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
export RADIOSHAQ_TWILIO__AUTH_TOKEN="your_twilio_auth_token"
export RADIOSHAQ_TWILIO__FROM_NUMBER="+15551234567"        # SMS sender (E.164)
export RADIOSHAQ_TWILIO__WHATSAPP_FROM="+15557654321"     # WhatsApp-enabled sender (E.164)

# If these are not set or invalid, SMS/WhatsApp relay requests will still return 200 from
# /messages/relay, but the outbound dispatcher will log warnings and eventually drop to
# a dead-letter queue. This does not affect core /messages or HackRF TX behavior.

# Optional: explicitly prefer ElevenLabs TTS (default is elevenlabs)
export RADIOSHAQ_TTS__PROVIDER="elevenlabs"
```

You can alternatively put these in a `.env` file and let `radioshaq.setup` manage them; for the demo, exporting in your shell is sufficient.

#### Docker/Postgres from WSL

The full demo still needs PostgreSQL running in Docker on port 5434. In WSL you have two options:

- **Docker Desktop on Windows with WSL integration enabled for your distro**, so the `docker` CLI works inside WSL.
- **Native Docker Engine inside WSL** (install via your distro’s package manager).

Verify from WSL that Docker is available:

```bash
docker ps
```

Then, from **WSL** (same venv as above), start the Postgres container using the standard launch CLI:

```bash
cd /mnt/c/Users/MeMyself/monorepo
source radioshaq/.venv-wsl/bin/activate   # or activate your chosen WSL venv

uv run radioshaq launch docker            # starts Postgres on 5434 in Docker
```

This is equivalent to running `radioshaq launch docker` on Windows; Docker Desktop exposes the same daemon to both Windows and WSL when WSL integration is enabled, and WSL will reach Postgres at `127.0.0.1:5434`.

### 5. Start HQ API in WSL (Terminal 1)

In **WSL Terminal 1**, after setting the env vars above:

```bash
cd /mnt/c/Users/MeMyself/monorepo/radioshaq
source .venv-wsl/bin/activate

uv run radioshaq run-api
```

Leave this running. HQ will be available at `http://localhost:8000` from both WSL and Windows.

### 6. Get a token for the receiver (HQ_TOKEN) in WSL (Terminal 2)

Open **WSL Terminal 2**, activate the same venv, and request a token from HQ:

```bash
cd /mnt/c/Users/MeMyself/monorepo/radioshaq
source .venv-wsl/bin/activate

TOKEN=$(curl -s -X POST \
  "http://localhost:8000/auth/token?subject=receiver&role=field&station_id=HACKRF-DEMO" \
  | jq -r .access_token)

echo "HQ_TOKEN=$TOKEN"
```

You will use `$TOKEN` as `HQ_TOKEN` for the receiver.

### 7. Start the HackRF receiver in WSL (Terminal 2)

Still in **WSL Terminal 2**:

```bash
cd /mnt/c/Users/MeMyself/monorepo/radioshaq

# Match HQ's JWT secret
export JWT_SECRET="demo-secret-change-me"

# HackRF configuration
export SDR_TYPE=hackrf
export HACKRF_INDEX=0
export STATION_ID=HACKRF-DEMO

# Where to send uploads
export HQ_URL=http://localhost:8000
export HQ_TOKEN="$TOKEN"

# Demod + audio settings
export RECEIVER_MODE=nfm
export RECEIVER_AUDIO_RATE=48000

uv run --active radioshaq run-receiver --host 0.0.0.0 --port 8765
```

You should **not** see "pyhackrf2 not installed". If you do, confirm `libhackrf` is installed (step 2) and that `uv sync --extra hackrf` was run in `.venv-wsl`, then restart the receiver.

### 8. Trigger a live stream and record audio in WSL (Terminal 3)

Open **WSL Terminal 3**, with the same venv:

```bash
cd /mnt/c/Users/MeMyself/monorepo/radioshaq
source .venv-wsl/bin/activate

# Stream 145 MHz for 30 seconds and upload to HQ
uv run python scripts/demo/stream_receiver_ws.py \
  --hq-url http://localhost:8000 \
  --receiver-url http://localhost:8765 \
  --frequency 145000000 \
  --duration 30

# Optionally: also save demodulated audio to a WAV file
uv run python scripts/demo/stream_receiver_ws.py \
  --hq-url http://localhost:8000 \
  --receiver-url http://localhost:8765 \
  --frequency 145000000 \
  --duration 30 \
  --wav-out out.wav
```

You should see `signal_strength` values above `-100 dB` when there is RF, and HQ will store and inject receiver uploads into the RX path. `out.wav` will contain demodulated audio you can play.

### 9. Optional: Full Option‑C live demo (Mistral + ElevenLabs + Twilio + HackRF TX)

With HQ still running in **Terminal 1** and the HackRF receiver running in **Terminal 2**, you can run the **full "Option C" live demo** that exercises:

- Auth, health, band listing, propagation.
- WAV uploads via `/messages/from-audio`.
- Inject-and-store text path.
- Relay to radio/SMS/WhatsApp via the bus consumer (Twilio).
- HackRF TX via `/radio/send-audio` and `/radio/send-tts`.
- Transcript search.

1. Prepare a folder of WAV files, for example (on Windows):

   ```text
   C:\Users\MeMyself\monorepo\radioshaq\scripts\demo\recordings\00_callsign_identity.wav
   C:\Users\MeMyself\monorepo\radioshaq\scripts\demo\recordings\01_whitelist_request.wav
   C:\Users\MeMyself\monorepo\radioshaq\scripts\demo\recordings\02_relay_message_40m_to_2m.wav
   C:\Users\MeMyself\monorepo\radioshaq\scripts\demo\recordings\03_notify_on_relay_opt_in.wav
   C:\Users\MeMyself\monorepo\radioshaq\scripts\demo\recordings\04_emergency_sms_relay.wav
   C:\Users\MeMyself\monorepo\radioshaq\scripts\demo\recordings\05_tx_payload.wav
   ```

   This is `/mnt/c/Users/MeMyself/monorepo/radioshaq/scripts/demo/recordings` inside WSL.  
   Each filename + spoken script is described in `scripts/demo/option-c-recording-scripts.md`; the live demo script simply uploads **all \`.wav\` files** in this directory via `POST /messages/from-audio` in sorted order.

2. Ensure SDR TX is enabled for HackRF in `radioshaq/config.yaml` (or via env):

   ```yaml
   radio:
     sdr_tx_enabled: true
     sdr_tx_backend: hackrf
   ```

   Or, equivalently via environment variables (recommended when iterating):

   ```bash
   export RADIOSHAQ_RADIO__SDR_TX_ENABLED=true
   export RADIOSHAQ_RADIO__SDR_TX_BACKEND=hackrf
   ```

   These must be set **before** starting `uv run radioshaq run-api` so that the HackRF SDR TX path is enabled.

3. In **WSL Terminal 4** (venv active), run:

   ```bash
   cd /mnt/c/Users/MeMyself/monorepo/radioshaq
   source .venv-wsl/bin/activate

   # Use the callsigns that match the suggested Option‑C recordings
   # (see scripts/demo/option-c-recording-scripts.md)
   uv run python scripts/demo/run_full_live_demo_option_c.py \
     --base-url http://localhost:8000 \
     --recordings-dir /mnt/c/Users/MeMyself/monorepo/radioshaq/scripts/demo/recordings \
     --source-callsign FLABC-1 \
     --dest-callsign F1XYZ-1 \
     --band 40m \
     --sms-to "+15559876543" \
     --whatsapp-to "+15559876543" \
     --tx-frequency-hz 145520000 \
     --tx-mode NFM
   ```

   Before running this, make sure the callsigns you use here are **registered/allowed** at HQ:

   - `POST /callsigns/register` for `FLABC-1` and `F1XYZ-1`, **or**
   - add them to `radio.allowed_callsigns` in `config.yaml`.

   If `radio.callsign_registry_required=true` (or `RADIOSHAQ_RADIO__CALLSIGN_REGISTRY_REQUIRED=true`), unregistered callsigns will be rejected by `/messages/from-audio` and `/messages/relay`.

This script uses your **Mistral**, **ElevenLabs**, and **Twilio** env vars to drive a full end‑to‑end live demo; HackRF TX is used for `send-audio` and `send-tts` if your HackRF is attached and `sdr_tx_enabled` is true. The Option‑C flow does **not** depend on live audio trigger phrases; it uploads prerecorded WAVs directly, bypassing the `audio.trigger_phrases` / `audio.audio_activation_phrase` gating used by the live `voice_rx` pipeline.

#### Env summary for HQ vs receiver in the Option‑C + HackRF demo

For clarity, here are the **key environment variables** for HQ (central API) and the remote receiver when running this combined demo:

- **HQ process (`uv run radioshaq run-api`)**

  ```bash
  # Core mode + JWT (must match receiver JWT_SECRET)
  export RADIOSHAQ_MODE=hq
  export RADIOSHAQ_JWT__SECRET_KEY="demo-secret-change-me"

  # Receiver uploads → store + inject
  export RADIOSHAQ_RADIO__RECEIVER_UPLOAD_STORE=true
  export RADIOSHAQ_RADIO__RECEIVER_UPLOAD_INJECT=true

  # HackRF SDR TX via HQ API
  export RADIOSHAQ_RADIO__SDR_TX_ENABLED=true
  export RADIOSHAQ_RADIO__SDR_TX_BACKEND=hackrf

  # Message bus consumer (for relay/SMS/WhatsApp)
  export RADIOSHAQ_BUS_CONSUMER_ENABLED=1

  # LLM (Mistral)
  export RADIOSHAQ_LLM__PROVIDER=mistral
  export MISTRAL_API_KEY="sk-your-mistral-key"
  export RADIOSHAQ_LLM__MISTRAL_API_KEY="$MISTRAL_API_KEY"

  # ElevenLabs ASR/TTS
  export ELEVENLABS_API_KEY="sk-your-elevenlabs-key"
  export RADIOSHAQ_TTS__PROVIDER="elevenlabs"

  # Twilio for SMS/WhatsApp relay (optional but required for SMS/WA portions of Option‑C)
  export RADIOSHAQ_TWILIO__ACCOUNT_SID="ACXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
  export RADIOSHAQ_TWILIO__AUTH_TOKEN="your_twilio_auth_token"
  export RADIOSHAQ_TWILIO__FROM_NUMBER="+15551234567"
  export RADIOSHAQ_TWILIO__WHATSAPP_FROM="+15557654321"
  ```

- **Remote receiver process (`uv run radioshaq run-receiver`)**

  ```bash
  # Same secret as RADIOSHAQ_JWT__SECRET_KEY on HQ
  export JWT_SECRET="demo-secret-change-me"

  # Identify this receiver / station
  export STATION_ID=HACKRF-DEMO

  # HackRF as SDR backend
  export SDR_TYPE=hackrf
  export HACKRF_INDEX=0
  # Optional: HACKRF_SERIAL, HACKRF_SAMPLE_RATE, HACKRF_MAX_GAIN, RESTRICTED_BANDS_REGION

  # Where to send uploads (HQ) + auth token from /auth/token
  export HQ_URL=http://localhost:8000
  export HQ_TOKEN="<paste token from Step 4>"

  # Demod + audio defaults for the receiver
  export RECEIVER_MODE=nfm
  export RECEIVER_AUDIO_RATE=48000

  uv run radioshaq run-receiver --host 0.0.0.0 --port 8765
  ```

The **trigger phrase** configuration (`RADIOSHAQ_AUDIO__TRIGGER_ENABLED`, `RADIOSHAQ_AUDIO__TRIGGER_PHRASES`, etc.) only affects the **live `voice_rx` audio pipeline** (when HQ is listening to rig audio directly). The Option‑C demo, including the WAV uploads described in `option-c-recording-scripts.md`, uses `/messages/from-audio` and is not gated by trigger phrases; you generally do **not** need to change the default trigger phrase settings for this demo.

---

## Step 1: Database and migrations

From the **monorepo root** (or `radioshaq/` if your `uv` project is there):

```bash
# Start Postgres (Docker on port 5434)
cd c:/Users/MeMyself/monorepo
uv run radioshaq launch docker

# Run migrations (from radioshaq directory) BEFORE any demo scripts
cd radioshaq
uv run alembic upgrade head
```

If you use an existing Postgres, set `RADIOSHAQ_DATABASE__POSTGRES_URL` and run migrations from `radioshaq/`.

---

## Step 2: Configure HQ (receiver upload store + inject)

HQ must accept receiver uploads and store/inject them. Set **one** of:

### Option A — Environment (recommended for demo)

```bash
# Bash (Git Bash / MINGW64)
export RADIOSHAQ_JWT__SECRET_KEY="demo-secret-change-me"
export RADIOSHAQ_RADIO__RECEIVER_UPLOAD_STORE=true
export RADIOSHAQ_RADIO__RECEIVER_UPLOAD_INJECT=true
```

### Option B — config.yaml in project root

In `radioshaq/config.yaml` (or path set by `SHAKODS_CONFIG` / `RADIOSHAQ_CONFIG`):

```yaml
jwt:
  secret_key: "demo-secret-change-me"
radio:
  receiver_upload_store: true
  receiver_upload_inject: true
```

Use the **same** `secret_key` value as `JWT_SECRET` for the receiver in the next step.

---

## Step 3: Start HQ (main API)

In a **first terminal**, from `radioshaq/`:

```bash
cd c:/Users/MeMyself/monorepo/radioshaq

# If using env (Step 2 Option A), set them first, then:
uv run radioshaq run-api
```

Leave it running. API: **`http://localhost:8000`** — docs: `http://localhost:8000/docs`.

---

## Step 4: Get a token for the receiver (HQ_TOKEN)

The receiver needs a **Bearer token** to POST to HQ’s `/receiver/upload`. Get one from HQ:

```bash
# Bash
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/token?subject=receiver&role=field&station_id=HACKRF-DEMO" | jq -r .access_token)
echo "HQ_TOKEN=$TOKEN"
```

Copy the token value; you’ll set it as `HQ_TOKEN` when starting the receiver.  
(If you don’t have `jq`, call the same URL in a browser or with curl and copy `access_token` from the JSON.)

---

## Step 5: Start the remote receiver (HackRF)

In a **second terminal**, same `JWT_SECRET` as HQ, and the token from Step 4:

```bash
cd c:/Users/MeMyself/monorepo/radioshaq

export SDR_TYPE=hackrf
export HACKRF_INDEX=0
export JWT_SECRET="demo-secret-change-me"    # same as RADIOSHAQ_JWT__SECRET_KEY
export STATION_ID=HACKRF-DEMO
export HQ_URL=http://localhost:8000
export HQ_TOKEN="<paste token from Step 4>"
export RECEIVER_MODE=nfm
export RECEIVER_AUDIO_RATE=48000

uv run radioshaq run-receiver --host 0.0.0.0 --port 8765
```

Receiver will listen on **`http://localhost:8765`**. It won’t stream until a client connects to its WebSocket (next step).

---

## Step 6: Trigger a live HackRF stream (and uploads to HQ)

In a **third terminal**, run the stream script. It gets a token from HQ, connects to the receiver’s WebSocket, and streams for the given duration; the receiver will tune the HackRF and upload each sample to HQ:

```bash
cd c:/Users/MeMyself/monorepo/radioshaq

uv run python scripts/demo/stream_receiver_ws.py --hq-url http://localhost:8000 --receiver-url http://localhost:8765 --frequency 145000000 --duration 30
```

- **30 seconds** of 145 MHz (2 m). You’ll see lines like `signal_strength=-42 dB`.
- HQ will receive POSTs to `/receiver/upload` and, with Step 2 config, **store transcripts** and **inject** into the RX path.

To also **record demodulated analog FM voice audio** (when `RECEIVER_MODE=nfm` is set on the receiver):

```bash
uv run python scripts/demo/stream_receiver_ws.py --frequency 145000000 --duration 30 --wav-out out.wav
```

You can also request the demod mode per connection (overrides the receiver’s default) using `--mode`:

```bash
uv run python scripts/demo/stream_receiver_ws.py --frequency 14250000 --mode usb --duration 30 --wav-out usb.wav
```

Try another frequency, e.g. 70 cm:

```bash
uv run python scripts/demo/stream_receiver_ws.py --frequency 433000000 --duration 20
```

---

## Step 7 (optional): Inject + relay + poll transcripts

With HQ and receiver still running, run the standard inject → relay → poll demo so you see transcripts from both **receiver uploads** (Step 6) and **injected/relayed** messages:

```bash
cd c:/Users/MeMyself/monorepo/radioshaq

uv run python scripts/demo/run_demo.py
```

This injects a message on 40m, relays it to 2m, then polls `/transcripts`. You should see transcript counts and entries. Receiver uploads (from Step 6) will also appear as transcripts when `receiver_upload_store` is true.

---

## Optional: HackRF transmit (SDR TX) of a WAV file (NFM)

By default, RadioShaq’s SDR TX path only sent a short test tone. If you enable SDR TX in your HQ config and provide an `audio_path`, it can now **modulate NFM** and transmit audio via HackRF.

1. Enable SDR TX in `radioshaq/config.yaml` (HQ):

```yaml
radio:
  sdr_tx_enabled: true
  sdr_tx_backend: hackrf
```

1. Install audio deps (for reading WAV):

```bash
cd c:/Users/MeMyself/monorepo/radioshaq
uv sync --extra voice_tx
```

1. Call the API (example uses `/messages/relay`’s optional “send_audio_back” flow, or use your own task wiring). If you already have an endpoint that triggers `radio_tx` with `audio_path`, pass it there.

---

## Step 8 (optional): Web UI and transcripts

1. Open **`http://localhost:8000`** in a browser.
1. Get a token: **`http://localhost:8000/docs`** → `POST /auth/token` (e.g. `subject=op1`, `role=field`, `station_id=DEMO-01`) → copy `access_token`.
1. Log in or set the token in the UI if it has a token field.
1. Open **Transcripts** (or call `GET /transcripts` with `Authorization: Bearer <token>`) to see stored receiver uploads and injected/relayed messages.

---

## Quick reference (all commands in order)

| Step | Terminal | Command |
| --- | --- | --- |
| 1 | one | `uv run radioshaq launch docker` then `cd radioshaq && uv run alembic upgrade head` |
| 2 | - | `export RADIOSHAQ_JWT__SECRET_KEY="demo-secret-change-me"` and `RADIOSHAQ_RADIO__RECEIVER_UPLOAD_STORE=true`, `RECEIVER_UPLOAD_INJECT=true` |
| 3 | 1 | `cd radioshaq && uv run radioshaq run-api` |
| 4 | 2 | `TOKEN=$(curl -s -X POST "http://localhost:8000/auth/token?subject=receiver&role=field&station_id=HACKRF-DEMO" \| jq -r .access_token)` |
| 5 | 2 | `export SDR_TYPE=hackrf` … `HQ_TOKEN=$TOKEN` … `uv run radioshaq run-receiver --host 0.0.0.0 --port 8765` |
| 6 | 3 | `uv run python scripts/demo/stream_receiver_ws.py --frequency 145000000 --duration 30` |
| 7 | 3 | `uv run python scripts/demo/run_demo.py` |
| 8 | browser | `http://localhost:8000` → Transcripts |

---

## Troubleshooting

- **Receiver says “JWT_SECRET not configured”** — Set `JWT_SECRET` to the same value as `RADIOSHAQ_JWT__SECRET_KEY` on HQ.
- **HQ returns 401 on /receiver/upload** — Use a token from `POST /auth/token` as `HQ_TOKEN`; replace it if it expires.
- **Stream script “Connection refused”** — Start the receiver (Step 5) before running the stream script (Step 6).
- **No transcripts from receiver** — Ensure `receiver_upload_store=true` and migrations are applied; check HQ logs for errors on `/receiver/upload`.
- **500 on `/messages/from-audio` in Option C** — This usually means the transcripts tables are not migrated yet. From the monorepo root run `uv run radioshaq launch docker` (if using the demo Postgres), then `cd radioshaq && uv run alembic upgrade head`, restart `radioshaq run-api`, and retry the demo.
- **signal_strength=-100 dB and "Wrote ~0.0s audio"** — Receiver is in stub mode (no real HackRF). Follow **[Use your real HackRF device (WSL)](#use-your-real-hackrf-device-wsl)** above: install libhackrf from source in WSL, attach HackRF via usbipd, then `uv sync --extra hackrf` (installs pyhackrf2) in a WSL venv and run HQ + receiver + stream client all in WSL.
