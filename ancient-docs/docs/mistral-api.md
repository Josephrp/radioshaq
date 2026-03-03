# Mistral API and OAuth in SHAKODS

SHAKODS uses **Mistral** (or other providers via LiteLLM) for the **REACT orchestrator and judge** when the LLM-backed agent is enabled. This document explains how authentication works and how to connect correctly.

---

## How Mistral is used in the agent

- **LLM client**: [shakods/llm/client.py](../shakods/llm/client.py) uses **LiteLLM** with a default model of `mistral/mistral-large-latest`. It is the backend for the **JudgeSystem** (task and subtask evaluation) and for the **REACTOrchestrator** when the app wires an orchestrator with a real LLM.
- **Auth in code**: The client does **not** use OAuth. It uses an **API key** passed to `litellm.acompletion(..., api_key=...)` or read from the environment.
- **Where the key is taken from** (in order):
  1. `LLMClient(api_key=...)` if you construct the client with a key
  2. Environment variable **`MISTRAL_API_KEY`**
  3. Environment variable **`OPENAI_API_KEY`** (LiteLLM fallback)

So for the agent to work with Mistral, you must set **`MISTRAL_API_KEY`** (or pass an API key when building the LLM client). No OAuth flow is required for standard Mistral API usage.

---

## Mistral OAuth manager (stub)

The repo includes [shakods/auth/oauth_mistral.py](../shakods/auth/oauth_mistral.py), which defines **`MistralOAuthManager`**:

- **Current behaviour**: It reads **`MISTRAL_API_KEY`** from the environment (or a key passed in the constructor) and exposes it via `get_api_key()` and `get_access_token_for_llm()`. There is **no OAuth flow** implemented; it is API-key only.
- **OAuth placeholder**: The class has an `oauth_config` and a `refresh_if_needed()` stub. The comment says it “can integrate oauth-cli-kit for OAuth flow” in the future. Today, nothing in the codebase uses `MistralOAuthManager` for the LLM; the **LLMClient** talks to LiteLLM with `MISTRAL_API_KEY` (or the key you pass).
- **Conclusion**: You do **not** need to use or configure OAuth to connect to the Mistral API. Use an API key only.

---

## How to connect to the Mistral API correctly

### 1. Get a Mistral API key

- Sign up at [console.mistral.ai](https://console.mistral.ai).
- Create an API key in your workspace (e.g. “Create new key” in the API Keys section).
- Store it securely. Do **not** commit it to the repo.

### 2. Set the key in the environment

**Bash (Linux/macOS):**
```bash
export MISTRAL_API_KEY="your-mistral-api-key"
```

**PowerShell:**
```powershell
$env:MISTRAL_API_KEY = "your-mistral-api-key"
```

**Windows (persistent, user):**
```powershell
[System.Environment]::SetEnvironmentVariable("MISTRAL_API_KEY", "your-mistral-api-key", "User")
```

### 3. Optional: config file

If your app loads [LLMConfig](../shakods/config/schema.py) from file or env, you can set:

- **`llm.mistral_api_key`** – API key (prefer env in production).
- **`llm.model`** – e.g. `mistral-large-latest`, `mistral-small-latest` (LiteLLM will use `mistral/<model>` if needed).
- **`llm.provider`** – `mistral` (default).

Example in YAML (optional; env vars override):

```yaml
llm:
  provider: mistral
  model: mistral-large-latest
  # Prefer MISTRAL_API_KEY in env; do not put secrets in config in production
  # mistral_api_key: your-key
```

### 4. Verify

With the API running and the orchestrator wired to use the LLM (see below), a request that triggers the REACT loop (e.g. `POST /messages/process` with a message) will call Mistral. If the key is missing or invalid, LiteLLM will raise an auth error.

You can also sanity-check the key with curl:

```bash
curl "https://api.mistral.ai/v1/models" -H "Authorization: Bearer $MISTRAL_API_KEY"
```

---

## When does the agent use Mistral?

The **REACT orchestrator** and **JudgeSystem** use the LLM only if:

1. The app **creates** an orchestrator and attaches it to `app.state.orchestrator` (e.g. in lifespan or a startup script). The default [server lifespan](../shakods/api/server.py) sets `app.state.orchestrator = None`, so **by default the agent is not wired** and `POST /messages/process` returns 503.
2. When the orchestrator **is** wired, it is typically built with a **JudgeSystem** that uses an **LLMClient**. That client uses LiteLLM with `MISTRAL_API_KEY` (or the key you pass) and the configured model.

So:

- **Demo / inject / relay**: No Mistral needed; those flows do not require the REACT agent.
- **Full agent (POST /messages/process)**: Requires the orchestrator to be started with an LLM; then setting **`MISTRAL_API_KEY`** (or passing the key into the LLM client) connects the agent to the Mistral API correctly.

---

## Summary

| Topic | Detail |
|--------|--------|
| **Auth type** | API key (Bearer). No OAuth required. |
| **Env var** | **`MISTRAL_API_KEY`** |
| **Used by** | **LLMClient** (LiteLLM) → JudgeSystem / REACTOrchestrator when the orchestrator is wired. |
| **MistralOAuthManager** | Stub; currently only exposes API key from env. Not required for connecting to the Mistral API. |
| **Correct setup** | Set `MISTRAL_API_KEY`; optionally set `llm.model` / `llm.provider` in config. |

For SHAKODS JWT auth (API tokens for inject/relay/transcripts), see [auth.md](auth.md).
