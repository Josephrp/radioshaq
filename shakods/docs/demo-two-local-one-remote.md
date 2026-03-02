# Demo: Two Local Machines + One Remote, Audio Injection, Band Translation

This guide describes running a SHAKODS demo on **two local machines** and **one remote host**, with a **user injection script for audio** and a scenario where **one human emits on one band and another receives on a different band**, with the message **translated between bands** and **stored** appropriately.

---

## Authentication (required for API calls)

All protected endpoints (inject, relay, transcripts, radio, messages) require a **Bearer JWT**. There is **no auth required to obtain a token**: call `POST /auth/token` with a subject and role; use the returned `access_token` in the `Authorization` header. Full reference: [auth.md](auth.md).

**Obtain token (local API):**
```bash
# Bash – capture token
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/token?subject=op1&role=field&station_id=STATION-01" | jq -r .access_token)
```
```powershell
# PowerShell
$r = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/auth/token?subject=op1&role=field&station_id=STATION-01"
$TOKEN = $r.access_token
```

**Obtain token (remote API):** Replace the host with your remote API base URL:
```bash
TOKEN=$(curl -s -X POST "http://REMOTE_HOST:8000/auth/token?subject=op1&role=field&station_id=STATION-01" | jq -r .access_token)
```

**Use token on every protected request:**
```bash
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/auth/me"
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"text":"Hello"}' "http://localhost:8000/inject/message"
```

Demo scripts (**run_demo.py**, **inject_audio.py**) get a token for you when you pass `--subject op1` (or run_demo uses `demo-op1`). No manual token needed for those scripts.

---

## 1. Topology

- **Machine A (local)**: Operator 1 – runs SHAKODS API, can “emit” via injection script (or real rig if present).
- **Machine B (local)**: Operator 2 – runs SHAKODS API, receives via injection queue and/or real receiver.
- **Machine C (remote)**: Relay/HQ or third station – runs SHAKODS API; optionally has **real receiver/emitter** (SDR or rig).

All three run the same API (`uv run python -m shakods.api.server` or uvicorn). They can share one Postgres (e.g. on C) or each have their own DB; for **band translation and storage** the relay step uses the DB on the machine that performs the relay (e.g. C or A).

---

## 2. User Injection Script (Audio → API)

Use the **injection API** to simulate “received” traffic without hardware. A **user injection script** can:

1. **Audio path**: Capture or read an audio file (e.g. from a mic or pre-recorded WAV).
2. **Optional speech-to-text**: Use a local or cloud STT (e.g. Whisper, cloud API) to get text.
3. **Inject into SHAKODS**: `POST /inject/message` with the text and band/frequency/mode/callsign.

Example (text-only, no audio file):

```bash
# Get token first (role=field or hq)
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/token?subject=op1&role=field&station_id=STATION-01" | jq -r .access_token)

# Inject a message as if received on 40m
curl -X POST "http://localhost:8000/inject/message" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "K5ABC de W1XYZ emergency traffic need relay to 2m",
    "band": "40m",
    "frequency_hz": 7215000,
    "mode": "PSK31",
    "source_callsign": "K5ABC",
    "destination_callsign": "W1XYZ"
  }'
```

A **full user injection script** can:

- Read an audio file (or stream from mic).
- Run STT to get `text`.
- Call `POST /inject/message` with `text`, `band`, `frequency_hz`, `mode`, and optional `audio_path` (path where the file is stored so transcripts can reference it).
- Optionally call `POST /messages/relay` to translate that message to another band and store both sides.

See **scripts/demo/inject_audio.py** for a script that accepts text (and optional audio path) and injects into a given API base URL.

### ASR: shakods/voxtral-asr-en

The inject script can transcribe audio using the **Voxtral** ASR model `shakods/voxtral-asr-en` (fine-tuned on mistralai/Voxtral-Mini-3B-2507). Install audio deps and run:

```bash
uv sync --extra audio
uv run python scripts/demo/inject_audio.py --subject op1 --audio-path recording.wav --stt --asr voxtral --band 40m
```

Use `--asr whisper` to fall back to Whisper (pip install openai-whisper) instead.

### TTS: ElevenLabs

Generate speech from text with **ElevenLabs**. Set `ELEVENLABS_API_KEY` (or pass via your shell). Then:

```bash
# TTS only (no API token needed)
uv run python scripts/demo/inject_audio.py --text "K5ABC de W1XYZ" --tts elevenlabs --tts-out output.mp3

# With inject + relay (subject/token required)
uv run python scripts/demo/inject_audio.py --subject op1 --text "Relay to 2m" --tts elevenlabs --tts-out out.mp3 --band 40m --relay-to-band 2m
```

Options: `--tts-voice-id`, `--tts-model` (e.g. `eleven_multilingual_v2`, `eleven_turbo_v2_5`, `eleven_flash_v2_5`).

---

## 3. How Machines Can Actually Receive Ham Radio Audio (Remote Host with Receiver/Emitter)

When you have **real hardware** on a remote host (SDR or rig with audio out):

### 3.1 Audio path (high level)

1. **RF → baseband audio**
   - **SDR** (e.g. RTL-SDR, SDRplay, HackRF): `rtl_sdr` or similar outputs I/Q; a demodulator (GNU Radio, sdrpp, GQRX, or FLDIGI’s sound card input) produces **audio**.
   - **Traditional rig**: Radio’s **audio output** (headphone/speaker or line-out) goes into the computer’s **sound card** (or USB audio device).

2. **Audio → application**
   - **Digital modes (PSK31, FT8, RTTY, etc.)**: Run **FLDIGI** (or similar) on the remote host. Set its input to the sound card (or virtual cable) that receives the rig/SDR audio. FLDIGI decodes text. SHAKODS talks to FLDIGI via **XML-RPC** (default port 7362) and calls `text.get_rx` in `receive_text()` to get decoded text – so the “machine” receives ham radio **text** via FLDIGI.
   - **Voice**: For voice you’d add a **speech-to-text** step (e.g. Whisper, cloud STT). Pipe rig audio into STT, then feed the resulting text into SHAKODS (e.g. inject API or a small daemon that calls `POST /inject/message` with the transcribed text and optional path to the audio file).

3. **Remote host setup**
   - Install FLDIGI (and optionally rig control: hamlib/rigctld).
   - Connect SDR or rig audio out → sound card in (or virtual audio).
   - Start FLDIGI, enable XML-RPC server (Edit → Preferences → Modem → XML-RPC).
   - Start SHAKODS API on the remote host; point `digital_modes` (FLDIGI) config to `localhost:7362`. Then `radio_rx` / orchestrator will get received text from FLDIGI.

So: **with a receiver and emitter on the remote host**, the machine “receives” ham radio by (1) SDR/rig → audio, (2) audio → FLDIGI (or STT for voice), (3) FLDIGI/STT → SHAKODS (XML-RPC or inject API). No receiver: use the **injection queue** and the user injection script instead.

---

## 4. Injecting User Data in a Useful Way

- **Without hardware**: Use **only** the injection API. The injection script (or a human typing) sends `POST /inject/message` with text, band, frequency, mode, callsigns. The RX path (e.g. `radio_rx` when not using FLDIGI) reads from the **in-memory injection queue** and treats messages as “received.”
- **With hardware on remote**: Real receive path is FLDIGI (or STT) → SHAKODS. You can **still** use the inject API on that same host to add **synthetic** messages (e.g. for testing or a second “virtual” operator). So: mix real RX and injected messages.
- **Storing and relaying**: After inject (or after real receive), call **`POST /messages/relay`** to “translate” the message to another band and store both the original and the relayed copy with band and `relay_from_transcript_id` in metadata. That gives you a clear audit trail: received on band A → stored → relayed to band B → stored.

---

## 5. Scenario: One User Emits on One Band, Another User on Another Band – Translate and Store

**Goal**: User 1 “emits” a message on **band A** (e.g. 40m). The system records it, **translates** it to **band B** (e.g. 2m), and User 2 “receives” it on band B. All stored with band and relay linkage.

### Option A: Injection + relay on one API (e.g. remote C)

1. **Inject** the message as “received” on 40m (simulating User 1’s transmission):
   ```bash
   curl -X POST "http://REMOTE:8000/inject/message" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"text":"Emergency traffic, need relay to 2m","band":"40m","frequency_hz":7215000,"mode":"PSK31","source_callsign":"K5ABC","destination_callsign":"W1XYZ"}'
   ```
2. **Relay** that message from 40m to 2m and store both:
   ```bash
   curl -X POST "http://REMOTE:8000/messages/relay" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "message": "Emergency traffic, need relay to 2m",
       "source_band": "40m",
       "source_frequency_hz": 7215000,
       "source_callsign": "K5ABC",
       "target_band": "2m",
       "target_frequency_hz": 146520000,
       "destination_callsign": "W1XYZ"
     }'
   ```
   The API stores:
   - One transcript on **40m** (source) with `metadata.band = "40m"`, `relay_role = "source"`.
   - One transcript on **2m** (relayed) with `metadata.relay_from_transcript_id`, `relay_from_band`, `relay_from_frequency_hz`.

3. User 2’s client (Machine B) can **receive** from the injection queue (if you inject the same text again for “2m”) or by querying transcripts (e.g. search by `destination_callsign=W1XYZ` or by band).

### Option B: Two local machines + remote

- **Machine A**: User 1 injects “sent” on 40m (or uses real rig). Either A or C stores the “received” transcript (e.g. A posts to C’s inject, or A has DB and stores locally).
- **Machine C (remote)**: Runs relay logic: `POST /messages/relay` with message, `source_band=40m`, `target_band=2m`. C’s DB holds both transcripts.
- **Machine B**: User 2 either (1) polls C’s transcript search for new relayed traffic for their callsign, or (2) C (or a script) injects the relayed message on 2m and B’s `radio_rx` (with injection queue) “receives” it.

End-to-end: **User 1 (band A) → store → translate to band B → store → User 2 (band B)**. Information is stored with band and relay linkage for logs and compliance.

---

## 6. Quick Reference

| Action | Endpoint | Purpose |
|--------|----------|---------|
| Get token | `POST /auth/token?subject=...&role=field&station_id=...` | Auth for inject/relay |
| Inject message | `POST /inject/message` | Push text (and optional audio_path) into RX path |
| Relay band→band | `POST /messages/relay` | Store on source band, then on target band with relay metadata |
| Process message | `POST /messages/process` | REACT orchestration (can trigger radio_tx/radio_rx) |

---

## 7. Exact command sequence (two local + one remote)

Replace **`REMOTE`** with the remote host’s hostname or IP (e.g. `192.168.1.10` or `hq.example.com`). All commands assume you are in the **repo root** on each machine and have run `uv sync` (and `uv sync --extra audio` only if you use ASR/TTS in inject_audio.py).

### Machine C (remote – relay/HQ)

Run the API here so A and B can call it. Optionally run Postgres on C and apply migrations so relay stores transcripts.

```bash
# 1) Optional: start Postgres and run migrations (if you want transcript storage)
# Then:
uv run python -m shakods.api.server
```

Leave this running. Ensure port 8000 is reachable from A and B (firewall/NAT).

---

### Machine A (local – Operator 1, injects and triggers relay)

Run the full demo script **against C’s API**. It will: get token, inject a message on 40m, relay it to 2m, then poll transcripts.

```bash
# 2) Full demo (inject → relay → poll) targeting remote API
uv run python scripts/demo/run_demo.py --base-url http://REMOTE:8000
```

If you prefer to inject and relay manually (e.g. with curl or inject_audio.py), use the same base URL:

```bash
# Optional: get token from C, then inject and relay by hand
TOKEN=$(curl -s -X POST "http://REMOTE:8000/auth/token?subject=op1&role=field&station_id=STATION-01" | jq -r .access_token)
curl -X POST "http://REMOTE:8000/inject/message" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"text":"Emergency traffic, need relay to 2m","band":"40m","frequency_hz":7215000,"mode":"PSK31","source_callsign":"K5ABC","destination_callsign":"W1XYZ"}'
curl -X POST "http://REMOTE:8000/messages/relay" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"message":"Emergency traffic, need relay to 2m","source_band":"40m","source_frequency_hz":7215000,"source_callsign":"K5ABC","target_band":"2m","target_frequency_hz":146520000,"destination_callsign":"W1XYZ"}'
```

---

### Machine B (local – Operator 2, receives by polling)

Get a token from C and poll transcripts (e.g. for 2m / relayed traffic).

```bash
# 3) Get token from C and list transcripts
TOKEN=$(curl -s -X POST "http://REMOTE:8000/auth/token?subject=op2&role=field&station_id=STATION-02" | jq -r .access_token)
curl -s -H "Authorization: Bearer $TOKEN" "http://REMOTE:8000/transcripts?limit=10"
# Optional: filter by band
curl -s -H "Authorization: Bearer $TOKEN" "http://REMOTE:8000/transcripts?band=2m&limit=10"
```

---

### Order of execution

1. **C**: Start API (and optionally Postgres + migrations).
2. **A**: Run `run_demo.py --base-url http://REMOTE:8000` (or manual inject + relay to C).
3. **B**: Get token from C, then `GET /transcripts` (and optionally filter by band).

With Postgres on C and migrations applied, step 2 stores source and relayed transcripts; step 3 shows them. Without DB, inject and relay still succeed; relay returns `"relay": "no_storage"` and transcript list is empty.

---

## 8. Run the demo (single-API, with or without DB)

From the repo root, with the API running on the **same** machine:

```bash
# Terminal 1: start API (and optionally Postgres + migrations)
uv run python -m shakods.api.server

# Terminal 2: run full demo (inject -> relay -> poll transcripts)
uv run python scripts/demo/run_demo.py
```

With Postgres running and migrated, you will see `source_transcript_id` and `relayed_transcript_id` and transcript counts when polling. Without DB, inject and relay still succeed; relay returns `"relay": "no_storage"` and poll returns zero transcripts.

To point at a remote API:

```bash
uv run python scripts/demo/run_demo.py --base-url http://REMOTE:8000
```

---

## 9. Real Ham Audio on Remote: Summary

- **SDR**: RF → rtl_sdr / SDR app → demodulated audio → FLDIGI (or STT for voice) → SHAKODS (FLDIGI XML-RPC or inject).
- **Rig**: Rig audio out → sound card → FLDIGI (or STT) → SHAKODS.
- **No hardware**: User injection script → `POST /inject/message` → injection queue → `radio_rx` (or downstream relay/transcript storage).

All of this works with **two local machines and one remote** by pointing the injection script and relay calls at the appropriate host’s API (localhost or REMOTE).
