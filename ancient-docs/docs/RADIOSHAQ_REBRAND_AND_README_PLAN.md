# RadioShaq rebrand and top-level README — implementation plan

## 1. Summary of goals

1. **Clarify repo scope** — This repo is a monorepo used for code references; **codex**, **mistral-vibe-main**, and **nanobot-main** are reference-only and **not part of the published codebase**.
2. **Rebrand the repo** as **radioshaq** (name and any public-facing copy).
3. **Rename the Python package** from **shakods** to **radioshaq** (package and import namespace; PEP 8 uses lowercase `radioshaq`; "RadioShaq" is the display/brand name).
4. **Add a top-level README** at the repo root, based on the main app README, that presents the repo as "radioshaq" and points to the published pieces (main app, remote_receiver).

---

## 2. Current state (from exploration)

### 2.1 Repo root layout

| Path                 | Purpose                                                                 | Published? |
|----------------------|-------------------------------------------------------------------------|------------|
| `shakods/`           | Main app: SHAKODS (API, orchestrator, web UI, radio, audio)             | **Yes**    |
| `remote_receiver/`   | Remote SDR receiver for SHAKODS (RTL-SDR, HackRF, JWT, HQ upload)       | **Yes**    |
| `docs/`              | Implementation plans, hardware notes, etc.                              | Ignored*   |
| `codex/`             | Reference code (in `.gitignore`)                                        | **No**     |
| `mistral-vibe-main/` | Reference code (in `.gitignore`)                                       | **No**     |
| `nanobot-main/`      | Reference code (in `.gitignore`)                                       | **No**     |
| `.gitignore`         | Excludes `codex/`, `mistral-vibe-main/`, `nanobot-main/`, `docs/`       | —          |

\* `docs/` is in `.gitignore`; if you want it published, it must be removed from `.gitignore` (optional, not part of this plan).

### 2.2 Reference folders vs "published" code

- **codex**, **mistral-vibe-main**, **nanobot-main** are **not** in the published codebase: they are listed in `.gitignore` and are for local reference only.
- **shakods** contains **vendored** code under `shakods/shakods/vendor/nanobot/` (message bus, tool registry). That vendored code **is** part of the published shakods package; the **nanobot-main** repo itself is not.
- **Mistral** in the codebase = Mistral AI (LLM provider / API), not the `mistral-vibe-main` folder. No change needed for that.

### 2.3 Existing READMEs

- **shakods/README.md** — Full SHAKODS doc: install (uv, setup.ps1), quick start (Postgres, migrations, API), auth (JWT), demo, development (pytest, mypy, ruff). Links to `docs/install.md`, `docs/database.md`, `docs/auth.md`, `../docs/HARDWARE_CONNECTION.md`.
- **remote_receiver/README.md** — Short: setup (uv, SDR/HackRF extras), env vars, run (uvicorn).
- **No README at repo root** — So new visitors don't see repo name or what's published.

### 2.4 Naming and branding

- **pyproject.toml** in shakods: `name = "shakods"` — will become `name = "radioshaq"`.
- **Package directory** `shakods/shakods/` — will become `shakods/radioshaq/` (Option A) or `radioshaq/radioshaq/` (Option B).
- **Display name** "RadioShaq" (PascalCase) for docs/UI; **import name** `radioshaq` (lowercase, PEP 8) for the Python package.

---

## 3. Implementation plan

### 3.1 Add a top-level README (based on main app)

**File:** `README.md` at repo root (e.g. `c:\Users\MeMyself\monorepo\README.md`).

**Content outline:**

1. **Title and one-liner**  
   - Repo name: **radioshaq**.  
   - One line: e.g. "Monorepo for RadioShaq: ham radio AI orchestration and remote reception."

2. **What this repo is**  
   - Short paragraph: this is a monorepo; the **published** codebases are the **main app** (RadioShaq/SHAKODS) and **remote_receiver** (remote SDR station).  
   - Explicit note: **codex**, **mistral-vibe-main**, and **nanobot-main** are **reference-only** and not part of the published codebase (they may be present locally but are gitignored).

3. **Quick links**  
   - Link to main app directory (e.g. `[radioshaq/](radioshaq/)` if Option B, or `[shakods/](shakods/)` if Option A) with one sentence (e.g. "RadioShaq — AI-powered ham radio orchestrator").  
   - Link to **remote_receiver**: `[remote_receiver/](remote_receiver/)` with one sentence (e.g. "Remote SDR receiver for RadioShaq").

4. **Quick start (from main app directory)**  
   - Postgres (Docker 5434), migrations, start API (`uv run python -m radioshaq.api.server`), link to API docs.  
   - All commands run from the project directory (e.g. "From the `radioshaq/` directory" or "From the `shakods/` directory" per layout option).

5. **Install**  
   - Prerequisites (Python 3.11+, uv), `uv sync --extra dev --extra test`, optional `.\infrastructure\local\setup.ps1`.  
   - Link to main app README for full install guide.

6. **License**  
   - MIT. Optionally add a root `LICENSE` file.

7. **Optional**  
   - Badges (Python 3.11+, License: MIT).  
   - Short "Development" subsection: run tests (pytest, mypy, ruff) and point to main app README for details.

**Do not:**  
- Duplicate all of the main app (auth, demo, every doc link). Keep the root README short and point into the main app directory for full docs.

### 3.2 Rebrand to "radioshaq" (repo and docs)

- **Repository name**  
  - On GitHub/GitLab etc.: rename the repo to **radioshaq** (or **radio-shaq** if you prefer kebab-case). Do this in the host's UI.

- **Top-level README**  
  - Use "RadioShaq" as the project/repo name in the title and intro. After the package rename, quick start will reference `radioshaq` (e.g. `uv run python -m radioshaq.api.server`).

### 3.3 Clarify "reference-only" in the repo

- **In the new top-level README**  
  - One clear sentence: "The folders `codex/`, `mistral-vibe-main/`, and `nanobot-main/` are for local reference only and are not part of the published codebase (they are in `.gitignore`)."

- **.gitignore**  
  - Already lists `codex/`, `mistral-vibe-main/`, `nanobot-main/` — no change required. Optionally add a short comment above them, e.g. `# Reference-only (not published)`.

- **No code changes** required for "mistral" or "nanobot" semantics:  
  - Mistral = LLM provider in code.  
  - nanobot = vendored code inside the main app; the **nanobot-main** repo is the reference, not published from this repo.

### 3.4 Rename Python package from shakods to radioshaq

**Convention:** Use **radioshaq** (all lowercase) for the Python package and import name (PEP 8). Use **RadioShaq** for display/brand in READMEs and UI.

**Two layout options:**

- **Option A (minimal path churn):** Keep the project directory name as `shakods/`. Rename only the inner package directory: `shakods/shakods/` → `shakods/radioshaq/`. All imports become `radioshaq.*`. Entrypoints and docs then refer to the `radioshaq` package; the folder containing it remains `shakods/`.
- **Option B (full consistency):** Rename project directory `shakods/` → `radioshaq/` and inner package `shakods/shakods/` → `radioshaq/radioshaq/`. Result: one top-level `radioshaq/` with `pyproject.toml` and package `radioshaq/radioshaq/`. All internal and external links (README, CI, remote_receiver docs) that pointed at `shakods/` must be updated to `radioshaq/`.

The following checklist applies to either option; paths use `shakods/` for Option A and `radioshaq/` for Option B where the project root is meant.

#### 3.4.1 Directory and build config

| Action | Location |
|--------|----------|
| Rename package directory | `shakods/shakods/` → `shakods/radioshaq/` (Option A) or `radioshaq/radioshaq/` (Option B) |
| Update `[project]` name | `pyproject.toml`: `name = "radioshaq"` |
| Update `[project.scripts]` | `pyproject.toml`: `shakods = "shakods.cli:app"` → `radioshaq = "radioshaq.cli:app"` (and same for `alembic-*` entries: `radioshaq.scripts.alembic_runner`) |
| Update `[project.urls]` | Replace `shakods` with `radioshaq` in Homepage, Documentation, Repository, Issues (e.g. `https://github.com/radioshaq/radioshaq`) |
| Update Hatch config | `[tool.hatch.build.targets.wheel]` `packages = ["radioshaq"]`; `[tool.hatch.build]` `include` → `"radioshaq/**/*.py"` |
| Update coverage source | `[tool.coverage.run]` `source = ["radioshaq"]` |
| Rename tool section | `[tool.shakods]` → `[tool.radioshaq]` (and all nested `[tool.shakods.*]` → `[tool.radioshaq.*]`) |

#### 3.4.2 Python imports and entrypoints

Replace every occurrence of the **import package name** `shakods` with `radioshaq` in:

- All `.py` files under the (renamed) package: `from shakods.` → `from radioshaq.`, `import shakods` → `import radioshaq`.
- **Vendor subpackage:** `shakods.vendor` → `radioshaq.vendor` (so `radioshaq.vendor.nanobot.*`, `radioshaq.vendor.vibe.*`).
- **Tests:** `tests/conftest.py`, `tests/unit/**/*.py`, `tests/integration/**/*.py` — all `shakods` imports → `radioshaq`.
- **Alembic:** `infrastructure/local/alembic/env.py` — `from shakods.database.models` → `from radioshaq.database.models`.
- **Lambda/infra:** `infrastructure/aws/lambda/api_handler.py` and any other AWS scripts that `import shakods` → `radioshaq`.
- **Scripts:** `scripts/demo/inject_audio.py` and any script that imports the package → `radioshaq`.

**Module run entrypoints** (change in configs and docs, not in Python):

- `python -m shakods.api.server` → `python -m radioshaq.api.server`
- `python -m shakods.orchestrator.worker` → `python -m radioshaq.orchestrator.worker`
- `python -m shakods.radio.worker` → `python -m radioshaq.radio.worker`
- `python -m shakods.modes.field_sync` → `python -m radioshaq.modes.field_sync`
- `python -m shakods.mq.worker` → `python -m radioshaq.mq.worker` (if present)

#### 3.4.3 Config files and defaults

- **Default DB/user names:** In `config/schema.py`, `examples/config_sample.yaml`, `docker-compose.yml`, `ecosystem.config.js`, `setup.ps1`, and `conftest.py`, the default Postgres user/db name is currently `shakods`. You can leave as-is for local dev or change to `radioshaq` for full consistency (optional).
- **Default paths:** `workspace_dir` / `data_dir` defaults `~/.shakods` → optionally `~/.radioshaq` in `config/schema.py` and `setup.ps1`.
- **Default trigger_phrases:** Config default `["shakods", "field station"]` can stay or become `["radioshaq", "field station"]` — optional.
- **hq_base_url** default → optionally `https://hq.radioshaq.example.com`.

#### 3.4.4 PM2 / ecosystem and Docker

- **ecosystem.config.js** (root and `infrastructure/local/`): app names (e.g. `shakods-api`) → `radioshaq-api`; script/args `-m shakods.api.server` → `-m radioshaq.api.server`; `watch` paths `shakods/api` → `radioshaq/api`; deployment paths/repo if desired.
- **docker-compose.yml:** Service/container names and Postgres user/DB — change to `radioshaq` for consistency or leave `shakods` for local dev.

#### 3.4.5 Web interface (frontend)

- **package.json:** `"name": "shakods-web-interface"` → `"name": "radioshaq-web-interface"`.
- **API client:** Rename `src/services/shakodsApi.ts` → `radioshaqApi.ts`; update imports in AudioConfigPage, VADVisualizer, ConfirmationQueue, and any other consumers to use `radioshaqApi` / `RadioshaqApi`.

#### 3.4.6 AWS / infrastructure

- **CloudFormation, IAM, deploy scripts:** Resource names/prefixes `shakods-${Environment}-*` → `radioshaq-${Environment}-*` in base.yaml, policies.json, deploy.sh, teardown.sh.
- **Lambda:** `"service": "shakods-api"` → `"radioshaq-api"` if desired.

#### 3.4.7 Docs and READMEs

- **Main app README:** Commands `python -m shakods.*` → `python -m radioshaq.*`; `mypy shakods` → `mypy radioshaq`.
- **examples/README.md, scripts/demo/README.md:** Package references → `radioshaq`.
- **Top-level README:** Use `radioshaq` in quick start; project folder link per Option A or B.
- **remote_receiver/README.md:** "SHAKODS" can stay or become "RadioShaq" (no Python changes).

#### 3.4.8 Shell and PowerShell scripts

- **setup.ps1, install.ps1:** "From shakods directory" → "From project/radioshaq directory"; `python -m shakods.api.server` → `radioshaq.api.server`; `.shakods` → `.radioshaq` if changing defaults.
- **run_e2e_no_radio.sh / .ps1:** `shakods-api` → `radioshaq-api`; module args → `radioshaq.api.server`.
- **run_integration_tests_with_pm2.sh:** Any `shakods` refs → `radioshaq`.

#### 3.4.9 Order of operations (recommended)

1. Rename package directory and update `pyproject.toml` (Hatch, coverage, tool section).
2. Global replace in `.py` files: import/package name `shakods` → `radioshaq` (avoid replacing string literals that should stay, e.g. DB name).
3. Update entrypoints in .js, .yml, .sh, .ps1, .md.
4. Update frontend: package.json name, shakodsApi → radioshaqApi (file and imports).
5. Update ecosystem configs, Docker, AWS resource names.
6. Run tests and smoke-check API with `uv run python -m radioshaq.api.server`.
7. Update all READMEs and top-level README.

---

## 4. File-level checklist

| Step | Action | File / place |
|------|--------|---------------|
| 1 | Rename Python package dir and update pyproject / Hatch / coverage / tool section | See §3.4.1 |
| 2 | Replace shakods → radioshaq in all Python imports and entrypoints | See §3.4.2 |
| 3 | Update config defaults, PM2, Docker, AWS, frontend, scripts, docs | See §3.4.3–3.4.8 |
| 4 | Create top-level README | `README.md` (repo root) |
| 5 | Optional: add comment in .gitignore | `.gitignore` (above codex/mistral-vibe-main/nanobot-main) |
| 6 | Rename repo to "radioshaq" | GitHub/GitLab (or other host) — manual |

---

## 5. Suggested top-level README structure (snippet)

```markdown
# RadioShaq

Monorepo for RadioShaq: ham radio AI orchestration and remote SDR reception.

**Published code in this repo:**

- **[radioshaq/](radioshaq/)** (or **[shakods/](shakods/)** if Option A) — RadioShaq (SHAKODS): AI-powered orchestrator for ham radio, emergency comms, and field–HQ coordination.
- **[remote_receiver/](remote_receiver/)** — Remote SDR receiver station (RTL-SDR / HackRF) with JWT auth and HQ upload.

The directories `codex/`, `mistral-vibe-main/`, and `nanobot-main/` are **reference-only** and are not part of the published codebase; they are listed in `.gitignore`.

## Quick start (main app)

From the project directory (e.g. `radioshaq/` or `shakods/`):

  # 1. Install
  uv sync --extra dev --extra test

  # 2. Start Postgres (Docker, port 5434)
  cd infrastructure/local && docker compose up -d postgres && cd ../..

  # 3. Migrations
  uv run alembic -c infrastructure/local/alembic.ini upgrade head

  # 4. Start API
  uv run python -m radioshaq.api.server
  # API: http://localhost:8000/docs

Full install and usage: see the main app **README.md** in that directory.

## License

MIT
```

---

## 6. Out of scope (for this plan)

- Changing `docs/` in `.gitignore` or publishing `docs/`.  
- Modifying vendored nanobot code or Mistral API usage.  
- Creating or moving a root `LICENSE` file (optional; can be done separately).

---

*Plan version: 1.1. Scope extended to include renaming the Python package to radioshaq.*
