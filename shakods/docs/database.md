# Database: Launch and Migrations

## What you need

- **PostgreSQL 16** with the **PostGIS** extension (for spatial data).
- The app expects the **asyncpg** driver in the connection URL (e.g. `postgresql+asyncpg://...`).

## 1. Launch the database

### Option A: Docker Compose (recommended)

From the **monorepo root** (or from `shakods` if your paths are relative to that):

```bash
cd shakods
docker compose -f infrastructure/local/docker-compose.yml up -d postgres
```

Or from `infrastructure/local`:

```bash
cd infrastructure/local
docker compose up -d postgres
```

This starts:

- **Image**: `postgis/postgis:16-3.4`
- **Host**: `127.0.0.1`
- **Port**: `5434` (mapped from container 5432 to avoid conflict with a local PostgreSQL on 5432)
- **User**: `shakods`
- **Password**: `shakods`
- **Database**: `shakods`

Wait until the container is healthy (e.g. `docker compose ps` shows healthy).

### Option B: Local PostgreSQL + PostGIS

- Install PostgreSQL 16 and the PostGIS extension.
- Create a database (e.g. `shakods`) and ensure PostGIS is enabled:

  ```sql
  CREATE EXTENSION IF NOT EXISTS postgis;
  ```

- Use a URL in this form (asyncpg required):

  `postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DATABASE`

## 2. Connection URL

Default (matches Docker Compose on port 5434):

- **URL**: `postgresql+asyncpg://shakods:shakods@127.0.0.1:5434/shakods`
- Optional: put `DATABASE_URL=...` in a `.env` file in the project root (loaded by Alembic and app).
- Override **`DATABASE_URL`** if you use different credentials or host/port:

  ```bash
  export DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/dbname"
  ```

Config is in `shakods/config/schema.py` (`DatabaseConfig.postgres_url`); env overrides it when set.

## 3. Run Alembic migrations

From the **`shakods`** directory (project root for the app):

```bash
# Apply all migrations (creates tables, PostGIS extension, indexes)
uv run alembic-upgrade
```

Or explicitly:

```bash
uv run alembic -c infrastructure/local/alembic.ini upgrade head
```

- **First run**: Creates `alembic_version`, enables PostGIS, and creates `operator_locations`, `transcripts`, `coordination_events`, `session_states`.
- **Later runs**: Apply any new migrations in `infrastructure/local/alembic/versions/`.

### Other Alembic commands

```bash
# Show current revision
uv run alembic-current

# Generate SQL only (no DB connection)
uv run alembic-upgrade-sql
```

## 4. Add or change schema (new migrations)

After changing `shakods/database/models.py`:

```bash
cd shakods
uv run alembic -c infrastructure/local/alembic.ini revision --autogenerate -m "describe_your_change"
```

Edit the new file under `infrastructure/local/alembic/versions/` if needed (e.g. PostGIS types, data backfills), then:

```bash
uv run alembic-upgrade
```

## 5. Port 5432 vs 5434

Alembic’s `env.py` uses port **5434** when talking to Postgres. If `DATABASE_URL` (or your config) points at `127.0.0.1:5432` or `localhost:5432`, it is **rewritten to 5434** so migrations hit the Docker Postgres. To use a different host/port, set `DATABASE_URL` explicitly (e.g. to `...@127.0.0.1:5434/shakods`).

## 6. If `alembic upgrade head` still fails from the host (e.g. password auth)

If you see `InvalidPasswordError` when running Alembic from the host while the container is healthy, you can apply migrations by piping SQL into the container:

```bash
# From shakods directory (PowerShell)
uv run alembic -c infrastructure/local/alembic.ini upgrade head --sql | Out-String | docker exec -i shakods-postgres psql -U shakods -d shakods
```

Or from a shell that supports pipes:

```bash
uv run alembic-upgrade-sql | docker exec -i shakods-postgres psql -U shakods -d shakods
```

Then ensure your app uses the same database (e.g. `DATABASE_URL=postgresql+asyncpg://shakods:shakods@127.0.0.1:5434/shakods`). If the host still cannot connect, run the API from inside Docker (same network as Postgres).

## 7. Test database (optional)

For integration tests, a second container is defined:

```bash
docker compose -f infrastructure/local/docker-compose.yml up -d postgres-test
```

- **Port**: `5433` (mapped from container 5432)
- **Database**: `shakods_test`
- Use `DATABASE_URL=postgresql+asyncpg://shakods:shakods@localhost:5433/shakods_test` when running tests that need the DB.
