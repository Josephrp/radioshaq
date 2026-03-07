# Hugging Face Inference Providers — LLM Support Plan

Add **Hugging Face Inference Providers** as a first-class LLM option so users can run chat (and tool-calling) via the HF router (`https://router.huggingface.co/v1`) without changing the existing LiteLLM-based client.

---

## Current state (summary)

- **Config**: `LLMConfig` has `provider` (mistral, openai, anthropic, custom), `model`, provider-specific keys, `custom_api_base`, `custom_api_key`. Per-role overrides via `config.llm_overrides[role]`.
- **Resolve**: `get_llm_config_for_role(config, role)` merges `config.llm` with overrides.
- **Factory**: `_llm_model_string_from_llm_config(llm)` → `provider/model`; `_llm_api_key_from_llm_config(llm)` → first non-None of mistral/openai/anthropic/custom keys; `api_base` only from `custom_api_base`. Builds `LLMClient` for judge, whitelist, orchestrator.
- **Client**: `LLMClient` calls `litellm.acompletion(**kwargs)`; api_key fallback: `MISTRAL_API_KEY` or `OPENAI_API_KEY`.
- **Call sites**: Judge, Whitelist agent, REACT orchestrator, daily summary cron (all use factory helpers + `LLMClient`).

**HF Inference Providers**: OpenAI-compatible router at `https://router.huggingface.co/v1`; auth = HF token with "Inference Providers" permission; model IDs e.g. `openai/gpt-oss-120b:groq`, `Qwen/Qwen2.5-7B-Instruct-1M`. We add provider `huggingface` and set `api_base` + provider-matched key; model string for LiteLLM: `openai/<user_model>` so the OpenAI client is used.

---

## Project 1: Config schema and factory (core wiring)

### Activity 1.1: Schema — Hugging Face provider and keys

| # | File | Task | Line-level subtasks |
|---|------|------|---------------------|
| 1.1.1 | `radioshaq/radioshaq/config/schema.py` | Add Hugging Face to LLM provider and config | In `LLMProvider` add `HUGGINGFACE = "huggingface"`. In `LLMConfig` add `huggingface_api_key: str \| None = Field(default=None)` and `huggingface_api_base: str \| None = Field(default=None, description="Default: https://router.huggingface.co/v1 when provider is huggingface.")`. |

### Activity 1.2: Factory — model string, api_base, api_key (provider-matched)

| # | File | Task | Line-level subtasks |
|---|------|------|---------------------|
| 1.2.1 | `radioshaq/radioshaq/orchestrator/factory.py` | Handle huggingface in model string | In `_llm_model_string_from_llm_config`: if `p == "huggingface"`, return `("openai/" + model)` if `model` and not `model.startswith("openai/")`, else `(model or "openai/")`. |
| 1.2.2 | `radioshaq/radioshaq/orchestrator/factory.py` | Add _llm_api_base_for_provider | New helper `_llm_api_base_for_provider(llm_cfg: LLMConfig) -> str \| None`: if provider is `"huggingface"` return `llm_cfg.huggingface_api_base or "https://router.huggingface.co/v1"`; if `"custom"` return `llm_cfg.custom_api_base`; else return `None`. |
| 1.2.3 | `radioshaq/radioshaq/orchestrator/factory.py` | API key by configured provider | In `_llm_api_key_from_llm_config`: resolve `provider` (string lower); return key for that provider: huggingface → `huggingface_api_key`, custom → `custom_api_key`, anthropic → `anthropic_api_key`, openai → `openai_api_key`, mistral → `mistral_api_key`; else `None`. |
| 1.2.4 | `radioshaq/radioshaq/orchestrator/factory.py` | Use api_base helper at all LLMClient call sites | In `create_judge`: replace `api_base=getattr(llm_cfg, "custom_api_base", None)` with `api_base=_llm_api_base_for_provider(llm_cfg)`. Same in whitelist agent creation and in `create_orchestrator` when building `llm_client`. |

### Activity 1.3: Client and daily_summary

| # | File | Task | Line-level subtasks |
|---|------|------|---------------------|
| 1.3.1 | `radioshaq/radioshaq/llm/client.py` | Env fallback for HF token | In `chat()` and `chat_with_tools()`, extend api_key fallback: after `OPENAI_API_KEY` add `os.environ.get("HF_TOKEN")` and `os.environ.get("HUGGINGFACE_API_KEY")`. |
| 1.3.2 | `radioshaq/radioshaq/memory/daily_summary_cron.py` | Use _llm_api_base_for_provider for daily_summary | Import `_llm_api_base_for_provider` from `radioshaq.orchestrator.factory`. When building `LLMClient` for daily_summary, use `api_base=_llm_api_base_for_provider(llm_cfg)` instead of `getattr(llm_cfg, "custom_api_base", None)`. |

---

## Project 2: Config files, setup, CLI, API, docs

### Activity 2.1: Example config and env reference

| # | File | Task | Line-level subtasks |
|---|------|------|---------------------|
| 2.1.1 | `radioshaq/config.example.yaml` | Add Hugging Face LLM options | Under `llm:`, add `huggingface_api_key: null` and `huggingface_api_base: null` with comment: for `provider: huggingface` set key or `HF_TOKEN`; optional base (default router URL). |
| 2.1.2 | `docs/reference/.env.example` | Document HF token for Inference Providers | Add `HF_TOKEN` and optionally `HUGGINGFACE_API_KEY` with note: required when `llm.provider` is huggingface; token needs "Inference Providers" permission. |

### Activity 2.2: Setup and CLI

| # | File | Task | Line-level subtasks |
|---|------|------|---------------------|
| 2.2.1 | `radioshaq/radioshaq/setup.py` | Accept huggingface in provider prompt and write config | In provider prompt/validation allow `"huggingface"`. When provider is huggingface, prompt for Hugging Face API key (or env `HF_TOKEN`) and optional api_base; write `huggingface_api_key`, `huggingface_api_base` to config; include in llm_overrides when building per-role entries. |
| 2.2.2 | `radioshaq/radioshaq/cli.py` | Add huggingface to --llm-provider and overrides | Add `huggingface` to `--llm-provider` choices and to any llm_overrides parsing/validation so `{"orchestrator":{"provider":"huggingface",...}}` is accepted. |

### Activity 2.3: API redaction and configuration docs

| # | File | Task | Line-level subtasks |
|---|------|------|---------------------|
| 2.3.1 | `radioshaq/radioshaq/api/routes/config_routes.py` | Redact huggingface_api_key | Add `"huggingface_api_key"` to `_LLM_SECRET_KEYS` so it is redacted in config API responses. |
| 2.3.2 | `docs/configuration.md` | Document Hugging Face provider | In LLM section: add `huggingface` to provider list; document `llm.provider: huggingface`, `llm.model` (e.g. `openai/gpt-oss-120b:groq`, `Qwen/Qwen2.5-7B-Instruct-1M`), `llm.huggingface_api_key`, `llm.huggingface_api_base`; note env `HF_TOKEN`; link to [HF Inference Providers](https://huggingface.co/docs/inference-providers). |

---

## Project 3: Tests and Web UI

### Activity 3.1: Unit tests

| # | File | Task | Line-level subtasks |
|---|------|------|---------------------|
| 3.1.1 | `radioshaq/tests/unit/test_config_llm.py` (new or extend) | Test LLMConfig huggingface | Test `LLMConfig(provider="huggingface", model="Qwen/Qwen2.5-7B-Instruct-1M")`; test `huggingface_api_key`, `huggingface_api_base` exist and default to None. |
| 3.1.2 | `radioshaq/tests/unit/test_llm_factory.py` (new) or in `test_orchestrator.py` | Test factory helpers for huggingface | Test `_llm_model_string_from_llm_config` with provider huggingface: model without `openai/` prefix becomes `openai/<model>`, with prefix stays; test `_llm_api_base_for_provider` returns HF router URL when provider huggingface and base None, returns custom_api_base when custom; test `_llm_api_key_from_llm_config` returns huggingface_api_key when provider is huggingface. |
| 3.1.3 | `radioshaq/tests/unit/test_llm_client.py` (new) or existing | Test client HF env fallback | When `api_key` is None, client uses env; test or document that `HF_TOKEN` / `HUGGINGFACE_API_KEY` are in fallback chain (can be tested by patching os.environ and calling chat with mock litellm). |

### Activity 3.2: Web UI (optional)

| # | File | Task | Line-level subtasks |
|---|------|------|---------------------|
| 3.2.1 | `radioshaq/web-interface/src/features/settings/SettingsPage.tsx` | Add huggingface to provider dropdown | Add `<option value="huggingface">huggingface</option>`. When provider is huggingface, show fields for `huggingface_api_key` and `huggingface_api_base` (same pattern as custom_api_base). |
| 3.2.2 | `radioshaq/web-interface/src/services/radioshaqApi.ts` (or types) | LLM config type | Ensure LLM config type includes `huggingface_api_key?: string \| null` and `huggingface_api_base?: string \| null`. |

---

## File summary (new vs modified)

**Modified**

- `radioshaq/radioshaq/config/schema.py` — LLMProvider, LLMConfig
- `radioshaq/radioshaq/orchestrator/factory.py` — model string, _llm_api_base_for_provider, _llm_api_key, api_base at call sites
- `radioshaq/radioshaq/llm/client.py` — env fallback HF_TOKEN, HUGGINGFACE_API_KEY
- `radioshaq/radioshaq/memory/daily_summary_cron.py` — import and use _llm_api_base_for_provider
- `radioshaq/config.example.yaml` — llm huggingface_*
- `docs/reference/.env.example` — HF_TOKEN
- `radioshaq/radioshaq/setup.py` — provider huggingface, prompts, write config
- `radioshaq/radioshaq/cli.py` — --llm-provider huggingface, overrides
- `radioshaq/radioshaq/api/routes/config_routes.py` — _LLM_SECRET_KEYS
- `docs/configuration.md` — LLM Hugging Face subsection
- `radioshaq/web-interface/...` — provider option and fields (optional)
- `radioshaq/tests/unit/...` — new or extended tests

**New**

- `radioshaq/tests/unit/test_llm_factory.py` (or tests in test_orchestrator / test_config_llm) — factory and config tests

---

## Optional / later

- **HF InferenceClient**: For embeddings, image generation, etc.; separate adapter if needed.
- **Routing policies**: Document `:fastest`, `:cheapest` in model ID where supported.
- **Streaming**: HF router supports it; add when we add streaming to LLMClient.
