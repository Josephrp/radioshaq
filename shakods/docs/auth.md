# SHAKODS Authentication

SHAKODS uses **JWT (JSON Web Token)** Bearer authentication. Most API endpoints require a valid access token in the `Authorization` header. Token issuance is done via the API itself (no separate identity provider out of the box).

---

## Overview

- **Obtain token**: `POST /auth/token` — **no auth required**. You pass a subject (user/station ID), role, and optional station_id. The API returns an access token.
- **Use token**: Send **`Authorization: Bearer <access_token>`** on all protected endpoints.
- **Roles**: `field` (field station / operator), `hq` (headquarters), or `receiver` (receiver-only). The API does not currently enforce role-based access per endpoint; any valid token can call any protected route.
- **Expiry**: Access tokens default to 30 minutes. Use `POST /auth/refresh` with a refresh token to get a new access token without re-identifying.

---

## Endpoints by auth

| Auth required? | Endpoints |
|----------------|-----------|
| **No** | `GET /health`, `GET /health/ready`, `POST /auth/token`, `POST /auth/refresh` |
| **Yes (Bearer)** | `GET /auth/me`, `GET /radio/bands`, `GET /radio/propagation`, `POST /messages/process`, `POST /messages/relay`, `GET /transcripts`, `POST /inject/message` |

---

## Obtaining a token

### POST /auth/token

**Parameters (query or body):**

- **subject** (required): User or station identifier (e.g. operator name, callsign, or machine ID).
- **role** (optional): `field` (default), `hq`, or `receiver`.
- **station_id** (optional): Station ID (e.g. callsign or STATION-01). Useful for field stations.

**Response:** `{"access_token": "<jwt>", "token_type": "bearer"}`

### Bash (curl)

```bash
# Field operator
curl -s -X POST "http://localhost:8000/auth/token?subject=op1&role=field&station_id=STATION-01"

# HQ operator
curl -s -X POST "http://localhost:8000/auth/token?subject=netcontrol&role=hq"

# Capture token for later use
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/token?subject=op1&role=field&station_id=STATION-01" | jq -r .access_token)
echo $TOKEN
```

### PowerShell

```powershell
# Field operator
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/auth/token?subject=op1&role=field&station_id=STATION-01"

# Capture token (PowerShell 7+ or parse JSON manually)
$r = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/auth/token?subject=op1&role=field&station_id=STATION-01"
$TOKEN = $r.access_token
```

### Remote API

Replace `localhost:8000` with your API base URL:

```bash
TOKEN=$(curl -s -X POST "http://REMOTE_HOST:8000/auth/token?subject=op1&role=field&station_id=STATION-01" | jq -r .access_token)
```

---

## Using the token

Send the token in the **Authorization** header on every protected request:

```bash
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/auth/me"
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/radio/bands"
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"text":"Hello"}' "http://localhost:8000/inject/message"
```

PowerShell:

```powershell
$headers = @{ Authorization = "Bearer $TOKEN" }
Invoke-RestMethod -Uri "http://localhost:8000/auth/me" -Headers $headers
```

---

## Refresh token

To get a new access token without re-calling `/auth/token`, use a **refresh token**. The API returns a refresh token only when you use the refresh flow (see auth implementation). Currently, the public `POST /auth/token` returns only an access token. Refresh is available via `POST /auth/refresh` with body `{"refresh_token": "<refresh_token>"}` when you have one (e.g. from a custom client that requests it).

---

## Configuration

JWT behaviour is controlled by config (file or environment):

- **JWT secret**: Must be the same across all API instances that should accept each other’s tokens. Set a strong secret in production.
- **Access token expiry**: Default 30 minutes (`access_token_expire_minutes`).
- **Refresh token expiry**: Default 7 days (`refresh_token_expire_days`).

Environment variables (if using pydantic-settings):

- `SHAKODS_JWT_SECRET_KEY` or `JWT_SECRET_KEY`
- `SHAKODS_JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, etc.

In production, do **not** use the default dev secret; use a long random value and keep it secret.

---

## Auth for demo scripts

- **run_demo.py**: Obtains a token internally with `subject=demo-op1`, `role=field`, `station_id=DEMO-01`. No manual token needed if the API is reachable.
- **inject_audio.py**: Pass **`--subject op1`** (and optionally `--role field`, `--station-id STATION-01`). The script calls `POST /auth/token` with those values and then uses the token for inject/relay. For **TTS-only** (no inject), no token is required.

See [scripts/demo/README.md](../scripts/demo/README.md) and [api.md](api.md) for endpoint details.

---

## Mistral / LLM (agent)

The REACT agent (orchestrator and judge) uses **Mistral** (or another provider via LiteLLM) with an **API key**, not JWT and not OAuth. Set **`MISTRAL_API_KEY`** in the environment so the LLM client can call the Mistral API. For details (OAuth stub, config, when the agent is used), see [mistral-api.md](mistral-api.md).
