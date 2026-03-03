# Documentation Site Plan — MkDocs Material, GitHub CI/CD, Engagement-Optimized

This plan defines a **complete documentation site** for the repository using **MkDocs Material** theme with a **tabular (tabbed) navigation interface**. Builds run **only on manual trigger** (workflow_dispatch); **tests must pass first**, then the docs are built. Content is organized into: **About** (autonomous agent), **Quick Start**, **Radio Usage**, **Configuration**, and **API Reference**, with legacy `docs/docs/` used for inspiration.

**Technical documentation policy:** Use **code anchors only** — no free-standing code blocks for source code. All code shown in the docs must be **included from repo files** via the Snippets extension and rendered with **line-number anchors** so every line is linkable. See §5 for plugins and detailed examples. **Mandatory features:** GitHub Pages deploy, API reference from OpenAPI, and search/instant loading — see §10.

---

## 1. Requirements Summary

| Requirement | Interpretation |
|-------------|----------------|
| **Complete documentation site** | Single MkDocs Material site at repo root, all key topics covered. |
| **Optimized for engagement** | Clear nav tabs, quick start above the fold, code copy/select, search and instant loading. |
| **Code anchors only, never code blocks** | Source code is included via Snippets from repo files; all code has line-number anchors (linkable). No pasted code blocks for real source. |
| **GitHub CI/CD** | GitHub Actions workflow for building and **publishing** the site (mandatory). |
| **GitHub Pages deploy (mandatory)** | Every successful docs build is deployed to GitHub Pages via `actions/upload-pages-artifact` and `actions/deploy-pages`; `site_url` must match the Pages URL. |
| **API reference from OpenAPI (mandatory)** | API Reference is **generated** from the FastAPI OpenAPI spec (export at build time, MkDocs plugin to render); not hand-written only. |
| **Search and instant loading (mandatory)** | `site_url` is set (required for instant loading and sitemap); `navigation.instant` enabled; search plugin active so search index survives navigation. |
| **Tests pass first, then docs** | Workflow runs tests (radioshaq + optional remote_receiver); only on success does it build docs. |
| **Never on push or PR** | No `push:` or `pull_request:` triggers for the docs workflow. |
| **Always capable manually** | Workflow is triggered only via `workflow_dispatch` (manual or API). |
| **MkDocs Material + tabular interface** | Theme: Material; top-level nav as **tabs** (`navigation.tabs`). |
| **Update time displayed** | Each page shows last updated date (git revision or build date) via plugin. |
| **Displays correctly on mobile** | Responsive layout; navigation.path (breadcrumbs) for small screens; site_url set for instant loading; no custom CSS that breaks viewport. |
| **Front page: About** | Describes the autonomous agent (RadioShaq, REACT orchestrator, capabilities). |
| **Quick Start** | Minimal steps to run the app (Postgres, migrations, API, auth). |
| **Radio Usage** | Connecting rigs, CAT/Hamlib, remote receiver, audio TX, band/compliance. |
| **Configuration** | Env vars, YAML/config schema, key options (DB, LLM, radio, audio). |
| **API Reference** | Documented endpoints (auth, messages, callsigns, audio, radio, transcripts, etc.). |
| **Legacy docs** | Use `docs/docs/` content for inspiration; migrate/copy into new structure, do not rely on old paths in nav. |

---

## 2. Current State

| Item | Current state |
|------|----------------|
| **MkDocs** | Not present; no `mkdocs.yml` in repo. |
| **GitHub Actions** | No `.github/workflows/` workflows. |
| **docs/** | In `.gitignore`; contains `docs/docs/` with legacy MD files (MIGRATION, HARDWARE_CONNECTION, AUDIO_TX_PLAN, PER_MESSAGE_ACTIVATION_PLAN, SHAKODS_MATERIALS_FRANCE, REPORT-interface-dashboard-and-client, etc.). |
| **Tests** | `radioshaq`: `uv run pytest tests/unit tests/integration -v` (from `radioshaq/`). |
| **API** | FastAPI app in `radioshaq/radioshaq/api/server.py`; routes under `/health`, `/auth`, `/messages`, `/callsigns`, `/api/v1`, `/transcripts`, `/radio`, `/inject`, `/internal`. |

To have the documentation site **versioned and built from the repo**, `docs/` (or the chosen MkDocs source directory) must be **tracked**. Options: (A) Remove `docs/` from `.gitignore` and use `docs/` as MkDocs source; (B) Use a different directory (e.g. `documentation/`) for the site and keep `docs/` ignored. This plan assumes **(A)** with a clean structure under `docs/` so the new site lives where users expect.

---

## 3. Architecture

### 3.1 Site structure (nav = tabs)

```
nav (tabs):
  About          → index.md (front page: agent description)
  Quick Start    → quick-start.md
  Radio Usage    → radio-usage.md
  Configuration  → configuration.md
  API Reference  → api-reference/ (or single api-reference.md)
```

### 3.2 MkDocs layout

- **Config:** `mkdocs.yml` at **repository root** (monorepo root).
- **Docs source:** `docs/` at repo root.
  - `docs/index.md` — About / autonomous agent.
  - `docs/quick-start.md` — Quick start.
  - `docs/radio-usage.md` — Radio usage (rigs, remote receiver, audio TX).
  - `docs/configuration.md` — Configuration reference.
  - `docs/api-reference.md` — API overview + per-route sections (or `docs/api-reference/` with one page per router).
- **Legacy:** Either move `docs/docs/` to `docs/legacy/` and link from a single "Legacy docs" page, or copy needed content into the new pages and leave legacy files in `docs/legacy/` for reference only.

### 3.3 CI/CD flow

- **Trigger:** `workflow_dispatch` only (manual run from Actions tab).
- **Job 1 — Tests:** Checkout → install (uv) → run tests in `radioshaq/` (and optionally `remote_receiver/`). On failure, workflow fails; no docs build.
- **Job 2 — Build docs:** Depends on Job 1 success; checkout → install MkDocs + Material + plugins → (optional: export OpenAPI from FastAPI) → `mkdocs build`. Output: `site/`.
- **Job 3 — Deploy to GitHub Pages (mandatory):** Depends on Job 2 success; use `actions/upload-pages-artifact` with `path: site/`; then `actions/deploy-pages`. Repository must have GitHub Pages source set to “GitHub Actions”. Site is live at `https://<owner>.github.io/<repo>/`.

---

## 4. Projects and Activities

### Project 1: MkDocs Material setup and tabular nav

**Objective:** Add MkDocs with Material theme and tabbed top-level navigation; no content yet beyond placeholders.

#### Activity 1.1 — Create `mkdocs.yml` at repo root

| File-level task | Line-level subtasks |
|-----------------|----------------------|
| Create `mkdocs.yml` at monorepo root. | (1) Set `site_name: "RadioShaq"`, `site_description`, and **`site_url`** (required; use `https://<owner>.github.io/<repo>/` for GitHub Pages so instant loading and sitemap work). (2) Set `docs_dir: docs`, `site_dir: site`. (3) `theme: name: material`, `language: en`; `features`: `navigation.tabs`, `navigation.tabs.sticky`, `navigation.path`, **`navigation.instant`** (mandatory), optionally `navigation.instant.prefetch`, `navigation.instant.progress`; `content.tabs.link`, `content.code.copy`, `content.code.select`, `content.code.annotate`, `toc.follow`. (4) `markdown_extensions`: (as in §5.3). (5) `plugins`: **`search`** (mandatory); `git-revision-date-localized`; add OpenAPI plugin when implementing API from OpenAPI. (6) `nav`: About, Quick Start, Radio Usage, Configuration, API Reference (latter points to OpenAPI-generated or overview + generated content). |

#### Activity 1.2 — Python / dependency for MkDocs

| File-level task | Line-level subtasks |
|-----------------|----------------------|
| Make MkDocs, Material, and docs plugins installable from repo. | (1) Create `docs/requirements.txt` at repo root with `mkdocs-material>=9.5`, `mkdocs-git-revision-date-localized-plugin`, `pymdown-extensions`, and **neoteroi-mkdocs** (or chosen OpenAPI plugin for API reference); optionally `mkdocstrings[python]`. (2) Or add a `docs` optional group in pyproject with the same deps. (3) Ensure CI installs these before the OpenAPI export and `mkdocs build` steps. |

#### Activity 1.3 — Docs directory and placeholder pages

| File-level task | Line-level subtasks |
|-----------------|----------------------|
| Create `docs/` and placeholder Markdown files. | (1) Create `docs/index.md` with title "About" and placeholder: "RadioShaq is an autonomous agent…". (2) Create `docs/quick-start.md` with title "Quick Start" and placeholder. (3) Create `docs/radio-usage.md` with title "Radio Usage" and placeholder. (4) Create `docs/configuration.md` with title "Configuration" and placeholder. (5) Create `docs/api-reference.md` with title "API Reference" and placeholder (or create `docs/api-reference/` and `docs/api-reference/index.md`). (6) Ensure `mkdocs build` runs without errors. |

---

### Project 2: Content — About (front page)

**Objective:** Front page describes the autonomous agent and system for engagement.

#### Activity 2.1 — Write About / index.md

| File-level task | Line-level subtasks |
|-----------------|----------------------|
| `docs/index.md`: About RadioShaq and the autonomous agent. | (1) Open with a short tagline (e.g. Strategic Ham Radio Autonomous Query and Kontrol System). (2) One paragraph: what RadioShaq is (AI-powered orchestrator for ham radio, field-to-HQ, emergency comms). (3) Subsection "What the agent does": REACT loop (Reasoning, Evaluation, Acting, Communicating, Tracking); planning and decomposition; tools (e.g. send audio, register callsign) and specialized agents (radio TX/RX, SMS, WhatsApp, GIS, whitelist, propagation, scheduler). (4) Subsection "Where it runs": main app (API + orchestrator), optional remote receiver (SDR). (5) Optional: bullet list of capabilities (voice/digital/packet TX, callsign whitelist, transcripts, relay). (6) Reuse/adapt content from `radioshaq/README.md`, `docs/docs/RADIOSHAQ_REBRAND_AND_README_PLAN.md`, and orchestrator description from `docs/docs/PLAN-orchestrator-unified-react.md` (high level only). |

---

### Project 3: Content — Quick Start

**Objective:** Minimal path to run the app; engagement-friendly (copy-paste commands).

#### Activity 3.1 — Write Quick Start page

| File-level task | Line-level subtasks |
|-----------------|----------------------|
| `docs/quick-start.md`: Prerequisites and steps to run API. | (1) Prerequisites: Python 3.11+, uv; optional Docker (Postgres), Node (PM2). (2) Step 1: Clone/navigate to repo and `cd radioshaq`. (3) Step 2: Install — `uv sync --extra dev --extra test` (or link to full install guide). (4) Step 3: Start Postgres (Docker on 5434) — one-liner from `radioshaq/README.md` or `docs/docs/MIGRATION.md`. (5) Step 4: Run migrations — `python infrastructure/local/run_alembic.py upgrade head` (or `uv run alembic upgrade head` with correct env). (6) Step 5: Start API — `uv run python -m radioshaq.api.server`; note URL `http://localhost:8000/docs`. (7) Step 6: Get a JWT — example `curl` and PowerShell for `POST /auth/token`; show using token in `Authorization` header. (8) Use Material content tabs for "PowerShell" vs "Bash" where useful. (9) Link to Configuration for env vars (DATABASE_URL, etc.) and to Radio Usage for hardware. |

---

### Project 4: Content — Radio Usage

**Objective:** How to connect and use radios (CAT rigs, remote receiver, audio TX).

#### Activity 4.1 — Write Radio Usage page

| File-level task | Line-level subtasks |
|-----------------|----------------------|
| `docs/radio-usage.md`: Hardware connection and radio usage. | (1) Overview table: deployment (station principale, portable, remote receiver), what runs where, hardware connection. (2) Section "Station principale (e.g. IC-7300)": hardware (USB CAT), Hamlib/rigctld, config snippet (`radio.enabled`, `rig_model`, `port`); Windows vs Linux port. (3) Section "Portable (FT-450D / FT-817)": SCU-17, config for Yaesu. (4) Section "Remote receiver (RTL-SDR on Pi)": hardware, env vars (JWT_SECRET, STATION_ID, HQ_URL, RTLSDR_INDEX), run command. (5) Section "Audio out to rig (voice TX)": cabling, `radio.audio_output_device`, `radio.voice_use_tts`; link to AUDIO_TX_PLAN if needed. (6) Section "HackRF (optional)": sdr_tx_enabled, compliance (band allowlist, audit log); brief pointer to HACKRF plan. (7) Quick reference table: goal vs config/env. (8) Adapt from `docs/docs/HARDWARE_CONNECTION.md` and `docs/docs/AUDIO_TX_PLAN.md`; use content tabs for YAML vs env where useful. |

---

### Project 5: Content — Configuration

**Objective:** Single place for config reference (env, schema, main sections).

#### Activity 5.1 — Write Configuration page

| File-level task | Line-level subtasks |
|-----------------|----------------------|
| `docs/configuration.md`: Config and environment reference. | (1) Intro: config via `Config` (Pydantic), env vars, optional YAML; link to `radioshaq/radioshaq/config/schema.py`. (2) Section "Environment variables": table of key vars (POSTGRES_*, DATABASE_URL, JWT_SECRET, RADIOSHAQ_*, LLM/API keys); copy from `radioshaq/.env.example` and extend. (3) Section "Database": postgres_url, pool, Alembic; link to MIGRATION/database for migrations. (4) Section "JWT / Auth": secret_key, expire times, field_token_expire_hours, require_station_id. (5) Section "LLM": provider, model, *\_api_key, temperature, max_tokens. (6) Section "Radio": enabled, rig_model, port, use_daemon, fldigi_*, packet_*, audio_output_device, voice_use_tts, sdr_tx_*, compliance options. (7) Section "Audio (voice_rx)": input_device, sample_rate, VAD, ASR, response_mode, trigger_phrases, activation. (8) Optional: subsections for HQ, Twilio, etc. if relevant. (9) Use tables and code blocks; optional mkdocstrings inclusion for `Config` and nested models if desired. |

---

### Project 6: Content — API Reference

**Objective:** Document all public API endpoints for discovery and integration.

#### Activity 6.1 — API reference structure

| File-level task | Line-level subtasks |
|-----------------|----------------------|
| `docs/api-reference.md` (or `docs/api-reference/index.md`): Overview and list of route groups. | (1) Intro: FastAPI app, base URL, auth (Bearer JWT from `POST /auth/token`). (2) Table or list: Health, Auth, Messages, Callsigns, Audio (config + pending + devices), Transcripts, Radio, Inject, Internal (bus). (3) Each row links to an anchor or subpage (e.g. `#health`, `#auth`, `#messages`). (4) Note OpenAPI at `/docs` and `/redoc`. |

#### Activity 6.2 — Per-route API documentation

| File-level task | Line-level subtasks |
|-----------------|----------------------|
| One section per router (or one page per router under `api-reference/`). | (1) **Health:** `GET /health`, `GET /health/ready` — purpose, response. (2) **Auth:** `POST /auth/token`, `POST /auth/refresh`, `GET /auth/me` — query/body params, response shape. (3) **Messages:** `POST /messages/process`, `POST /messages/whitelist-request`, `POST /messages/from-audio`, `POST /messages/inject-and-store`; **Relay:** `POST /messages/relay` — request body, response. (4) **Callsigns:** `GET /callsigns`, `POST /callsigns/register`, `POST /callsigns/register-from-audio`, `DELETE /callsigns/registered/{callsign}`. (5) **Audio:** `GET/PATCH /api/v1/config/audio`, `POST /api/v1/config/audio/reset`, `GET /api/v1/audio/devices`, `POST /api/v1/audio/devices/{id}/test`, `GET /api/v1/audio/pending`, `POST .../approve`, `POST .../reject`. (6) **Transcripts:** `GET /transcripts`, `GET /transcripts/{id}`, `POST /transcripts/{id}/play`. (7) **Radio:** `GET /radio/propagation`, `GET /radio/bands`, `POST /radio/send-tts`. (8) **Inject:** `POST /inject/message`. (9) **Internal:** `POST /internal/bus/inbound`. (10) For each endpoint: method + path, short description, request (body/query), response (key fields); optional code block example. (11) Source: `radioshaq/radioshaq/api/routes/*.py` and `docs/docs/REPORT-interface-dashboard-and-client.md`. |

#### Activity 6.3 — API reference from OpenAPI (mandatory)

| File-level task | Line-level subtasks |
|-----------------|----------------------|
| Generate API Reference from FastAPI OpenAPI spec. | (1) **Export OpenAPI at build time:** Add a script (e.g. `radioshaq/scripts/export_openapi.py` or a step in the build-docs job) that imports the FastAPI app and writes `app.openapi()` to a JSON file (e.g. `docs/api/openapi.json`). Run this before `mkdocs build` so the spec is available. (2) **Add MkDocs OpenAPI plugin:** Install and configure a plugin that turns OpenAPI into docs: e.g. **neoteroi-mkdocs** (syntax `[OAD(path_or_url)]` in a markdown page), or **mkdocs-openapi-markdown** / similar. In `mkdocs.yml`, add the plugin and point it at the exported spec. (3) **API Reference page:** Create `docs/api-reference.md` (or `docs/api-reference/index.md`) that embeds the generated API docs (e.g. `[OAD(api/openapi.json)]` or plugin’s equivalent). Optionally add a short intro (auth, base URL) above the generated block. (4) **Nav:** Ensure “API Reference” in `nav` points to this page. (5) **CI:** In the build-docs job, run the export step (from repo root: `cd radioshaq && uv run python scripts/export_openapi.py` or inline Python) then `mkdocs build`. |

#### Activity 6.4 — Optional: mkdocstrings for Python modules

| File-level task | Line-level subtasks |
|-----------------|----------------------|
| Optionally add Python API (modules) alongside OpenAPI. | (1) Add plugin `mkdocstrings` with handler `python`; add a page that uses `::: radioshaq.api.routes.messages` etc. for module-level reference. (2) Link from API Reference overview to this page if used. |

---

### Project 7: GitHub Actions — Tests, build, and deploy (manual only)

**Objective:** One workflow: manual trigger only; run tests → build docs → **deploy to GitHub Pages** (all mandatory); never on push/PR.

#### Activity 7.1 — Create workflow file

| File-level task | Line-level subtasks |
|-----------------|----------------------|
| Create `.github/workflows/build-docs.yml`. | (1) Name: e.g. "Build and deploy documentation". (2) `on: workflow_dispatch:` only (no `push` or `pull_request`). (3) **Permissions** (at workflow or deploy job level): `contents: read`, `pages: write`, `id-token: write`. (4) Job `test`: runs on ubuntu-latest; checkout; set up Python (e.g. 3.11); install uv; run tests in `radioshaq/` — `cd radioshaq && uv sync --extra dev --extra test && uv run pytest tests/unit tests/integration -v`. (5) Job `build-docs`: `needs: test`; checkout; install MkDocs, Material, and plugins (including OpenAPI plugin and git-revision-date-localized); **export OpenAPI** (run script or inline Python that writes FastAPI `app.openapi()` to `docs/api/openapi.json`); run `mkdocs build` from repo root; **upload artifact** with `actions/upload-pages-artifact@v4` (or v3), `path: site/` (MkDocs default `site_dir`). (6) Job **`deploy` (mandatory):** `needs: build-docs`; `runs-on: ubuntu-latest`; `environment: github-pages`; `permissions: pages: write, id-token: write`; single step: `uses: actions/deploy-pages@v4` (or v3). This deploys the artifact produced by the build job to GitHub Pages. (7) **Repository setting:** In repo Settings → Pages, set “Source” to **GitHub Actions**. (8) Ensure build runs from repo root so `mkdocs.yml` and `docs/` resolve. |

#### Activity 7.2 — Paths and working directory

| File-level task | Line-level subtasks |
|-----------------|----------------------|
| Ensure workflow runs from repo root and radioshaq tests see correct cwd. | (1) Default working directory for jobs is repo root. (2) In `test` job, run `cd radioshaq && uv run pytest ...` so `radioshaq` is the project root for pytest. (3) In `build-docs` job, run OpenAPI export then `mkdocs build` without `cd` so `mkdocs.yml` at root is used. (4) `upload-pages-artifact` must receive the directory that MkDocs writes to: use `path: site/` (match `site_dir` in `mkdocs.yml`). |

#### Activity 7.3 — GitHub Pages deploy (mandatory): detailed steps

| File-level task | Line-level subtasks |
|-----------------|----------------------|
| Implement deploy job so every successful build is published. | (1) In the **build-docs** job, after `mkdocs build`, add a step: `uses: actions/upload-pages-artifact@v4` with `path: site/` (default artifact name is `github-pages`). (2) Add a **deploy** job: `needs: build-docs`; `runs-on: ubuntu-latest`; `environment: github-pages` (create this environment in repo Settings → Environments if needed); `permissions: { pages: write, id-token: write }`; one step: `uses: actions/deploy-pages@v4`. (3) At workflow top level set `permissions: contents: read` so other jobs can read the repo. (4) **Repo configuration:** Settings → Pages → Build and deployment → Source: **GitHub Actions**. (5) After the first successful run, the site is available at `https://<owner>.github.io/<repo>/`; set this exact URL as `site_url` in `mkdocs.yml` so instant loading and sitemap work. |

---

### Project 8: Legacy docs and .gitignore

**Objective:** Use legacy content for inspiration; decide whether to track `docs/` and where legacy lives.

#### Activity 8.1 — Un-ignore docs and legacy layout

| File-level task | Line-level subtasks |
|-----------------|----------------------|
| Allow documentation to be versioned. | (1) Remove `docs/` from `.gitignore` at repo root so the new `docs/` (index, quick-start, etc.) is committed. (2) Move or copy existing `docs/docs/*` into `docs/legacy/` (or keep `docs/docs/` and add a nav entry "Legacy" → `docs/legacy/index.md` that lists links to legacy files). (3) In `mkdocs.yml` nav, do not add every legacy file; add at most one "Legacy" page that links to them for reference. (4) Update any in-repo links that pointed to `docs/docs/...` to point to the new canonical pages (about, quick-start, radio-usage, configuration, api-reference) where applicable. |

#### Activity 8.2 — Canonical links from radioshaq README

| File-level task | Line-level subtasks |
|-----------------|----------------------|
| Point radioshaq README to the new doc site. | (1) In `radioshaq/README.md`, replace links like `docs/database.md`, `../docs/HARDWARE_CONNECTION.md` with links to the built site (e.g. `https://<org>.github.io/<repo>/` or relative paths to `docs/quick-start.md`, `docs/radio-usage.md`). (2) Or keep relative paths to Markdown in repo (e.g. `../docs/quick-start.md`) for GitHub repo browsing; document that the published site is at GitHub Pages (or other URL). |

---

## 5. Technical documentation: code anchors and plugins

### 5.1 Policy: code anchors only, no free-standing code blocks

- **Rule:** Do not paste source code as raw Markdown fenced code blocks. All code that comes from the repository must be **included via the Snippets extension** (`--8<--`) from real files, so the doc stays in sync with the codebase and every line is **anchorable** (clickable line numbers).
- **Exception:** One-line shell commands or env var examples that are not stored in a repo file may use a single short code block if needed; prefer snippet-included scripts (e.g. `scripts/install.ps1` excerpt) where possible.
- **Result:** Readers get shareable links to specific lines (e.g. `page.md#L42`), and the docs avoid drift from the actual source.

### 5.2 MkDocs Material version and recent updates

- **Pin version:** Use `mkdocs-material>=9.5,<10` (or `>=9.7` for latest features) in `docs/requirements.txt` or optional deps so CI and local builds are reproducible.
- **Changelog:** [Material for MkDocs changelog](https://squidfunk.github.io/mkdocs-material/changelog/).
- **Relevant recent features (9.5–9.7):**
  - **9.7:** `content.code.select` — button to select line ranges in code blocks (ideal for linking to subsections); `navigation.instant.prefetch` — prefetch on link hover; `navigation.path` — breadcrumbs above title (helps mobile); instant previews for header links.
  - **9.5:** Content tabs get anchor links (right-click tab to copy link); tab slugify for readable anchors.
  - **Insiders features now free** (as of 9.7.0): instant previews, projects plugin, social plugin, etc., available without Insiders subscription.
- **Mobile:** Theme is responsive by default (“Works on all devices”). Set `site_url` for instant loading; enable `navigation.path` so small screens get breadcrumbs; avoid extra CSS that overrides viewport or breaks touch targets; test on a narrow viewport (e.g. Chrome DevTools device mode).

### 5.3 Plugins and extensions (detailed)

#### Markdown extensions (code anchors and inclusion)

```yaml
# mkdocs.yml — code anchors and snippets (no raw code blocks for source)
markdown_extensions:
  - pymdownx.highlight:
      anchor_linenums: true
      line_spans: __span
      pygments_lang_class: true
  - pymdownx.inlinehilite
  - pymdownx.snippets:
      base_path: [., radioshaq]
      check_paths: true
  - pymdownx.superfences
  - pymdownx.tabbed:
      alternate_style: true
      slugify: !!python/object/apply:pymdownx.slugs.slugify
        kwds:
          case: lower
```

- **pymdownx.highlight** with `anchor_linenums: true`: every line in a code block gets an anchor ID; line numbers become clickable and shareable (e.g. `#L1`, `#L15`).
- **pymdownx.snippets**: include content from repo files. `base_path: [., radioshaq]` allows paths relative to repo root and to `radioshaq/` (e.g. `radioshaq/.env.example`). Use `check_paths: true` so the build fails if a snippet file is missing.
- **pymdownx.tabbed** with `slugify`: content tabs get readable anchor links (e.g. `#bash` instead of `#tab-1`).

#### Theme features (code and navigation)

```yaml
theme:
  name: material
  language: en
  features:
    - navigation.tabs
    - navigation.tabs.sticky
    - navigation.path
    - content.tabs.link
    - content.code.copy
    - content.code.select
    - content.code.annotate
    - toc.follow
```

- **content.code.copy**: one-click copy for code blocks (including snippet-included code).
- **content.code.select**: button to select line ranges and highlight (great for “see lines 10–20”).
- **content.code.annotate**: attach annotations to lines via `# (1)` in comments; use sparingly for “why” notes next to snippet-included code.
- **navigation.path**: breadcrumbs above the page title (improves orientation on mobile).
- **navigation.tabs.sticky**: tabs stay visible when scrolling.

#### Plugin: last update time

```yaml
plugins:
  - search
  - git-revision-date-localized:
      type: date
      timezone: UTC
      locale: en
      fallback_to_build_date: true
```

- **mkdocs-git-revision-date-localized-plugin**: shows “Last updated: &lt;date&gt;” per page from git commit date. Install: `pip install mkdocs-git-revision-date-localized-plugin`. If build is not in a git repo or file is untracked, `fallback_to_build_date: true` uses build time. Options: `type: date` (e.g. “28 November 2019”), `datetime`, `iso_date`, `timeago` (“2 days ago”). Locale follows `theme.language` or set explicitly.

### 5.4 Detailed examples: snippets and code anchors

#### Example 1: Include full file with line anchors

In `docs/configuration.md`, include the example env file so every line is linkable:

```markdown
## Environment variables

The app reads from the following variables. Source:

--8<-- "radioshaq/.env.example"
```

Rendered: full content of `radioshaq/.env.example` in a code block with line numbers; each line number is an anchor (e.g. `configuration/#L5`). Use `title=".env.example"` in a fenced wrapper if desired (see Example 3).

#### Example 2: Include line range

Include only lines 99–132 of the config schema (RadioConfig):

```markdown
--8<-- "radioshaq/radioshaq/config/schema.py:99:132"
```

Syntax: `path:start:end`. Lines 99–132 are included; anchors still apply to the shown lines. To include from start to line 50: `schema.py::50`. From line 200 to end: `schema.py:200`.

#### Example 3: Named section (pymdown-extensions 9.7+)

In source, add section markers in comments:

```python
# radioshaq/radioshaq/api/server.py
def create_app() -> FastAPI:
    # --8<-- [start:create_app]
    app = FastAPI(...)
    ...
    return app
    # --8<-- [end:create_app]
```

In docs:

```markdown
--8<-- "radioshaq/radioshaq/api/server.py:create_app"
```

Only the marked block is included; line anchors apply to that block. Section markers are stripped from the output.

#### Example 4: Snippet inside a fenced block with title and language

To get syntax highlighting and a title when including a file:

````markdown
``` yaml title=".env.example"
--8<-- "radioshaq/.env.example"
```
````

This renders as a YAML block titled “.env.example” with anchor_linenums (if highlight is configured as above).

#### Example 5: Content tabs (PowerShell vs Bash) with anchor links

Use tabs for shell variants; each tab gets an anchor (e.g. `#powershell`, `#bash` with slugify):

```markdown
=== "PowerShell"
    ``` powershell title="Get token"
    --8<-- "docs/snippets/auth-get-token.ps1"
    ```

=== "Bash"
    ``` bash title="Get token"
    --8<-- "docs/snippets/auth-get-token.sh"
    ```
```

Store the actual commands in `docs/snippets/auth-get-token.ps1` and `.sh` so the doc never duplicates them and line anchors work.

### 5.5 Authoring checklist for technical pages

- [ ] No raw fenced code blocks containing source code from the repo; use `--8<-- "path"` or `path:start:end` or `path:section`.
- [ ] Snippet paths are relative to `base_path` (e.g. `radioshaq/.env.example`, `radioshaq/radioshaq/config/schema.py:99:132`).
- [ ] Where a single command is not in a file, consider adding a small snippet file (e.g. under `docs/snippets/`) and including it so anchors are still available.
- [ ] Content tabs use slugify so “PowerShell” / “Bash” produce readable anchors.
- [ ] `mkdocs build` runs with `check_paths: true` so missing snippets fail the build.

---

## 6. File-Level Task Summary

| File | Tasks |
|------|--------|
| `mkdocs.yml` (repo root) | Create; site_name, docs_dir, **site_url** (GitHub Pages URL); theme material with **navigation.instant** + navigation.tabs, navigation.path, content.code.*; markdown_extensions (highlight, snippets, superfences, tabbed); plugins **search**, git-revision-date-localized, **OpenAPI plugin** (e.g. neoteroi-mkdocs); nav including API Reference (OpenAPI-generated). |
| `docs/requirements.txt` | mkdocs-material>=9.5, mkdocs-git-revision-date-localized-plugin, pymdown-extensions, **neoteroi-mkdocs** (or chosen OpenAPI plugin); optionally mkdocstrings[python]. |
| `docs/index.md` | About: tagline, what the agent is, REACT/capabilities, where it runs. No code blocks; link to repo or use snippets if showing code. |
| `docs/quick-start.md` | Prerequisites, steps; use snippets for commands (e.g. docs/snippets/*.ps1, *.sh) and content tabs PowerShell/Bash; anchor-friendly. |
| `docs/radio-usage.md` | Station principale, portable, remote receiver, audio TX, HackRF; config via snippets from radioshaq or docs/snippets; tables. |
| `docs/configuration.md` | Env vars, Database, JWT, LLM, Radio, Audio; include .env.example and schema excerpts via snippets (with line anchors). |
| `docs/api-reference.md` (or `api-reference/`) | **OpenAPI-generated** content via plugin (e.g. `[OAD(api/openapi.json)]`); optional short intro (auth, base URL). |
| `docs/api/openapi.json` | Exported at build time from FastAPI `app.openapi()`; not committed or generated by script in build-docs job. |
| `radioshaq/scripts/export_openapi.py` (or inline in CI) | Script that imports app, calls `app.openapi()`, writes JSON to `docs/api/openapi.json`. |
| `docs/requirements.txt` | Include `neoteroi-mkdocs` (or chosen OpenAPI plugin) and other doc deps. |
| `docs/snippets/` (optional) | Small shell scripts or config fragments included by docs so all code has anchors. |
| `.github/workflows/build-docs.yml` | workflow_dispatch only; job test → build-docs (export OpenAPI, mkdocs build, upload-pages-artifact) → **deploy** (deploy-pages). |
| `.gitignore` | Remove `docs/` so docs are tracked. |
| `docs/legacy/` or `docs/docs/` | Move or keep legacy MDs; add Legacy index page if desired. |
| `radioshaq/README.md` | Update doc links to new site or relative paths to new docs. |

---

## 7. Line-Level Subtask Checklist (critical files)

### `mkdocs.yml`

- Set `site_name: "RadioShaq"`, `site_description: "..."`, `site_url` (e.g. `https://<org>.github.io/<repo>/`) for instant loading and mobile.
- Set `docs_dir: docs`, `site_dir: site`.
- Under `theme`: `name: material`; `language: en`; `features`: **`navigation.instant`** (mandatory), `navigation.tabs`, `navigation.tabs.sticky`, `navigation.path`, `content.tabs.link`, `content.code.copy`, `content.code.select`, `content.code.annotate`, `toc.follow`; optionally `navigation.instant.prefetch`, `navigation.instant.progress`.
- `markdown_extensions`: `pymdownx.highlight` with `anchor_linenums: true`, `line_spans: __span`, `pygments_lang_class: true`; `pymdownx.inlinehilite`; `pymdownx.snippets` with `base_path: [., radioshaq]`, `check_paths: true`; `pymdownx.superfences`; `pymdownx.tabbed` with `alternate_style: true` and slugify for readable tab anchors.
- `plugins`: **`search`** (mandatory); `git-revision-date-localized` with `type: date`, `fallback_to_build_date: true`; OpenAPI plugin (e.g. neoteroi-mkdocs) for API reference; add `mkdocstrings` only if using it.
- **`site_url`** (mandatory): set to `https://<owner>.github.io/<repo>/` so instant loading and sitemap work; required by Material for `navigation.instant`.
- **`theme.features`** must include **`navigation.instant`** (mandatory); optionally `navigation.instant.prefetch`, `navigation.instant.progress`.
- `nav`: five entries — About → index.md; Quick Start → quick-start.md; Radio Usage → radio-usage.md; Configuration → configuration.md; API Reference → api-reference.md (or api-reference/index.md, OpenAPI-generated).

### `.github/workflows/build-docs.yml`

- `on: workflow_dispatch:` only. Permissions: `contents: read` (workflow); deploy job: `pages: write`, `id-token: write`.
- `jobs.test`: checkout, setup-python 3.11, install uv, `cd radioshaq && uv sync --extra dev --extra test && uv run pytest tests/unit tests/integration -v`.
- `jobs.build-docs`: `needs: [test]`; checkout; install deps (MkDocs, Material, git-revision-date-localized, OpenAPI plugin); export OpenAPI to `docs/api/openapi.json`; `mkdocs build`; step `actions/upload-pages-artifact@v4` with `path: site/`.
- **`jobs.deploy` (mandatory):** `needs: [build-docs]`; `runs-on: ubuntu-latest`; `environment: github-pages`; one step: `actions/deploy-pages@v4`. Repo Settings → Pages → Source = GitHub Actions.

### `docs/index.md`

- First line or frontmatter: title "About".
- Paragraph 1: tagline and one sentence what RadioShaq is.
- Paragraph 2: autonomous agent (REACT, planning, tools, agents).
- Bullets or short sections: capabilities; where it runs (main app, remote receiver).

### `docs/quick-start.md`

- Prerequisites; Step 1–6 as in Activity 3.1; use snippets for commands (e.g. `--8<-- "docs/snippets/..."`) so code has line anchors; content tabs for PowerShell vs Bash; no raw code blocks for repo source.

### `docs/radio-usage.md`

- Overview table; sections for station principale, portable, remote receiver, audio TX, HackRF; quick reference table at end.

### `docs/configuration.md`

- Sections: Environment variables, Database, JWT, LLM, Radio, Audio; include `radioshaq/.env.example` and schema excerpts via snippets (anchor_linenums); tables for summary.

### `docs/api-reference.md`

- Intro (auth, base URL); one subsection per router with method, path, description, request/response; use snippets for example payloads from repo where possible (line anchors).

---

## 8. Implementation Order

| Order | Project / Activity | Rationale |
|-------|--------------------|-----------|
| 1 | 8.1 — Un-ignore docs, legacy layout | So new docs can be committed and built. |
| 2 | 1.1, 1.2, 1.3 — MkDocs setup, deps, placeholders | Get `mkdocs build` green with tabbed nav. |
| 3 | 7.1, 7.2, 7.3 — GitHub Actions (test, build-docs, **deploy**) | Manual trigger; tests → build (with OpenAPI export) → upload-pages-artifact → deploy-pages; set Pages source to GitHub Actions. |
| 4 | 6.3 — API reference from OpenAPI | Export script; OpenAPI plugin in mkdocs.yml; API Reference page embeds generated docs; run export in build-docs job. |
| 5 | 1.1 — Ensure site_url + navigation.instant | Required for instant loading; site_url = GitHub Pages URL. |
| 6 | 2.1 — About / index.md | Front page for engagement. |
| 7 | 3.1 — Quick Start | Next most critical for engagement. |
| 8 | 4.1 — Radio Usage | High value for hardware users. |
| 9 | 5.1 — Configuration | Reference for operators. |
| 10 | 6.1, 6.2 — API Reference overview + OpenAPI page | Intro text; nav to OpenAPI-generated content. |
| 11 | 8.2 — README links | Point to new docs (GitHub Pages URL). |
| 12 | 5.x — Code anchors and snippets | docs/snippets/; snippet includes; verify anchor_linenums and update time. |
| 13 | 6.4 — Optional mkdocstrings | If desired for Python modules. |

---

## 9. Success Criteria

- **Manual only:** Workflow runs only via "Run workflow" (workflow_dispatch); no runs on push or PR.
- **Tests first:** If tests fail, docs job does not run; artifact is produced only after tests pass.
- **Build:** `mkdocs build` succeeds from repo root and produces `site/` with all five nav sections.
- **GitHub Pages (mandatory):** Deploy job runs after build-docs; site is published and reachable at `https://<owner>.github.io/<repo>/`; `site_url` in mkdocs.yml matches this URL.
- **API reference from OpenAPI (mandatory):** API Reference page content is generated from the FastAPI OpenAPI spec (exported at build time, rendered via MkDocs plugin).
- **Search and instant loading (mandatory):** `site_url` is set; `navigation.instant` is enabled; search plugin is active; internal links load without full page reload and search index survives navigation.
- **Tabs:** Top-level navigation appears as tabs (Material `navigation.tabs`).
- **Code anchors only:** No free-standing code blocks for repo source; code is included via Snippets; all code blocks have line-number anchors (clickable/shareable).
- **Update time:** Each page shows last updated date (git-revision-date-localized or build date).
- **Mobile:** Site displays correctly on narrow viewports; breadcrumbs (`navigation.path`) visible; no custom CSS that breaks layout.
- **Content:** About describes the agent; Quick Start gets a user to a running API and JWT; Radio Usage covers rigs and remote receiver; Configuration documents env and main options; API Reference is OpenAPI-generated.
- **Engagement:** Clear structure, snippet-included commands with copy/select, content tabs (PowerShell/Bash) with readable anchors, search working.
- **Legacy:** Legacy files in `docs/docs/` rehomed or linked from one Legacy page; new content is the single source of truth for the five main sections.

---

## 10. Mandatory features: implementation details

### 10.1 GitHub Pages (mandatory)

- **Artifact:** `actions/upload-pages-artifact@v4` (or v3) with `path: site/` — the default `path` is `_site/`; MkDocs uses `site_dir: site` so **must** set `path: site/`.
- **Deploy:** `actions/deploy-pages@v4` in a separate job with `needs: build-docs`, `environment: github-pages`, permissions `pages: write`, `id-token: write`. No need to pass the artifact explicitly; deploy-pages uses the artifact uploaded by upload-pages-artifact from the build job.
- **Repo:** Settings → Pages → Build and deployment → Source: **GitHub Actions**. First deployment may require creating the `github-pages` environment (Settings → Environments).
- **URL:** After deploy, site is at `https://<owner>.github.io/<repo>/`. Set `site_url: https://<owner>.github.io/<repo>/` in `mkdocs.yml` (trailing slash per MkDocs convention).

### 10.2 API reference from OpenAPI (mandatory)

- **Export:** FastAPI exposes `app.openapi()`. In CI, before `mkdocs build`, run a script that: (1) adds repo root and `radioshaq` to `sys.path`, (2) imports the app (e.g. `from radioshaq.api.server import app`), (3) writes `json.dumps(app.openapi(), indent=2)` to `docs/api/openapi.json`. Ensure `docs/api/` exists (create in script or in repo).
- **Plugin options:** (1) **neoteroi-mkdocs** — install `neoteroi-mkdocs`, add to `plugins:`, in a markdown page use `[OAD(api/openapi.json)]` to embed generated API docs. (2) **mkdocs-openapi-markdown** or similar — generate one or more .md files from the spec; add those to `nav`. Prefer a plugin that renders from a single spec file so export-on-build is enough.
- **Nav:** API Reference tab links to the page that contains the OpenAPI-generated content (and optionally a short intro).

### 10.3 Search and instant loading (mandatory)

- **site_url:** **Required** by Material for instant loading (uses sitemap). Set to the deployed site URL (GitHub Pages). If omitted, instant navigation will not work correctly.
- **navigation.instant:** Add to `theme.features`. Enables XHR-based navigation without full reload; search index is preserved across page changes.
- **Optional:** `navigation.instant.prefetch` (prefetch on link hover), `navigation.instant.progress` (progress bar on slow loads).
- **Search:** Default `plugins: [search]` is sufficient; no extra config required for search to work with instant loading.

---

## 11. Optional Enhancements (later)

- **Versioning:** Use `mike` or Material’s versioning for multiple doc versions.
- **Mobile testing:** Add a CI step or doc note to test build in a narrow viewport (e.g. Chrome DevTools device mode) to confirm breadcrumbs and tabs behave correctly.

---

*End of plan.*
