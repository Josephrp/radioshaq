# Interface / Dataflow Remediation Plan

**Scope:** Config effectiveness, API-served UI parity, VAD metrics semantics, frontend env docs.  
**Goal:** Runtime configuration semantics explicit; UI and bundle aligned; observability honest.

## Implementation status (complete)

All planned activities and optional items have been implemented:

- **A1.1** — `radioshaq/api/config_semantics.py` added; schema docstring updated.
- **A1.2, A1.3, A1.4** — All config GET responses include `_meta.config_applies_after`; PATCH/reset docstrings updated; PATCH and POST reset return `JSONResponse` with header `X-Config-Effective-After: restart`.
- **A2.1, A2.2** — Audio and Settings pages show restart notice when `_meta.config_applies_after === "restart"`; types and API responses include `_meta`.
- **B1.1** — test-ci builds web UI and copies to `radioshaq/radioshaq/web_ui` before pytest.
- **B1.2** — `tests/integration/test_web_ui_served.py`: GET / and asset reference asserted when web_ui present; tests skip when web_ui not built.
- **B1.3** — `radioshaq/README.md` subsection “Serving the web UI from the API (local)” with build/copy commands.
- **C1.1, C1.2, C1.3** — Websocket sends `placeholder: true` when no producer; docstring updated; VADVisualizer shows placeholder message (i18n).
- **C2.1, C2.2** — Lifespan wires `radio_rx_audio.set_metrics_callback(lambda d: setattr(app.state, "audio_metrics_latest", d))`; `AudioStreamProcessor.set_metrics_callback` and agent `set_metrics_callback` push real VAD/SNR/state when voice pipeline runs.
- **D1.1, D1.2, D1.3** — README and index use RadioShaq and VITE_RADIOSHAQ_*; `main.tsx` logs deprecation warning if VITE_SHAKODS_* is set.

**Note:** `POST /callsigns/register-from-audio` has parameter order `request, file, config=Depends(...), ...` so required params come before defaulted ones (fixes SyntaxError).

---

## Summary of Root Causes (Investigation)

| Issue | Root cause |
|-------|------------|
| Config PATCH does not affect agents | Overlays stored only in `request.app.state.*_override`. `get_config(request)` returns `app.state.config` (startup Config). Agents (orchestrator, radio_rx_audio, etc.) are created in **lifespan** with this config and hold references; they never read overrides. |
| Orchestrator/LLM overrides | `get_llm_config_for_role(config, role)` in factory uses `config.llm` and `config.llm_overrides` from the **Config** object (file/env). Runtime `app.state.llm_config_override` and `config_overrides_override` are only merged in GET/PATCH handlers; no code path applies them to the running orchestrator. |
| Web UI bundle lag | PyPI/nightly workflows build `web-interface` and `cp dist → radioshaq/radioshaq/web_ui` before building the wheel. Local runs serve from `radioshaq/radioshaq/web_ui` if present, which may be stale or from a different commit. No automated check that served bundle matches source for same commit. |
| VAD websocket placeholder | `app.state.audio_metrics_latest` is **never set** anywhere. The websocket handler sends either that dict or a heartbeat; no audio pipeline writes to it, so clients always see heartbeat/placeholder. |
| Frontend env mismatch | Code uses `VITE_RADIOSHAQ_API` / `VITE_RADIOSHAQ_TOKEN` (`radioshaqApi.ts`). README and index now use RadioShaq and VITE_RADIOSHAQ_*; deprecated VITE_SHAKODS_* triggers a console warning in main.tsx. |

---

## Projects and Activities

### Project A: Config overlay semantics (P0)

**Objective:** Make it explicit that config changes via API are “pending restart” and do not affect active agents until process restart.

#### Activity A1: Document and expose “restart required”

| # | Task | File(s) | Line-level / subtasks |
|---|------|---------|------------------------|
| A1.1 | Add a small config-semantics module or extend schema with a clear docstring that runtime overrides are app-state only and do not reconfigure agents. | `radioshaq/config/schema.py` or new `radioshaq/api/config_semantics.py` | Document in module/schema that overlay is for GET merge only; agents use startup config. |
| A1.2 | In GET responses for config (audio, llm, memory, overrides), add a top-level key e.g. `_meta: { "effective": "merged_with_overlay", "applies_to_runtime": false }` or `config_applies_after": "restart"`. | `radioshaq/api/routes/audio.py`, `radioshaq/api/routes/config_routes.py` | GET /config/audio: after building `out`, set `out["_meta"] = {"config_applies_after": "restart"}`. Same pattern for GET /config/llm, /config/memory, /config/overrides. |
| A1.3 | Document in OpenAPI/route docstrings that PATCH only updates runtime overlay and that a process restart is required for changes to affect orchestrator and agents. | `radioshaq/api/routes/audio.py`, `radioshaq/api/routes/config_routes.py` | PATCH docstrings: state “Runtime overlay only; does not persist to file. **Restart required** for changes to affect active agents (orchestrator, voice_rx, etc.).” |
| A1.4 | (Optional) Add a non-breaking response header e.g. `X-Config-Effective-After: restart` on PATCH responses. | Same routes | In each PATCH handler, before `return`, set `response.headers["X-Config-Effective-After"] = "restart"` (if using Response parameter or similar). |

#### Activity A2: UI indication (no “active” illusion)

| # | Task | File(s) | Line-level / subtasks |
|---|------|---------|------------------------|
| A2.1 | In the Settings and Audio config UI, show a short notice that config changes take effect after restart. | `radioshaq/web-interface/src/features/settings/SettingsPage.tsx`, `radioshaq/web-interface/src/features/audio/AudioConfigPage.tsx` | Add a small banner or paragraph: “Configuration changes are saved as runtime overrides and take effect after API restart.” Use existing i18n keys (add to en/fr/es if needed). |
| A2.2 | (Optional) Parse `_meta.config_applies_after` or header from GET and show “Restart required” only when overlay is present. | `radioshaq/web-interface/src/services/radioshaqApi.ts`, Settings/Audio pages | If GET returns `_meta`, display notice when `_meta.config_applies_after === "restart"`. |

---

### Project B: Frontend bundle parity (P1)

**Objective:** Guarantee that API-served `web_ui` is built from current `web-interface` for the same commit.

#### Activity B1: CI and build

| # | Task | File(s) | Line-level / subtasks |
|---|------|---------|------------------------|
| B1.1 | Ensure test or build job builds the web UI and copies to `radioshaq/radioshaq/web_ui` so the same artifact is used for “serve from API” tests. | `.github/workflows/test-ci.yml` (or main test workflow) | Add steps: checkout → setup Node → npm ci + npm run build in `radioshaq/web-interface` → mkdir -p radioshaq/radioshaq/web_ui && cp -r radioshaq/web-interface/dist/. radioshaq/radioshaq/web_ui/ . Run after unit tests or in a dedicated “integration” job that starts API and checks that / returns 200 and that a known route (e.g. /settings) is present in HTML or in a static asset. |
| B1.2 | Add a simple integration test: start API with bundled web_ui, GET / and optionally a key path (e.g. /settings); assert 200 and that response contains expected content (e.g. “Settings” or script chunk). | `radioshaq/tests/integration/` (new or existing) | New test module: build or use pre-built web_ui, create TestClient(app), GET "/", assert status 200; GET "/settings" or parse index.html for route presence. |
| B1.3 | Document in README or CONTRIBUTING that for “testing API-served UI” locally, run `npm run build` in web-interface then copy dist to `radioshaq/radioshaq/web_ui`. | `radioshaq/README.md` or `radioshaq/CONTRIBUTING.md` | Add subsection “Serving the web UI from the API” with the copy command and note that CI does this before packaging. |

---

### Project C: VAD metrics websocket (P1)

**Objective:** Either publish real metrics from the audio pipeline or clearly label the stream as placeholder/degraded.

#### Activity C1: Honest labeling when no producer

| # | Task | File(s) | Line-level / subtasks |
|---|------|---------|------------------------|
| C1.1 | In the websocket handler, when `audio_metrics_latest` is missing or not a dict, send a payload that explicitly marks the stream as placeholder (e.g. `type: "heartbeat"`, `degraded: true` or `placeholder: true`). | `radioshaq/radioshaq/api/routes/audio.py` | In `websocket_audio_metrics`, when `latest` is not a dict, set payload to include e.g. `"placeholder": True` and `"state": "idle"` so the UI can show “Live metrics unavailable (placeholder)”. |
| C1.2 | Update the WebSocket handler docstring to state that when the voice_rx pipeline does not set `app.state.audio_metrics_latest`, the stream sends placeholder heartbeats only. | `radioshaq/radioshaq/api/routes/audio.py` | Docstring: “When the voice_rx pipeline is wired, set app.state.audio_metrics_latest to a dict with vad_active, snr_db, state. Otherwise sends placeholder heartbeats; clients should treat as degraded/no live signal.” |
| C1.3 | In the frontend VAD visualizer, when receiving a message with `placeholder === true` or `type === "heartbeat"` and no recent real metrics, show a short “Placeholder / no live signal” or “Waiting for audio pipeline” message. | `radioshaq/web-interface/src/components/audio/VADVisualizer.tsx` | Parse WS message; if placeholder or heartbeat-only for N seconds, set local state “placeholder” and render a small notice instead of or in addition to the meter. |

#### Activity C2: (Optional) Wire real metrics from pipeline

| # | Task | File(s) | Line-level / subtasks |
|---|------|---------|------------------------|
| C2.1 | Pass `app` (or a setter for `app.state.audio_metrics_latest`) into the voice listener / radio_rx_audio path so the audio pipeline can update metrics. | `radioshaq/radioshaq/api/server.py`, `radioshaq/radioshaq/listener/voice_listener.py`, `radioshaq/radioshaq/specialized/radio_rx_audio.py` | Lifespan: when creating voice listener task, pass app (or a callback). In radio_rx_audio or stream_processor, when VAD/SNR/state change, call the setter to update `app.state.audio_metrics_latest`. |
| C2.2 | In AudioStreamProcessor or RadioAudioReceptionAgent, on segment start/end or periodic tick, set `app.state.audio_metrics_latest` to `{ "vad_active": bool, "snr_db": float|null, "state": str }`. | `radioshaq/radioshaq/audio/stream_processor.py` and/or `radioshaq/radioshaq/specialized/radio_rx_audio.py` | Where segment or VAD state is available, assign to the injected app-state setter so the websocket handler sends real values. |

---

### Project D: Frontend env and docs (P2)

**Objective:** Frontend README and index title match actual code; reduce misconfiguration risk.

#### Activity D1: Align env var names and docs

| # | Task | File(s) | Line-level / subtasks |
|---|------|---------|------------------------|
| D1.1 | Replace all references to deprecated `VITE_SHAKODS_*` in README with `VITE_RADIOSHAQ_API` and `VITE_RADIOSHAQ_TOKEN`. | `radioshaq/web-interface/README.md` | Use VITE_RADIOSHAQ_* and “RadioShaq API” throughout. |
| D1.2 | Update index.html title to “RadioShaq” or “RadioShaq Audio Config” so it matches the product name. | `radioshaq/web-interface/index.html` | Change `<title>` to “RadioShaq” or “RadioShaq Web Interface”. |
| D1.3 | (Optional) In the frontend, at startup, check for deprecated `VITE_SHAKODS_*` and log a console warning directing users to VITE_RADIOSHAQ_*. | `radioshaq/web-interface/src/main.tsx` or `radioshaqApi.ts` | If deprecated env is set, log: “Deprecated: use VITE_RADIOSHAQ_API / VITE_RADIOSHAQ_TOKEN”. |

---

## Implementation Order (Priority)

1. **P0 (Project A):** A1.2, A1.3, A2.1 — document restart-required in API responses and UI.
2. **P1 (Project D):** D1.1, D1.2 — frontend env docs and title (quick, low risk).
3. **P1 (Project C):** C1.1, C1.2, C1.3 — VAD placeholder labeling.
4. **P1 (Project B):** B1.1, B1.3 — CI build and copy web_ui; doc for local testing.
5. **P2:** A1.1, A1.4, A2.2, B1.2, C2.1–C2.2, D1.3 — optional refinements and real metrics wiring.

---

## Local testing: API-served UI

To test the API serving the same UI as the built bundle (e.g. before packaging):

```bash
cd radioshaq/web-interface && npm run build
mkdir -p ../radioshaq/web_ui && cp -r dist/. ../radioshaq/web_ui/
cd .. && uv run uvicorn radioshaq.api.server:app --reload
```

Then open http://localhost:8000. CI (test-ci, publish-pypi, publish-nightly) builds the web UI and copies to `radioshaq/radioshaq/web_ui` so the served artifact matches the source for the same commit.

---

## Acceptance Criteria (Recap)

- [x] API config GET responses indicate that overlay does not apply to runtime until restart (e.g. `_meta.config_applies_after` or equivalent).
- [x] API config PATCH docstrings and response header `X-Config-Effective-After: restart` “restart required”.
- [x] Settings and Audio UI show (data-driven from `_meta` when present) “Config takes effect after restart” notice.
- [x] CI builds web_ui from current web-interface; integration test verifies GET / and assets.
- [x] VAD websocket sends placeholder when no producer; real metrics wired when voice_rx runs; UI shows “Placeholder” or “No live signal” when appropriate.
- [x] Frontend README and index title use RadioShaq and VITE_RADIOSHAQ_*; D1.3 deprecated env warning in main.tsx.

---

## File-Level Index

| File | Activities |
|------|------------|
| `radioshaq/radioshaq/api/config_semantics.py` | A1.1 |
| `radioshaq/radioshaq/api/routes/audio.py` | A1.2, A1.3, A1.4, C1.1, C1.2 |
| `radioshaq/radioshaq/api/routes/config_routes.py` | A1.2, A1.3, A1.4 |
| `radioshaq/web-interface/src/features/audio/AudioConfigPage.tsx` | A2.1, A2.2 |
| `radioshaq/web-interface/src/features/settings/SettingsPage.tsx` | A2.1, A2.2 |
| `radioshaq/web-interface/README.md` | D1.1, B1.3 |
| `radioshaq/web-interface/index.html` | D1.2 |
| `radioshaq/web-interface/src/main.tsx` | D1.3 |
| `radioshaq/web-interface/src/components/audio/VADVisualizer.tsx` | C1.3 |
| `.github/workflows/test-ci.yml` | B1.1 |
| `radioshaq/README.md` | B1.3 |
| `radioshaq/tests/integration/test_web_ui_served.py` | B1.2 |
| `radioshaq/radioshaq/api/server.py` | C2.1 |
| `radioshaq/radioshaq/specialized/radio_rx_audio.py` | C2.2 |
| `radioshaq/radioshaq/audio/stream_processor.py` | C2.2 |
| `radioshaq/radioshaq/config/schema.py` | A1.1 docstring |
