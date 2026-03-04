# Interactive Setup – Feature Implementation Plan

This document describes how the RadioShaq CLI and setup flow work today, and provides a complete feature implementation plan for an **interactive setup** that guides users from a fresh clone to a running station (and optionally to production-ready configuration).

---

## 1. Current state: how the CLI and setup work

### 1.1 CLI entry point and structure

- **Entry point:** `radioshaq` (from `pyproject.toml` → `radioshaq.cli:app`).
- **Framework:** [Typer](https://typer.tigarcia.io/); no interactive prompts today.
- **Environment:** Commands use `RADIOSHAQ_API` (default `http://localhost:8000`) and `RADIOSHAQ_TOKEN` for authenticated calls. These are read from the environment; the CLI does not create or edit `.env` or config files.

**Current commands:**

| Command / group | Subcommands | Purpose |
|-----------------|-------------|---------|
| `health` | — | GET /health or /health/ready |
| `token` | — | POST /auth/token → print access_token |
| `run-api` | — | Start uvicorn (API server) |
| `callsigns` | list, add, remove, register-from-audio | Callsign whitelist |
| `message` | process, inject, whitelist-request, relay | REACT, inject, relay |
| `transcripts` | list, get, play | Transcripts API |
| `radio` | bands, send-tts | Bands list, TTS over radio |

There is **no** `setup`, `init`, or `configure` command.

### 1.2 Existing “setup” flow (PowerShell only)

**Script:** `radioshaq/infrastructure/local/setup.ps1`  
**Usage:** From `radioshaq/`: `.\infrastructure\local\setup.ps1`

**What it does (in order):**

1. **Prerequisites:** Checks for `uv`, Python 3.11+, Node (optional), Docker (optional).
2. **Install:** `uv sync --extra dev --extra test` (or pip/venv fallback).
3. **Directories:** Creates `logs`, `.radioshaq`, `.radioshaq/data`, `.radioshaq/config`.
4. **Config file:** If `.radioshaq/config.yaml` does not exist, writes a **fixed** default YAML (mode, database URL, jwt, llm, radio, field, pm2). No user prompts.
5. **Docker:** If Docker is available, runs `docker compose up -d postgres` from `infrastructure/local`, waits for Postgres on 127.0.0.1:5434, then runs `alembic -c infrastructure/local/alembic.ini upgrade head`.
6. **PM2:** If Node is available, `npm install -g pm2`.
7. **Summary:** Prints next steps (set MISTRAL_API_KEY, start API, run tests, open docs).

**Gaps:**

- No interactive questions (mode, DB URL, API keys, radio, etc.).
- No `.env` creation; API keys and secrets are left to the user.
- Windows-only (PowerShell); no equivalent Bash script or cross-platform CLI.
- Config is written to `.radioshaq/config.yaml`, while the app’s default in code is `config.yaml` in the current working directory — so behavior depends on where the process is started and whether `RADIOSHAQ_YAML_FILE` (or equivalent) is set.
- No “verify” step (e.g. health check or DB ping after setup).
- No option to run in non-interactive/CI mode.

### 1.3 Config and env loading (relevant to setup)

- **Config model:** `radioshaq.config.schema.Config` (Pydantic Settings).
- **Sources (priority):** Defaults → config file → environment variables (env wins).
- **Config file:** Default `yaml_file="config.yaml"` (relative to CWD when the app runs). Optional JSON. Path can be overridden if the loader supports it (e.g. env).
- **Env:** Prefix `RADIOSHAQ_`, nested keys with `__` (e.g. `RADIOSHAQ_DATABASE__POSTGRES_URL`).
- **Helpers:** `load_config(path)` and `save_config(config, path)` in `schema.py` for explicit file load/save.
- **Alembic:** Uses `DATABASE_URL` or `POSTGRES_*` from env (see `radioshaq/alembic/env.py` and `infrastructure/local/alembic/env.py`).

So an interactive setup must:

- Decide where to write config: e.g. `config.yaml` in project root (radioshaq/) and/or `.env` in project root.
- Write env vars that Alembic and the server both understand (e.g. `POSTGRES_*` or `DATABASE_URL`; `RADIOSHAQ_*` for the app).

---

## 2. Goals for interactive setup

- **Primary:** First-time users can run a single command (e.g. `radioshaq setup`) and be guided through choices; the result is a working API (and optionally DB + token).
- **Secondary:** Re-running setup can adjust or add options (e.g. add LLM key, enable radio) without wiping existing config; support “non-interactive” mode for CI/scripts.
- **Consistency:** One flow for Windows, macOS, and Linux via the Python CLI; reduce reliance on PowerShell-only scripts for core setup.
- **Documentation:** Point users to `.env.example` and `config.example.yaml`; optionally open docs (quick-start, configuration) at the end.

---

## 3. User flows

### 3.1 First-time interactive (default)

1. User runs `radioshaq setup` (or `radioshaq setup --interactive`).
2. CLI detects existing `.env` / `config.yaml` / `.radioshaq/config.yaml` and asks whether to use as base or start fresh (or “reconfigure”).
3. Prompts (with defaults and skip option where sensible):
   - **Mode:** field / hq / receiver (default: field).
   - **Database:** Use Docker Postgres (default port 5434) / existing Postgres (URL or host, port, user, password, db) / skip DB for now.
   - **Secrets:** JWT secret (optional prompt; default dev secret with warning), LLM provider + API key (optional; can skip and set later).
   - **Memory:** Enable memory, Hindsight URL (optional).
   - **Radio:** Enable radio? If yes: rig model, port, optional FLDIGI/packet (can be minimal).
   - **Audio/voice:** Enable voice_rx pipeline? (optional; can skip).
   - **Field/HQ:** If mode=field: station_id, HQ URL, auth token (optional). If mode=hq: host/port (optional override).
4. Write outputs:
   - `.env` (at least `POSTGRES_*` or `DATABASE_URL`, optionally `RADIOSHAQ_*` for overrides, `MISTRAL_API_KEY` or other LLM key, `RADIOSHAQ_JWT__SECRET_KEY` for production).
   - `config.yaml` (or `.radioshaq/config.yaml` — see design) with non-secret choices; keep secrets in `.env` where possible.
5. Optional steps (prompt user):
   - Start Docker Postgres if chosen and Docker available.
   - Run migrations (`alembic upgrade head` with correct env/config path).
   - Verify: `radioshaq health` or direct DB ping.
   - Get token: `radioshaq token` and optionally append `RADIOSHAQ_TOKEN=...` to `.env` (or instruct user).
6. Summary: “Setup complete. Start API: radioshaq run-api. See docs/quick-start.md and docs/configuration.md.”

### 3.2 Re-run / reconfigure

- `radioshaq setup --reconfigure` or “Update existing configuration” in interactive flow.
- Load existing `Config` from current config file (and env); prompt only for sections user wants to change (e.g. “Change LLM? (y/n)” then provider/key).
- Merge into existing files; do not overwrite entire `.env` or config without confirmation if they already exist.

### 3.3 Non-interactive / CI

- `radioshaq setup --no-input` (or `--ci`) with options passed via flags and/or env.
- Example: `radioshaq setup --no-input --mode field --db-url postgresql://... --jwt-secret xxx --llm-provider mistral --llm-api-key $MISTRAL_API_KEY`.
- Writes `.env` and `config.yaml` (or only env) and optionally runs migrations; exits 0 on success. No prompts.

### 3.4 “Quick start” minimal

- `radioshaq setup --quick`: minimal prompts (mode, “use Docker for DB?”), use all defaults otherwise, write config + .env, start Docker if yes, run migrations, print “Run: radioshaq run-api”.

---

## 4. Technical design

### 4.1 Where it lives

- **CLI command:** New Typer command under the same `app`: `setup` (and optionally `init` as alias).
- **Implementation:** Prefer a dedicated module to keep `cli.py` thin, e.g. `radioshaq/cli/setup.py` or `radioshaq/setup.py`, containing:
  - Prompt logic (interactive).
  - Decision logic (Docker vs existing DB, paths).
  - File writing: `.env` (append or overwrite by choice), `config.yaml` (via `save_config` or structured YAML write).
  - Optional: subprocess or in-process calls for Docker, Alembic, health check.

### 4.2 Config file location

- **Recommendation:** Write to **project root** (directory containing `pyproject.toml` when running `radioshaq`): `config.yaml` and `.env`. This matches the default `yaml_file="config.yaml"` when the server is started from the same root.
- **Alternative:** Write to `~/.radioshaq/` (align with `workspace_dir`) and set `RADIOSHAQ_YAML_FILE` or equivalent in `.env` so the server finds it. Document clearly.
- **Decision:** Implement one canonical location (e.g. project root) and document in quick-start and configuration; optionally support `--config-dir` or `--workspace-dir` for advanced users.

### 4.3 Prompts and defaults

- Use **Typer** for CLI; for interactive prompts, use either:
  - `typer.prompt()` / `typer.confirm()` (simple), or
  - **Rich** (already a dev dependency) for better formatting and prompts, or
  - a small library (e.g. `questionary`, `inquirer`) for menus and validation — add only if needed.
- Defaults must match `radioshaq.config.schema` (e.g. mode=field, postgres_url with 5434, jwt secret default, llm provider/model).

### 4.4 Secrets

- **JWT:** Prompt for production secret if user says “production” or leave default with a clear warning.
- **API keys:** Prompt for LLM key (or read from env if already set); write to `.env` only, not to `config.yaml` in plain text (or write to config with a comment “set via RADIOSHAQ_LLM__MISTRAL_API_KEY”).
- **.env:** Ensure `.env` is in `.gitignore`; setup must not commit secrets.

### 4.5 Docker and migrations

- **Docker:** If user chooses “use Docker for Postgres”, check `docker` availability; run `docker compose -f infrastructure/local/docker-compose.yml up -d postgres` (from project root). Wait for port 5434 (or configured port) with a short retry loop.
- **Migrations:** Run Alembic from project root with env that includes `DATABASE_URL` or `POSTGRES_*` (from the same `.env` just written). Use existing `radioshaq.scripts.alembic_runner` or subprocess `alembic -c infrastructure/local/alembic.ini upgrade head` with env inherited or passed.
- **Failure handling:** If Docker or migrations fail, report clearly and do not mark setup as “complete”; suggest manual steps (see docs).

### 4.6 Verification

- After writing config and (if applicable) running migrations:
  - Set `RADIOSHAQ_API` from written config (e.g. http://localhost:8000) and run `radioshaq health` only if the user has already started the API in another terminal (optional).
  - Or run a direct DB connection test (async engine with written postgres_url) and print “Database connection OK.”
- Do not start the API server from within `setup` by default (user starts it with `radioshaq run-api`).

### 4.7 Backward compatibility

- Existing `infrastructure/local/setup.ps1` can remain for users who prefer it; document that `radioshaq setup` is the recommended cross-platform flow.
- If `radioshaq setup` finds `.radioshaq/config.yaml` and no `config.yaml`, offer to migrate or copy to project root `config.yaml` for consistency.

---

## 5. Implementation plan (phased)

### Phase 1: CLI command and skeleton (no prompts)

- Add `setup` command to `radioshaq/cli.py` (or a typer sub-app) with options: `--interactive`, `--no-input`, `--quick`, `--reconfigure`, `--config-dir`, `--force`.
- Create `radioshaq/setup.py` (or `radioshaq/cli/setup.py`) with:
  - `run_setup(interactive: bool, no_input: bool, quick: bool, reconfigure: bool, config_dir: Path | None, force: bool) -> int`.
  - Resolve project root (directory containing `pyproject.toml`; search upward from CWD or from `__file__`).
  - Detect existing `.env`, `config.yaml`, `.radioshaq/config.yaml`.
  - For `--no-input`, require minimal env or flags (e.g. `--db-url`, `--mode`) and write default `.env` + `config.yaml`; exit 0.
- Unit test: run `radioshaq setup --no-input --mode field` with a temp dir and assert `.env` and `config.yaml` exist and contain expected keys.

### Phase 2: Interactive prompts (core only)

- Implement prompts for: mode, database (Docker / URL / skip), JWT secret (default + warning), LLM provider and API key (optional).
- Write `.env` with at least: `POSTGRES_*` or `DATABASE_URL`, `RADIOSHAQ_MODE`, `RADIOSHAQ_JWT__SECRET_KEY` (if changed), `RADIOSHAQ_LLM__PROVIDER`, `RADIOSHAQ_LLM__MISTRAL_API_KEY` (or other) if provided.
- Write `config.yaml` with mode, database section (postgres_url if not from env), jwt section (no secret in file), llm section (provider/model; no key in file).
- Use `load_config` / `save_config` where possible; for `.env`, append or overwrite line-by-line (preserve existing vars if reconfigure).

### Phase 3: Docker and migrations

- If “use Docker” and Docker available: start Postgres container, wait for port.
- Set env (or pass to subprocess) and run Alembic upgrade.
- On failure: print message and return non-zero; do not overwrite config with broken state.

### Phase 4: Optional steps and verification

- After write: optional “Run migrations now? (y/n)”; if user already chose Docker, run migrations automatically.
- Optional “Verify database connection? (y/n)”: run async engine connect and report OK/fail.
- Optional “Get a token and save to .env? (y/n)”: start server not required; only if user has started API, call `radioshaq token` and suggest appending `RADIOSHAQ_TOKEN=...` to `.env` (or document manual step).

### Phase 5: Reconfigure and quick mode

- **Reconfigure:** Load existing config (and .env); prompt “What to change? (mode / database / jwt / llm / radio / audio / done)”; update only selected sections; merge into files.
- **Quick:** `--quick` implies minimal prompts (mode, “Docker for DB?”); all other defaults; write files; if Docker yes, start + migrate; print next steps.

### Phase 6: Radio, audio, memory, field/HQ

- Add prompts for: radio enabled, rig model, port; audio_input_enabled; memory enabled, Hindsight URL; field station_id, hq_base_url, hq_auth_token; hq host/port.
- Write corresponding sections to `config.yaml` and optional overrides to `.env`.
- Keep prompts short; link to “See docs/configuration.md for all options.”

### Phase 7: Polish and docs

- Help text: `radioshaq setup --help` documents all flags and that it writes to project root by default.
- Update **quick-start.md**: add step “(Optional) Run interactive setup: `radioshaq setup`” and point to configuration.md.
- Update **configuration.md**: add “Interactive setup” subsection pointing to `radioshaq setup` and `.env.example` / `config.example.yaml`.
- Update **README.md** (radioshaq): mention `radioshaq setup` as recommended first-time setup.
- Optional: add `docs/interactive-setup.md` describing the prompts and flows (or keep this plan as the reference).

---

## 6. Edge cases and requirements

- **No Docker:** User selects “existing Postgres” or “skip DB”; do not fail; document that migrations and API will need DB later.
- **Existing .env:** If reconfigure, merge; if first-time and `.env` exists, ask “Overwrite / merge / skip .env?”
- **Existing config.yaml:** Same: overwrite / merge / skip; for merge, load with `load_config`, update fields from prompts, `save_config`.
- **Permission errors:** Catch write errors and print clear message (e.g. “Cannot write .env: permission denied”).
- **Windows vs Unix:** Use `Path` and ensure newlines and path separators are correct for `.env` and YAML.
- **Alembic config path:** Use `infrastructure/local/alembic.ini` when running from project root; ensure `env.py` loads `.env` from project root (already done in `infrastructure/local/alembic/env.py` via `load_dotenv(project_root / ".env")`).
- **Config location when server runs:** If server is started from same project root, `config.yaml` in CWD is picked up; document that “run from radioshaq directory” is required for default behavior.

---

## 7. Testing strategy

- **Unit:** Temp directory; run `setup --no-input` with various flags; assert file contents and no crashes. See `radioshaq/tests/unit/test_setup.py`.
- **Unit:** Mock prompts; run interactive, quick, and reconfigure flows; assert written config. See same file.
- **Integration:** `radioshaq/tests/integration/test_setup_integration.py` — run_setup --no-input produces loadable config; CLI `radioshaq setup --no-input --mode field --config-dir <dir>` exits 0 and creates files.
- **Manual (checklist):** On each OS (Windows, macOS, Linux): (1) `radioshaq setup --help`; (2) `radioshaq setup --no-input --mode field` in a temp dir, confirm `.env` and `config.yaml` exist; (3) optionally run `radioshaq setup` interactive and answer prompts, then `radioshaq run-api` and `radioshaq health`.

---

## 8. Success criteria

- User can run `radioshaq setup`, answer a small set of questions, and get a working `.env` + `config.yaml` such that `radioshaq run-api` starts and (if DB was configured) migrations are applied and health checks pass.
- User can run `radioshaq setup --no-input --mode field --db-url ...` in CI and get a consistent result.
- Re-running setup with `--reconfigure` updates only requested sections without wiping secrets or other sections.
- Documentation (quick-start, configuration, README) references interactive setup and example files.

---

## 9. References

- **CLI:** `radioshaq/radioshaq/cli.py`
- **Config schema:** `radioshaq/radioshaq/config/schema.py` (`Config`, `load_config`, `save_config`)
- **Alembic:** `radioshaq/alembic/env.py`, `radioshaq/infrastructure/local/alembic/env.py`, `radioshaq/radioshaq/scripts/alembic_runner.py`
- **PowerShell setup:** `radioshaq/infrastructure/local/setup.ps1`
- **Docs:** `docs/quick-start.md`, `docs/configuration.md`, `radioshaq/.env.example`, `radioshaq/config.example.yaml`
