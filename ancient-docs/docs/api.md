# SHAKODS API Reference

REST API for the Strategic Autonomous Ham Radio and Knowledge Operations Dispatch System.

## Base URL

- **Local**: `http://localhost:8000` (or the port set by `uvicorn`)
- **AWS**: `https://{api-id}.execute-api.{region}.amazonaws.com/{stage}` (from CloudFormation output `ApiEndpoint`)

## Authentication

Most endpoints require a **Bearer JWT**. There is **no auth required to obtain a token**: call `POST /auth/token` with `subject`, `role` (e.g. `field` or `hq`), and optional `station_id`; use the returned `access_token` in the header on all protected requests.

- **Header**: `Authorization: Bearer <access_token>`
- **Obtain token**: `POST /auth/token?subject=op1&role=field&station_id=STATION-01` → `{"access_token": "<jwt>", "token_type": "bearer"}`

Full auth description, roles, config, and exact commands: [auth.md](auth.md).

---

## Endpoints

### Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | Liveness probe |
| GET | `/health/ready` | No | Readiness probe |

**Response (200)**  
`{"status": "ok"}` or `{"status": "ready"}`

---

### Auth

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/token` | No | Issue access token |
| POST | `/auth/refresh` | No | Refresh access token |
| GET | `/auth/me` | Yes | Current token claims |

#### POST /auth/token

**Query/body**  
- `subject` (string, required): User/station identifier  
- `role` (string, default `field`): `field` or `hq`  
- `station_id` (string, optional): Station ID  

**Response (200)**  
`{"access_token": "<jwt>", "token_type": "bearer"}`

#### POST /auth/refresh

**Body**  
- `refresh_token` (string): Valid refresh token  

**Response (200)**  
`{"access_token": "<jwt>", "token_type": "bearer"}`

#### GET /auth/me

**Headers**  
- `Authorization: Bearer <token>`

**Response (200)**  
`{"sub": "...", "role": "...", "station_id": "...", "scopes": [...]}`

---

### Radio

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/radio/propagation` | Yes | Propagation prediction between two points |
| GET | `/radio/bands` | Yes | List supported bands |

#### GET /radio/propagation

**Query**  
- `lat_origin`, `lon_origin`: Origin latitude/longitude  
- `lat_dest`, `lon_dest`: Destination latitude/longitude  

**Response (200)**  
JSON with propagation-related fields (e.g. distance, band suggestions).

#### GET /radio/bands

**Response (200)**  
`{"bands": ["160m", "80m", ...]}`

---

### Messages

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/messages/process` | Yes | Submit message for REACT orchestration |
| POST | `/messages/relay` | Yes | Translate message from one band to another, store both transcripts |

#### POST /messages/relay (band translation)

**Body**  
- `message` (string, required): Text to relay  
- `source_band`, `target_band` (string, required): e.g. `40m`, `2m`  
- `source_frequency_hz`, `target_frequency_hz` (number, optional)  
- `source_callsign` (string, default `UNKNOWN`)  
- `destination_callsign` (string, optional)  
- `session_id` (string, optional)  
- `source_audio_path`, `target_audio_path` (string, optional)  

**Response (200)**  
`{"ok": true, "source_transcript_id": <id>, "relayed_transcript_id": <id>, "source_band", "target_band", ...}`  

Stores one transcript on the source band and one on the target band with `metadata.relay_from_transcript_id` linking them.

---

#### POST /messages/process

**Body**  
- `message` or `text` (string, required): Content to process  

**Response (200)**  
`{"success": true|false, "message": "...", "task_id": "..."}`

**Errors**  
- `400`: Missing `message`/`text`  
- `503`: Orchestrator not available  

---

### Inject (demo / user injection)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/inject/message` | Yes | Push message into RX injection queue (for demo without hardware) |

#### POST /inject/message

**Body**  
- `text` (string, required): Message to inject as “received”  
- `band` (string, optional): e.g. `40m`, `2m`  
- `frequency_hz` (number, optional)  
- `mode` (string, default `PSK31`)  
- `source_callsign`, `destination_callsign` (string, optional)  
- `audio_path` (string, optional): Path to audio file for transcript storage  
- `metadata` (object, optional)  

**Response (200)**  
`{"ok": true, "message": "Injected", "qsize": <n>}`  

Consumers (e.g. `radio_rx` when not using FLDIGI) read from the injection queue. See [demo-two-local-one-remote.md](demo-two-local-one-remote.md).

---

### Transcripts (search)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/transcripts` | Yes | Search transcripts by callsign, band, frequency, mode, since |

#### GET /transcripts

**Query**  
- `callsign`: Filter by source or destination callsign  
- `frequency_min`, `frequency_max`: Hz  
- `mode`: e.g. FM, PSK31  
- `band`: Filter by `extra_data.band` (e.g. 40m, 2m)  
- `since`: ISO 8601 timestamp  
- `limit`: Max results (default 100, max 500)  

**Response (200)**  
`{"transcripts": [...], "count": n}` – each transcript includes `id`, `transcript_text`, `source_callsign`, `destination_callsign`, `frequency_hz`, `mode`, `extra_data` (band, relay_from_transcript_id, etc.).

---

## Lambda (API Gateway)

When deployed to AWS, the API Gateway proxy uses a single Lambda handler that exposes:

- **GET /health** – Health check (no auth)
- **POST /orchestrate** – Orchestration request (JWT required)

### POST /orchestrate (Lambda)

**Headers**  
- `Authorization: Bearer <token>`

**Body**  
- `request` (string): User request text  
- `context` (object, optional): Extra context  

**Response (202)**  
- With Step Functions: `{"execution_arn": "...", "status": "started"}`  
- Without: `{"status": "accepted", "message": "..."}`  

**Errors**  
- `401`: Missing or invalid token  

---

## Error format

JSON errors typically include:

- `detail`: String or list of validation errors  
- `status_code`: HTTP status  

Example: `{"detail": "message or text required"}`
