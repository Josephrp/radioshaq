# Exact WSL commands to run the demo

Copy-paste these in order. Use your actual paths: replace `/mnt/c/Users/MeMyself/monorepo` with your repo path if different.

---

## Option A: Run-all-demos only (no HackRF, no receiver)

Good for: inject, relay, whitelist, orchestrator, scheduler, voice-rx poll. Option C / TX / voice-to-voice are **skipped** (no `--recordings-dir`) or you can add `--recordings-dir` to run them if HQ has SDR TX configured.

### One-time (if not done yet)

```bash
cd /mnt/c/Users/MeMyself/monorepo
source radioshaq/.venv-wsl/bin/activate
uv run radioshaq launch docker
cd radioshaq && uv run alembic upgrade head
cd /mnt/c/Users/MeMyself/monorepo/radioshaq
```

### Terminal 1 — HQ API

```bash
cd /mnt/c/Users/MeMyself/monorepo/radioshaq
source .venv-wsl/bin/activate

export RADIOSHAQ_JWT__SECRET_KEY="demo-secret-change-me"
export RADIOSHAQ_RADIO__RECEIVER_UPLOAD_STORE=true
export RADIOSHAQ_RADIO__RECEIVER_UPLOAD_INJECT=true
export RADIOSHAQ_BUS_CONSUMER_ENABLED=1
export RADIOSHAQ_MODE=hq

# LLM (required for orchestrator/whitelist/scheduler demos)
export MISTRAL_API_KEY="sk-your-mistral-key"
export RADIOSHAQ_LLM__MISTRAL_API_KEY="$MISTRAL_API_KEY"

# ASR/TTS if you will use recordings later
export ELEVENLABS_API_KEY="sk-your-elevenlabs-key"

uv run radioshaq run-api
```

Leave running.

### Terminal 2 — Run all demos (no recordings)

```bash
cd /mnt/c/Users/MeMyself/monorepo/radioshaq
source .venv-wsl/bin/activate

uv run python scripts/demo/run_all_demos.py --base-url http://localhost:8000
```

### Optional: Run all demos with recordings (needs WAVs + SDR TX for TX steps)

Put WAVs in `scripts/demo/recordings/` (see [option-c-recording-scripts.md](option-c-recording-scripts.md)), then:

```bash
cd /mnt/c/Users/MeMyself/monorepo/radioshaq
source .venv-wsl/bin/activate

uv run python scripts/demo/run_all_demos.py --base-url http://localhost:8000 --recordings-dir scripts/demo/recordings
```

If you have HackRF attached to HQ and want to require it for TX demos:

```bash
uv run python scripts/demo/run_all_demos.py --base-url http://localhost:8000 --recordings-dir scripts/demo/recordings --require-hardware
```

---

## Option B: Full demo (HackRF receiver + stream + run-all-demos)

Requires: HackRF attached to WSL (usbipd-win), libhackrf + pyhackrf2 in WSL, Postgres, env vars above.

### One-time: Postgres + migrations

```bash
cd /mnt/c/Users/MeMyself/monorepo
source radioshaq/.venv-wsl/bin/activate
uv run radioshaq launch docker
cd radioshaq && uv run alembic upgrade head
cd /mnt/c/Users/MeMyself/monorepo/radioshaq
```

### Terminal 1 — HQ API

```bash
cd /mnt/c/Users/MeMyself/monorepo/radioshaq
source .venv-wsl/bin/activate

export RADIOSHAQ_JWT__SECRET_KEY="demo-secret-change-me"
export RADIOSHAQ_RADIO__RECEIVER_UPLOAD_STORE=true
export RADIOSHAQ_RADIO__RECEIVER_UPLOAD_INJECT=true
export RADIOSHAQ_BUS_CONSUMER_ENABLED=1
export RADIOSHAQ_MODE=hq
export RADIOSHAQ_RADIO__SDR_TX_ENABLED=true
export RADIOSHAQ_RADIO__SDR_TX_BACKEND=hackrf

export MISTRAL_API_KEY="sk-your-mistral-key"
export RADIOSHAQ_LLM__MISTRAL_API_KEY="$MISTRAL_API_KEY"
export ELEVENLABS_API_KEY="sk-your-elevenlabs-key"

uv run radioshaq run-api
```

Leave running.

### Terminal 2 — Receiver token, then HackRF receiver

```bash
cd /mnt/c/Users/MeMyself/monorepo/radioshaq
source .venv-wsl/bin/activate

TOKEN=$(curl -s -X POST "http://localhost:8000/auth/token?subject=receiver&role=field&station_id=HACKRF-DEMO" | jq -r .access_token)
export HQ_TOKEN="$TOKEN"

export JWT_SECRET="demo-secret-change-me"
export SDR_TYPE=hackrf
export HACKRF_INDEX=0
export STATION_ID=HACKRF-DEMO
export HQ_URL=http://localhost:8000
export RECEIVER_MODE=nfm
export RECEIVER_AUDIO_RATE=48000

uv run radioshaq run-receiver --host 0.0.0.0 --port 8765
```

Leave running.

### Terminal 3 — Run all demos with recordings

```bash
cd /mnt/c/Users/MeMyself/monorepo/radioshaq
source .venv-wsl/bin/activate

uv run python scripts/demo/run_all_demos.py --base-url http://localhost:8000 --recordings-dir scripts/demo/recordings --require-hardware
```

### Optional: Live HackRF stream (Terminal 4)

While HQ and receiver are running, to actually stream from the HackRF to HQ for a short time:

```bash
cd /mnt/c/Users/MeMyself/monorepo/radioshaq
source .venv-wsl/bin/activate

uv run python scripts/demo/stream_receiver_ws.py --hq-url http://localhost:8000 --receiver-url http://localhost:8765 --frequency 145000000 --duration 30
```

---

## Quick reference

| Step | Terminal | What runs |
|------|----------|-----------|
| 0 | any | `uv run radioshaq launch docker` (once), `cd radioshaq && uv run alembic upgrade head` (once) |
| 1 | 1 | `uv run radioshaq run-api` (HQ) |
| 2 | 2 | (Option B only) Get `HQ_TOKEN`, then `uv run radioshaq run-receiver` |
| 3 | 3 (or 2 for A) | `uv run python scripts/demo/run_all_demos.py ...` |
| 4 | 4 (optional) | `uv run python scripts/demo/stream_receiver_ws.py ...` (live RX) |

Replace `/mnt/c/Users/MeMyself/monorepo` with your actual monorepo path in WSL (e.g. `$(pwd)` if you are already in the repo).
