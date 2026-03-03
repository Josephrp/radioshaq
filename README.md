# RadioShaq

Monorepo for RadioShaq: ham radio AI orchestration and remote SDR reception.

**Published code in this repo:**

- **[radioshaq/](radioshaq/)** — RadioShaq (formerly SHAKODS): AI-powered orchestrator for ham radio, emergency comms, and field–HQ coordination.
- **[remote_receiver/](remote_receiver/)** — Remote SDR receiver station (RTL-SDR / HackRF) with JWT auth and HQ upload.

The directories `codex/`, `mistral-vibe-main/`, and `nanobot-main/` are **reference-only** and are not part of the published codebase; they are listed in `.gitignore`.

---

## Quick start (main app)

From the `radioshaq/` directory:

```bash
# 1. Install
uv sync --extra dev --extra test

# 2. Start Postgres (Docker, port 5434)
cd infrastructure/local && docker compose up -d postgres && cd ../..

# 3. Migrations
uv run alembic -c infrastructure/local/alembic.ini upgrade head

# 4. Start API
uv run python -m radioshaq.api.server
# API: http://localhost:8000/docs
```

Full install and usage: see the main app [README.md](radioshaq/README.md) in that directory.

---

## Project structure

```
radioshaq/                   # Main RadioShaq application
├── radioshaq/               # Python package (API, radio, audio, orchestrator)
├── web-interface/          # React frontend (Vite + TypeScript)
├── tests/                  # pytest suite (unit + integration)
├── infrastructure/         # Docker, PM2, AWS Lambda, Alembic
└── scripts/                # Demo and utility scripts

remote_receiver/            # Remote SDR receiver station
├── receiver/               # FastAPI server for SDR data
└── pyproject.toml          # Separate uv project

docs/                       # Implementation plans and hardware notes
codex/                      # Reference-only (gitignored)
mistral-vibe-main/          # Reference-only (gitignored)
nanobot-main/               # Reference-only (gitignored)
```

---

## Development

```bash
# Run tests
cd radioshaq
uv run pytest tests/unit tests/integration -v

# Type check
uv run mypy radioshaq

# Lint / format
uv run ruff check . && uv run ruff format .
```

---

## License

MIT
