# SHAKODS Examples

## Config sample

- **config_sample.yaml** – Example YAML configuration. Copy to `config.yaml` or set `SHAKODS_CONFIG_PATH`. Environment variables override file values.

## Quick API usage

With the API running locally (`uv run python -m shakods.api.server` or `uv run uvicorn shakods.api.server:app --reload --port 8000`).

**Authentication:** No auth is required to get a token. Call `POST /auth/token`, then send `Authorization: Bearer <access_token>` on protected endpoints. See [docs/auth.md](../docs/auth.md).

```bash
# Health (no auth)
curl http://localhost:8000/health

# Get a token (no auth required)
curl -X POST "http://localhost:8000/auth/token?subject=operator1&role=field&station_id=STATION-01"
# Response: {"access_token":"<jwt>","token_type":"bearer"}

# Save token and use on protected endpoints
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/token?subject=operator1&role=field&station_id=STATION-01" | jq -r .access_token)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/auth/me
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/radio/bands"
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/radio/propagation?lat_origin=0&lon_origin=0&lat_dest=1&lon_dest=1"
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"message":"Schedule a net on 40m"}' http://localhost:8000/messages/process
```

## Lambda /orchestrate (AWS)

```bash
curl -X POST "https://YOUR_API.execute-api.us-east-1.amazonaws.com/staging/orchestrate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"request":"Process this message","context":{"source":"api"}}'
```

Returns `202` with `execution_arn` when Step Functions is configured.
