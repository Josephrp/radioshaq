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

| Service / script      | How it gets a token |
|-----------------------|----------------------|
| **run_demo.py**       | Calls `/auth/token` with `subject=demo-op1`, `role=field`, `station_id=DEMO-01`. No flags needed. |
| **inject_audio.py**   | Pass `--subject op1` (and optional `--role field`, `--station-id STATION-01`). Script calls `/auth/token` then uses the token for inject/relay. For **TTS-only** (no inject), no token needed. |
| **curl / manual**     | Call `POST /auth/token?...` once, then set `Authorization: Bearer <access_token>` on every request. |

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
