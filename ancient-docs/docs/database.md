# Database and migrations

## Database URL

PostgreSQL with PostGIS is used for operator locations, transcripts, coordination events, and registered callsigns. The local Docker Compose exposes Postgres on **host port 5434** (container 5432) to avoid conflict with a local PostgreSQL.

Default URL (sync for migrations):

- `postgresql://radioshaq:radioshaq@127.0.0.1:5434/radioshaq`

For the async app (asyncpg):

- `postgresql+asyncpg://radioshaq:radioshaq@127.0.0.1:5434/radioshaq`

Set `DATABASE_URL` if you use different host/port/credentials.

## Running migrations (Alembic)

Migrations live under `infrastructure/local/alembic/`. On some hosts (e.g. Windows), running the `alembic` CLI with `-c infrastructure/local/alembic.ini` can fail with *"Failed to canonicalize script path"*. Use the **runner script** instead (from the **radioshaq** directory):

```bash
# Upgrade to latest
python infrastructure/local/run_alembic.py upgrade head

# Show current revision
python infrastructure/local/run_alembic.py current

# Generate a new migration (autogenerate from models)
python infrastructure/local/run_alembic.py revision --autogenerate -m "describe_change"

# Downgrade one revision
python infrastructure/local/run_alembic.py downgrade -1
```

The script sets the migration script location to an absolute path so Alembic can find it. Ensure Postgres is running (e.g. `docker compose up -d postgres` in `infrastructure/local`) and `DATABASE_URL` is set if needed.

## Schema

- **operator_locations** – GIS locations for callsigns
- **transcripts** – stored radio messages (source/destination callsign, band, text)
- **coordination_events** – schedules, relay requests, etc.
- **session_states** – orchestrator session state
- **registered_callsigns** – whitelist of allowed callsigns (see [PLAN-callsign-registration-audio-routes.md](PLAN-callsign-registration-audio-routes.md))
