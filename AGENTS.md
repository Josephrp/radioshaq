# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

RadioShaq is a Python (FastAPI) + React (Vite/TypeScript) application for AI-powered ham radio orchestration. The primary backend lives in `radioshaq/` and the React frontend in `radioshaq/web-interface/`.

### Services

| Service | Port | How to start |
|---------|------|-------------|
| PostgreSQL (PostGIS) | 5434 | `docker compose -f radioshaq/infrastructure/local/docker-compose.yml up -d postgres` |
| FastAPI backend | 8000 | `cd radioshaq && RADIOSHAQ_MEMORY__HINDSIGHT_ENABLED=false uv run python -m radioshaq.api.server` |
| React frontend (dev) | 3000 | `cd radioshaq/web-interface && VITE_SHAKODS_API=http://localhost:8000 npx vite --host 0.0.0.0 --port 3000` |

### Docker setup (required for cloud agents)

Docker must be started before PostgreSQL. In the Cursor Cloud VM:
```bash
sudo dockerd &>/tmp/dockerd.log &
sleep 3
sudo chmod 666 /var/run/docker.sock
```

### Database migrations

After starting PostgreSQL, run migrations from `radioshaq/`:
```bash
cd radioshaq && uv run python infrastructure/local/run_alembic.py upgrade head
```

### Key commands

- **Lint:** `cd radioshaq && uv run ruff check .` (pre-existing warnings in the codebase are expected)
- **Format:** `cd radioshaq && uv run ruff format .`
- **Type check:** `cd radioshaq && uv run mypy radioshaq`
- **Unit + integration tests:** `cd radioshaq && uv run pytest tests/unit tests/integration -v`
- **Frontend build:** `cd radioshaq/web-interface && npm run build`

### Non-obvious notes

- Set `RADIOSHAQ_MEMORY__HINDSIGHT_ENABLED=false` when starting the API without the optional Hindsight container, otherwise memory endpoints will attempt to connect to a non-existent Hindsight service.
- The API uses port 5434 for Postgres (not 5432) to avoid clashing with any system Postgres.
- JWT tokens for dev can be obtained without prior auth: `POST /auth/token?subject=dev-op1&role=field&station_id=STATION-01`.
- The `uv.lock` file is the lockfile for Python dependencies; always use `uv sync` (not pip) for dependency management.
- Frontend `package-lock.json` is the lockfile; use `npm install` for frontend deps.
- Two pre-existing test failures in `tests/unit/memory/test_manager.py` are known (asyncpg DataError on metadata dict serialization).
- The pre-push hook (`.githooks/pre-push`) runs version sync check, dependency install, and full test suite. Enable with `git config core.hooksPath .githooks`.
