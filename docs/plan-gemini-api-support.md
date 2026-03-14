# Plan: Add Gemini API Support to RadioShaq LLM Configuration

This document summarizes **Google Gemini API authentication** (from official docs), how **LLMs are authenticated and configured in this repo**, and a **complete implementation plan** with projects, activities, file-level tasks, and line-level subtasks to support and configure the Gemini API in RadioShaq.

---

## 1. Google Authentication & Gemini API (Summary)

### 1.1 Authentication options

- **API key (recommended for most use)**  
  All requests must include an `x-goog-api-key` header. Create a key in [Google AI Studio](https://aistudio.google.com/).  
  Env: `GEMINI_API_KEY` (common convention; LiteLLM uses this).

- **OAuth**  
  For stricter access control (e.g. production with Google Cloud). Uses application-default credentials or OAuth flow. Not required for standard Gemini API usage; this plan focuses on **API key** only.

### 1.2 Endpoint and usage

- **Endpoint**: `https://generativelanguage.googleapis.com` (Google AI Studio).
- **Example**:  
  `POST .../v1beta/models/gemini-2.5-flash:generateContent` (or `gemini-3-flash-preview`, etc.) with header `x-goog-api-key: $GEMINI_API_KEY`.
- **Models**: e.g. `gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-3-flash-preview`, `gemini-3.1-flash-lite-preview`. LiteLLM uses the `gemini/` prefix (e.g. `gemini/gemini-2.5-flash`).

### 1.3 LiteLLM support

LiteLLM supports Gemini via the **Gemini API** (Google AI Studio):

- **Model format**: `gemini/<model-id>` (e.g. `gemini/gemini-2.5-flash`, `gemini/gemini-pro`).
- **Auth**: Pass `api_key` to `litellm.acompletion(...)` or set `os.environ["GEMINI_API_KEY"]`.
- **No custom `api_base`** needed for standard Google AI Studio; LiteLLM uses the correct base URL.

So the existing `LLMClient` (LiteLLM) can support Gemini by:

1. Adding provider `gemini` (or `google`).
2. Building model string `gemini/<model>`.
3. Passing the Gemini API key (config + env `GEMINI_API_KEY`).

---

## 2. How LLMs Are Authenticated and Configured in This Repo

### 2.1 Configuration layer

| Location | Purpose |
|----------|--------|
| `radioshaq/config/schema.py` | `LLMProvider` enum and `LLMConfig` with provider, model, and **per-provider API key fields** (e.g. `mistral_api_key`, `openai_api_key`, `anthropic_api_key`, `custom_api_key`, `huggingface_api_key`). |
| `radioshaq/config/resolve.py` | `get_llm_config_for_role()` returns merged global `llm` + optional `llm_overrides[role]`. |
| Config file / env | `config.yaml` and env vars like `RADIOSHAQ_LLM__PROVIDER`, `RADIOSHAQ_LLM__MODEL`, `RADIOSHAQ_LLM__MISTRAL_API_KEY`, etc. |

**Pattern**: One provider at a time; the chosen provider's key is used. No OAuth in the codebase; API keys only (including for Mistral).

### 2.2 API key resolution

- **Config → key**: `radioshaq/orchestrator/factory.py` → `_llm_api_key_from_llm_config(llm)`.  
  It checks `llm.provider` and returns the matching key: `mistral_api_key`, `openai_api_key`, `anthropic_api_key`, `custom_api_key`, or `huggingface_api_key`.  
  **No `gemini` branch yet.**

- **Client fallback**: `radioshaq/llm/client.py` → `LLMClient.chat()` and `chat_with_tools()`.  
  If `self.api_key` is not set, it falls back to env: `MISTRAL_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `HF_TOKEN`, `HUGGINGFACE_API_KEY`.  
  **No `GEMINI_API_KEY` yet.**

### 2.3 Model string and api_base

- **Model string**: `factory.py` → `_llm_model_string_from_llm_config(llm)`.  
  Builds LiteLLM-style `provider/model` (e.g. `mistral/mistral-large-latest`, `openai/gpt-4o`, `anthropic/...`, `custom/...`, `openai/...` for Hugging Face).  
  **No `gemini/...` branch yet.**

- **api_base**: `factory.py` → `_llm_api_base_for_provider(llm_cfg)`.  
  Only non-`None` for `huggingface` (HF router URL) and `custom` (e.g. Ollama).  
  For Gemini we keep `api_base` as `None` (LiteLLM default).

### 2.4 Where the key is used

- **Judge**: `factory.create_judge()` builds `LLMClient(model=..., api_key=..., api_base=...)` from `get_llm_config_for_role(config, "judge")`.
- **Orchestrator / agents**: Same pattern in `factory.py` (orchestrator, whitelist agent, etc.) via `_llm_api_key_from_llm_config`, `_llm_model_string_from_llm_config`, `_llm_api_base_for_provider`.
- **Daily summary cron**: `radioshaq/memory/daily_summary_cron.py` uses `_llm_api_key_from_llm_config` and builds `LLMClient(..., api_key=api_key, api_base=api_base)`.

### 2.5 Other places that must stay consistent

- **Config API (keys redacted)**: `radioshaq/api/routes/config_routes.py` → `_LLM_SECRET_KEYS` (used to redact keys in GET/PATCH `/config/llm`). Must include any new key field (e.g. `gemini_api_key`).
- **CLI**: `radioshaq/cli.py` → `_safe_llm_dict()` redacts API key fields for `config show`. Must include `gemini_api_key` (and ensure `huggingface_api_key` is present if not already).
- **Setup / .env**: `radioshaq/setup.py` → `write_env()` maps provider → env var for API key (e.g. `mistral` → `MISTRAL_API_KEY`). Add `gemini` → `GEMINI_API_KEY`. Also `_prompt_llm()` lists allowed providers and default models; add `gemini` and a default model (e.g. `gemini-2.5-flash`). When stripping secrets before saving config, set `config.llm.gemini_api_key = None`.
- **Env example and docs**: `radioshaq/.env.example`, `docs/configuration.md`, `docs/reference/.env.example`, `site/...` reference config: add `gemini` provider and `RADIOSHAQ_LLM__GEMINI_API_KEY` / `GEMINI_API_KEY`.
- **Config examples**: `radioshaq/config.example.yaml`, `docs/reference/config.example.yaml`, `site/reference/config.example.yaml`, `site/configuration/index.html`: add `llm.provider: gemini` option and `llm.gemini_api_key`.
- **Web UI**: `radioshaq/web-interface/src/services/radioshaqApi.ts` → `LlmConfigResponse`: add optional `gemini_api_key` if the UI displays or patches LLM config (for consistency with other keys).
- **Integration tests**: `radioshaq/tests/integration/test_live_e2e_workflows.py` → `_LIVE_KEY_ENV_VARS`: add `RADIOSHAQ_LLM__GEMINI_API_KEY` and `GEMINI_API_KEY` so live tests can run with Gemini.
- **Docker / Hindsight**: `radioshaq/infrastructure/local/docker-compose.yml` (and any `ecosystem.config.js` that forwards LLM keys): add `RADIOSHAQ_LLM__GEMINI_API_KEY` and `GEMINI_API_KEY` to the chain of keys passed to Hindsight (or equivalent) so that when provider is Gemini, the key is available.

---

## 3. Complete Implementation Plan: Projects, Activities, Tasks, Subtasks

### Project 1: Schema and configuration model

**Objective:** Add Gemini as a first-class provider in the config schema and ensure validation accepts it.

---

#### Activity 1.1 — Schema: LLMProvider and LLMConfig

**File:** `radioshaq/radioshaq/config/schema.py`

| # | Task | Line-level subtasks |
|---|------|---------------------|
| 1.1.1 | Add Gemini to `LLMProvider` enum | **Lines 54–61:** In `class LLMProvider(StrEnum):`, after `HUGGINGFACE = "huggingface"` add a new line: `GEMINI = "gemini"`. |
| 1.1.2 | Add `gemini_api_key` to `LLMConfig` | **Lines 199–214:** In `class LLMConfig(BaseModel):`, after `anthropic_api_key: str \| None = Field(default=None)` (around line 203) add: `gemini_api_key: str \| None = Field(default=None)`. Place it with the other provider keys (before `# Custom provider`). No `gemini_api_base` needed for standard Google AI Studio. |

---

### Project 2: Runtime — factory and LLM client

**Objective:** Wire Gemini into model-string building, API-key resolution, and client env fallback so judge, orchestrator, agents, and daily summary use Gemini when configured.

---

#### Activity 2.1 — Factory: model string and API key

**File:** `radioshaq/radioshaq/orchestrator/factory.py`

| # | Task | Line-level subtasks |
|---|------|---------------------|
| 2.1.1 | Add Gemini branch in `_llm_model_string_from_llm_config` | **Lines 54–75:** After the `if p == "custom":` block (around line 71) and before the fallback `if "/" not in model ...`: add `if p == "gemini":` block: if model is empty or missing, use default `"gemini-2.5-flash"`; if model does not already contain `gemini/`, return `f"gemini/{model}"`; otherwise return `model`. |
| 2.1.2 | Add Gemini branch in `_llm_api_key_from_llm_config` | **Lines 94–108:** In `_llm_api_key_from_llm_config`, after `if p == "mistral": return getattr(llm, "mistral_api_key", None)` add: `if p == "gemini": return getattr(llm, "gemini_api_key", None)`. |
| 2.1.3 | Confirm `_llm_api_base_for_provider` for Gemini | **Lines 78–87:** No code change. Ensure behavior: for provider `gemini`, `p == "gemini"` is not handled, so the function returns `None` (correct; LiteLLM uses default Gemini base). Document in comment if desired. |

---

#### Activity 2.2 — LLM client: env fallback for API key

**File:** `radioshaq/radioshaq/llm/client.py`

| # | Task | Line-level subtasks |
|---|------|---------------------|
| 2.2.1 | Add `GEMINI_API_KEY` to env fallback in `chat()` | **Lines 78–85:** In the `api_key = (self.api_key or os.environ.get(...))` chain, add `or os.environ.get("GEMINI_API_KEY")` (e.g. after `HUGGINGFACE_API_KEY`). |
| 2.2.2 | Add `GEMINI_API_KEY` to env fallback in `chat_with_tools()` | **Lines 130–136:** In the same `api_key = (...)` chain in `chat_with_tools()`, add `or os.environ.get("GEMINI_API_KEY")`. |

---

### Project 3: API, CLI, and setup

**Objective:** Redact Gemini API key in config API and CLI; support Gemini in interactive setup, env writing, and config save (strip secret).

---

#### Activity 3.1 — Config API: redact Gemini key

**File:** `radioshaq/radioshaq/api/routes/config_routes.py`

| # | Task | Line-level subtasks |
|---|------|---------------------|
| 3.1.1 | Add `gemini_api_key` to `_LLM_SECRET_KEYS` | **Lines 21–27:** In the set `_LLM_SECRET_KEYS = {...}`, add `"gemini_api_key"` so GET and PATCH `/config/llm` redact it (existing loops at 37 and 71, 90 already iterate over this set). |

---

#### Activity 3.2 — CLI: redact Gemini key in config show

**File:** `radioshaq/radioshaq/cli.py`

| # | Task | Line-level subtasks |
|---|------|---------------------|
| 3.2.1 | Redact `gemini_api_key` (and `huggingface_api_key`) in `_safe_llm_dict` | **Lines 468–474:** In `_safe_llm_dict`, extend the tuple of keys to redact: add `"gemini_api_key"` and `"huggingface_api_key"` if not already present: `("mistral_api_key", "openai_api_key", "anthropic_api_key", "custom_api_key", "huggingface_api_key", "gemini_api_key")`. |

---

#### Activity 3.3 — Setup: prompts, env writing, and config strip

**File:** `radioshaq/radioshaq/setup.py`

| # | Task | Line-level subtasks |
|---|------|---------------------|
| 3.3.1 | Add `gemini` to provider prompt and validation in `_prompt_llm()` | **Lines 346–352:** Change prompt text to include `gemini`: e.g. `"LLM provider (mistral / openai / anthropic / custom / huggingface / gemini)"`. Add `"gemini"` to the allowed set: `if provider not in ("mistral", "openai", "anthropic", "custom", "huggingface", "gemini"): provider = "mistral"`. **Lines 352–357:** Add `elif provider == "gemini": model_default = "gemini-2.5-flash"`. |
| 3.3.2 | Add `gemini` to `key_var` map in `write_env()` | **Lines 188–195:** In the `key_var = { ... }.get(llm_provider.lower())` dict, add `"gemini": "GEMINI_API_KEY"`. Optionally add `RADIOSHAQ_LLM__GEMINI_API_KEY` to `override_keys` (lines 149–157) so merge logic preserves it. |
| 3.3.3 | Add Gemini to `override_keys` in `write_env()` | **Lines 149–157:** Add `"RADIOSHAQ_LLM__GEMINI_API_KEY"` and `"GEMINI_API_KEY"` to the `override_keys` set so existing .env entries are preserved when merging. |
| 3.3.4 | Strip `gemini_api_key` before saving config | **Lines 926–931:** After `config.llm.huggingface_api_key = None` add: `config.llm.gemini_api_key = None`. |

---

### Project 4: Config examples and documentation

**Objective:** Document Gemini in YAML examples, .env examples, and configuration docs so users can copy-paste and understand provider options.

---

#### Activity 4.1 — YAML config examples

| # | File | Task | Line-level subtasks |
|---|------|------|---------------------|
| 4.1.1 | `radioshaq/config.example.yaml` | Add Gemini to LLM section | **~Line 47:** Update comment: `# mistral \| openai \| anthropic \| custom \| huggingface \| gemini`. **After line 54 (custom_api_key):** add `gemini_api_key: null` and a short comment (e.g. `# For provider: gemini; or set GEMINI_API_KEY`). |
| 4.1.2 | `docs/reference/config.example.yaml` | Same as 4.1.1 | **~Line 46:** Update provider comment to include `gemini`. **After custom_api_key:** add `gemini_api_key: null` with comment. |

---

#### Activity 4.2 — .env examples

| # | File | Task | Line-level subtasks |
|---|------|------|---------------------|
| 4.2.1 | `radioshaq/.env.example` | Add Gemini env vars | **~Lines 55–62:** Add commented line `# RADIOSHAQ_LLM__GEMINI_API_KEY=` with other LLM keys. **~Lines 70–73:** In “Alternative” section add `# GEMINI_API_KEY=`. |
| 4.2.2 | `docs/reference/.env.example` | Same as 4.2.1 | Add `# RADIOSHAQ_LLM__GEMINI_API_KEY=` and `# GEMINI_API_KEY=` in the LLM and alternative sections. |

---

#### Activity 4.3 — Configuration documentation

**File:** `docs/configuration.md`

| # | Task | Line-level subtasks |
|---|------|---------------------|
| 4.3.1 | Add Gemini to provider list and LLM table | **~Line 128:** In the `llm.provider` row, change “One of:” to include `gemini` (e.g. `mistral`, `openai`, `anthropic`, `custom`, `huggingface`, `gemini`). **After ~line 134 (custom_api_key row):** add a new row: `llm.gemini_api_key` \| `RADIOSHAQ_LLM__GEMINI_API_KEY` \| `null` \| Gemini API key (or set `GEMINI_API_KEY`). |
| 4.3.2 | Mention Gemini in “LLM” narrative | **~Line 124:** In the paragraph describing provider options, add “For **Google Gemini** (Google AI Studio), set `provider: gemini`, `model` (e.g. `gemini-2.5-flash`, `gemini-2.5-pro`), and **`gemini_api_key`** or `GEMINI_API_KEY`.” |

---

#### Activity 4.4 — Site / reference config (if present)

| # | File | Task | Line-level subtasks |
|---|------|------|---------------------|
| 4.4.1 | `site/configuration/index.html` (or equivalent) | Add Gemini to provider list and LLM table | If this file exists and lists LLM providers or env vars, add `gemini` and `RADIOSHAQ_LLM__GEMINI_API_KEY` / `GEMINI_API_KEY` for consistency. |
| 4.4.2 | `site/reference/config.example.yaml` | Mirror radioshaq/config.example.yaml | If present, add `gemini_api_key: null` and provider comment as in 4.1.1. |

---

### Project 5: Tests and infrastructure

**Objective:** Unit tests for Gemini in factory and config; integration test env list; Docker/Hindsight env chain for Gemini key.

---

#### Activity 5.1 — Unit tests

| # | File | Task | Line-level subtasks |
|---|------|------|---------------------|
| 5.1.1 | `radioshaq/tests/unit/test_llm_factory.py` | Test Gemini model string | Add test: `LLMConfig(provider=LLMProvider.GEMINI, model="gemini-2.5-flash")` → `_llm_model_string_from_llm_config(llm) == "gemini/gemini-2.5-flash"`. Add test for default model when model is empty. |
| 5.1.2 | `radioshaq/tests/unit/test_llm_factory.py` | Test Gemini API key | Add test: `LLMConfig(provider=LLMProvider.GEMINI, gemini_api_key="key123")` → `_llm_api_key_from_llm_config(llm) == "key123"`. |
| 5.1.3 | `radioshaq/tests/unit/test_llm_factory.py` | Test Gemini api_base is None | Add test: `LLMConfig(provider=LLMProvider.GEMINI)` → `_llm_api_base_for_provider(llm) is None`. |
| 5.1.4 | `radioshaq/tests/unit/test_config_llm.py` | Test LLMConfig supports Gemini | Add test that `LLMConfig(provider=LLMProvider.GEMINI, model="gemini-2.5-flash", gemini_api_key="...")` is valid and fields are as set. |

---

#### Activity 5.2 — Integration tests

**File:** `radioshaq/tests/integration/test_live_e2e_workflows.py`

| # | Task | Line-level subtasks |
|---|------|---------------------|
| 5.2.1 | Add Gemini to live key env vars | **Lines 14–21:** Add `"RADIOSHAQ_LLM__GEMINI_API_KEY"` and `"GEMINI_API_KEY"` to the `_LIVE_KEY_ENV_VARS` tuple so live runs can use Gemini when configured. |

---

#### Activity 5.3 — Docker / Hindsight

**File:** `radioshaq/infrastructure/local/docker-compose.yml`

| # | Task | Line-level subtasks |
|---|------|---------------------|
| 5.3.1 | Add Gemini key to Hindsight API key chain | **Line 155:** Extend the `HINDSIGHT_API_LLM_API_KEY=${...}` environment value to include Gemini keys in the fallback chain, e.g. add `RADIOSHAQ_LLM__GEMINI_API_KEY` and `GEMINI_API_KEY` in the same order-of-precedence style as the existing keys (so when provider is gemini, the key is available to Hindsight if it supports Gemini). |

---

### Project 6: Web UI and verification

**Objective:** Keep TypeScript types in sync with API (redacted Gemini key); define verification steps.

---

#### Activity 6.1 — Web UI types

**File:** `radioshaq/web-interface/src/services/radioshaqApi.ts`

| # | Task | Line-level subtasks |
|---|------|---------------------|
| 6.1.1 | Add `gemini_api_key` to `LlmConfigResponse` | **Lines 86–95:** In `export interface LlmConfigResponse`, add `gemini_api_key?: string \| null;` so the UI type matches the API and keys remain redacted when displayed or patched. |

---

#### Activity 6.2 — Verification (manual / CI)

| # | Task | Line-level subtasks |
|---|------|---------------------|
| 6.2.1 | Manual verification | Set `RADIOSHAQ_LLM__PROVIDER=gemini`, `RADIOSHAQ_LLM__MODEL=gemini-2.5-flash` (or `gemini-2.5-pro`), and `RADIOSHAQ_LLM__GEMINI_API_KEY` or `GEMINI_API_KEY`. Run the app; trigger a flow that uses the LLM (e.g. judge, orchestrator, daily summary). Confirm requests reach the Gemini API and responses are handled. |
| 6.2.2 | Unit tests | Run unit tests for factory and config: `pytest radioshaq/tests/unit/test_llm_factory.py radioshaq/tests/unit/test_config_llm.py -v`. |
| 6.2.3 | Integration tests | If a Gemini key is available, run integration tests with provider=gemini and confirm no regressions. |

---

## 4. Summary checklist (by project)

| Project | Activity | File-level focus | Done |
|---------|----------|------------------|------|
| 1. Schema | 1.1 | `schema.py`: LLMProvider.GEMINI, LLMConfig.gemini_api_key | ☐ |
| 2. Runtime | 2.1 | `factory.py`: model string + api_key for gemini | ☐ |
| 2. Runtime | 2.2 | `client.py`: GEMINI_API_KEY env fallback in chat + chat_with_tools | ☐ |
| 3. API/CLI/Setup | 3.1 | `config_routes.py`: _LLM_SECRET_KEYS + gemini_api_key | ☐ |
| 3. API/CLI/Setup | 3.2 | `cli.py`: _safe_llm_dict + gemini_api_key, huggingface_api_key | ☐ |
| 3. API/CLI/Setup | 3.3 | `setup.py`: _prompt_llm gemini, write_env key_var, override_keys, strip gemini_api_key | ☐ |
| 4. Docs/examples | 4.1–4.4 | config.example.yaml, .env.example, configuration.md, site/* | ☐ |
| 5. Tests/infra | 5.1–5.3 | test_llm_factory.py, test_config_llm.py, test_live_e2e_workflows.py, docker-compose.yml | ☐ |
| 6. Web UI / verify | 6.1–6.2 | radioshaqApi.ts LlmConfigResponse; manual + pytest verification | ☐ |

---

## 5. Dependency order

1. **Project 1** (schema) must be done first; all other code and docs depend on `LLMProvider.GEMINI` and `LLMConfig.gemini_api_key`.
2. **Project 2** (factory + client) can follow immediately; no dependency on 3–6.
3. **Projects 3, 4, 5, 6** can be done in parallel after 1 and 2, except:
   - 5.1 (unit tests) depends on 1 and 2.
   - 6.2 (verification) should be last.

This keeps authentication **API-key only** (no OAuth), aligns with existing provider-specific key and model handling, and ensures Gemini is supported end-to-end (config, env, client, API, CLI, setup, tests, and Docker) with a complete implementation plan down to line-level subtasks.
