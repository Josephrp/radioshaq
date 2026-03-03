# SHAKODS – Get everything installed

Follow these steps from the **shakods** directory (project root).

---

## 1. Prerequisites

| Tool | Required | Install |
|------|----------|--------|
| **Python 3.11+** | Yes | [python.org](https://www.python.org/downloads/) or `winget install Python.Python.3.12` |
| **uv** | Yes (recommended) | `pip install uv` or [install uv](https://github.com/astral-sh/uv#installation) |
| **Docker** | For local Postgres | [Docker Desktop](https://www.docker.com/products/docker-desktop/) |
| **Node.js 18+** | For PM2 & integration tests | [nodejs.org](https://nodejs.org/) or `winget install OpenJS.NodeJS.LTS` |

---

## 2. Python environment and dependencies

From the **shakods** directory:

```powershell
# Windows (PowerShell)
uv sync --extra dev --extra test
```

```bash
# macOS / Linux
uv sync --extra dev --extra test
```

This creates `.venv`, installs the project, and all dev/test dependencies (pytest, ruff, mypy, etc.). No need to activate the venv when using `uv run`.

**Verify:**

```powershell
uv run python -c "import shakods; print('OK')"
uv run pytest tests/unit -v --tb=short -x
```

---

## 3. Database (optional but recommended)

If you use Docker for Postgres:

```powershell
# From shakods directory
cd infrastructure\local
docker compose up -d postgres
cd ..\..
```

Postgres listens on **port 5434** (to avoid conflict with a local 5432). Default URL:

`postgresql+asyncpg://shakods:shakods@127.0.0.1:5434/shakods`

**Run migrations:**

```powershell
uv run alembic -c infrastructure/local/alembic.ini upgrade head
```

---

## 4. Node.js and PM2 (optional)

Needed for PM2-based runs and integration tests that start the API with PM2.

**Install Node.js** if not already installed, then install PM2 globally:

```powershell
# Windows (run as current user; may need to fix npm global path)
npm install -g pm2
```

```bash
# macOS / Linux
npm install -g pm2
```

**Verify:** `pm2 --version`

If `pm2` is not found after install, add npm’s global bin to your PATH (e.g. `%APPDATA%\npm` on Windows).

---

## 5. Full automated setup (Windows)

For a one-shot setup including venv, deps, dirs, config, Docker Postgres, and PM2:

```powershell
# From shakods directory
.\infrastructure\local\setup.ps1
```

This script:

- Prefers **uv** if available (`uv sync --extra dev --extra test`), otherwise uses `pip install -e ".[dev,test]"`
- Creates `logs`, `.shakods`, and config if missing
- Starts Postgres (and Redis) via Docker on port **5434** if Docker is installed
- Waits for Postgres and runs Alembic migrations
- Installs **PM2** globally if Node.js is installed

---

## 6. Quick reference after install

| Task | Command |
|------|---------|
| Run tests (unit + integration) | `uv run pytest tests/unit tests/integration -v` |
| Start API (foreground) | `uv run python -m shakods.api.server` |
| Start API with PM2 | `pm2 start ecosystem.config.js --only shakods-api` |
| Get API token (no auth required) | `curl -s -X POST "http://localhost:8000/auth/token?subject=op1&role=field&station_id=STATION-01"` |
| Migrations | `uv run alembic -c infrastructure/local/alembic.ini upgrade head` |
| Lint/format | `uv run ruff check .` / `uv run ruff format .` |
| Type check | `uv run mypy shakods` |

**API auth:** Protected endpoints need `Authorization: Bearer <access_token>`. See [auth.md](auth.md) for full details and exact commands (Bash/PowerShell, local/remote).

---

## Troubleshooting

- **Port 5434 in use:** Stop any other process on 5434 or change the Docker Compose port mapping in `infrastructure/local/docker-compose.yml`.
- **Alembic uses wrong port:** Ensure no `DATABASE_URL` or `SHAKODS_DATABASE__POSTGRES_URL` points at 5432 if you intend to use Docker on 5434. Alembic rewrites `localhost:5432` to `127.0.0.1:5434` when that URL is set.
- **PM2 not found:** Install Node.js, then `npm install -g pm2`. Add npm global bin to PATH (e.g. `%APPDATA%\npm` on Windows).
- **Tests fail (imports):** Run from the **shakods** directory and use `uv run pytest` so the project package is on the path.
