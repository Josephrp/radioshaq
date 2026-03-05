# RadioShaq

RadioShaq for RadioShaq: ham radio AI orchestration and remote SDR reception.

**PyPI long description:** [.github/PYPI_README.md](PYPI_README.md) is a user-facing README for the package (interactive setup, CLI, quick start). To use it as the PyPI project description, set `readme = "../.github/PYPI_README.md"` in `radioshaq/pyproject.toml` when building from the repo root, or copy its contents into `radioshaq/README.md` before publishing.

**Published code in this repo:**

- **[radioshaq/](radioshaq/)** — RadioShaq (formerly SHAKODS): AI-powered orchestrator for ham radio, emergency comms, and field–HQ coordination. Includes the **remote receiver** (SDR listen-only station) as `radioshaq.remote_receiver`; run with `radioshaq run-receiver`.

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
radioshaq/                   # Main RadioShaq application (single PyPI package)
├── radioshaq/               # Python package (API, radio, audio, orchestrator)
│   └── remote_receiver/     # Bundled SDR receiver (run-receiver)
├── web-interface/           # React frontend (Vite + TypeScript)
├── tests/                   # pytest suite (unit + integration + remote_receiver)
├── infrastructure/          # Docker, PM2, AWS Lambda, Alembic
└── scripts/                # Demo and utility scripts

docs/                        # Implementation plans and hardware notes
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

GPL-2.0-only
