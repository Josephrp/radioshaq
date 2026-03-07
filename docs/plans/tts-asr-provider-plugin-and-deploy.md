# TTS and ASR Provider Plugin Plan (Kokoro, ElevenLabs, Scribe)

Complete plan to vendor Kokoro as a local TTS provider, add ElevenLabs Scribe as an API ASR option, and follow repository patterns (compliance-style plugin, config, setup/deploy). The `kokoro-demo/` folder will be removed; all functionality lives under `radioshaq/`.

---

## Repository patterns to follow

- **Compliance plugin** (`radioshaq/radioshaq/compliance_plugin/`): Protocol in `base.py`; backends in `backends/<name>.py` implementing the protocol; `__init__.py` imports all backends and calls `register_backend()` for each; public API: `get_backend(region_key)`, `get_backend_or_default()`, `get_band_plan_source_for_config()`. No dynamic discovery—explicit registration.
- **Config**: Pydantic schema in `radioshaq/config/schema.py`; nested sections (e.g. `radio`, `audio`); env overlay via `RADIOSHAQ_<SECTION>__<KEY>`; `config.example.yaml` and `docs/reference/.env.example` document options.
- **Setup**: `infrastructure/local/setup.sh` and `setup.ps1` from `radioshaq/`; `uv sync --extra dev --extra test` (extend to mention optional `audio`, `tts_kokoro`); default config created if missing; Docker Postgres, migrations, PM2.
- **Launch**: `radioshaq launch docker` / `radioshaq launch pm2` (CLI in `radioshaq/cli.py`); no separate process for TTS/ASR—optional backends load on first use or at startup.
- **Deploy**: AWS `infrastructure/aws/scripts/deploy.sh` and `deploy_lambda.sh`; Lambda installs `pip install --target STAGING .` (no extras by default—document that Lambda without audio/TTS extras has no Voxtral/Kokoro; ElevenLabs/Scribe are API-only and work with `ELEVENLABS_API_KEY`).

---

## Project 1: TTS plugin (protocol, backends, registry, config, call sites)

### Activity 1.1: TTS protocol and registry

| # | File | Task | Line-level subtasks |
|---|------|------|---------------------|
| 1.1.1 | `radioshaq/radioshaq/audio/tts_plugin/base.py` (new) | Define `TTSBackend` Protocol and result type | Add `Protocol` with method `synthesize(text: str, *, voice: str \| None, speed: float \| None, output_path: Path \| None, **kwargs) -> bytes \| None`; define `TTSResult` or use `bytes` + optional sample_rate; docstring for contract. |
| 1.1.2 | `radioshaq/radioshaq/audio/tts_plugin/__init__.py` (new) | Registry and public API | `_backends: dict[str, TTSBackend]`; `register_tts_backend(provider_id: str, backend: TTSBackend)`; `get_tts_backend(provider_id: str) -> TTSBackend \| None`; `synthesize_speech(text, provider_id, ..., output_path) -> bytes` that looks up backend and calls `synthesize`; export `TTSBackend`, `register_tts_backend`, `get_tts_backend`, `synthesize_speech`. |
| 1.1.3 | `radioshaq/radioshaq/audio/tts_plugin/backends/__init__.py` (new) | Backend package | Re-export `ElevenLabsTTSBackend`, `KokoroTTSBackend` (to be added). |

### Activity 1.2: ElevenLabs TTS backend

| # | File | Task | Line-level subtasks |
|---|------|------|---------------------|
| 1.2.1 | `radioshaq/radioshaq/audio/tts_plugin/backends/elevenlabs.py` (new) | Implement ElevenLabs backend | Class `ElevenLabsTTSBackend` implementing `TTSBackend`; move logic from current `tts.py` into `synthesize()` (voice_id, model_id, output_format from kwargs or backend defaults); read `api_key` from kwargs or `os.environ.get("ELEVENLABS_API_KEY")`; raise clear error if no key; return bytes (or write to output_path and return bytes). |
| 1.2.2 | `radioshaq/radioshaq/audio/tts.py` | Refactor to delegate to plugin | Replace body of `text_to_speech_elevenlabs` with call to `tts_plugin.synthesize_speech(..., provider_id="elevenlabs", ...)` or keep as thin wrapper that builds kwargs and calls `synthesize_speech`; preserve existing function signature for backward compatibility. |

### Activity 1.3: Kokoro TTS backend (local)

| # | File | Task | Line-level subtasks |
|---|------|------|---------------------|
| 1.3.1 | `radioshaq/radioshaq/audio/tts_plugin/backends/kokoro.py` (new) | Implement Kokoro backend | Class `KokoroTTSBackend` implementing `TTSBackend`; in `synthesize()`: optional kwargs `voice` (default e.g. `af_heart`), `lang_code` (default `a`), `speed` (default 1.0), `split_pattern` (default `r'\n+'`); use `from kokoro import KPipeline`; chunk text by split_pattern, loop `pipeline(text, voice=voice, speed=speed)`, collect 24 kHz numpy audio; concatenate; write WAV to output_path or temp and return bytes (or return bytes in a standard format); handle 510-token limit per chunk (KPipeline yields segments). Lazy-import kokoro and raise helpful error if not installed (`uv sync --extra tts_kokoro`). |
| 1.3.2 | `radioshaq/radioshaq/audio/tts_plugin/__init__.py` | Register Kokoro backend | Import `KokoroTTSBackend`; call `register_tts_backend("kokoro", KokoroTTSBackend())` inside a try/except ImportError so that without the extra the backend is simply not registered. |
| 1.3.3 | `radioshaq/pyproject.toml` | Add optional extra for Kokoro | Add `tts_kokoro = ["kokoro>=0.9.4", "soundfile>=0.12.1"]` (soundfile for WAV write); note: voice_tx already has soundfile; optional `misaki[en]` if needed for en-only install. |

### Activity 1.4: Register ElevenLabs in TTS plugin and wire config

| # | File | Task | Line-level subtasks |
|---|------|------|---------------------|
| 1.4.1 | `radioshaq/radioshaq/audio/tts_plugin/__init__.py` | Register ElevenLabs backend | Import `ElevenLabsTTSBackend`; `register_tts_backend("elevenlabs", ElevenLabsTTSBackend())` (no try/except—httpx is core). |
| 1.4.2 | `radioshaq/radioshaq/config/schema.py` | Add TTS config under `RadioConfig` or new section | Add fields: `tts_provider: str = "elevenlabs"` (or new `TTSConfig` with `provider`, `elevenlabs_voice_id`, `elevenlabs_model_id`, `elevenlabs_output_format`, `kokoro_voice`, `kokoro_lang_code`, `kokoro_speed`). Prefer nested `tts` section under `radio` or top-level `tts` for clarity. |
| 1.4.3 | `radioshaq/radioshaq/specialized/radio_tx.py` | Use TTS plugin and config | In `_transmit_voice`, replace direct `text_to_speech_elevenlabs(message, output_path=f.name)` with: resolve provider from config (e.g. `config.radio.tts_provider` or `config.tts.provider`), build kwargs from config (voice_id, model_id for ElevenLabs; voice, lang_code, speed for Kokoro); call `synthesize_speech(text=message, provider_id=..., output_path=f.name, **kwargs)`. Handle backend missing (e.g. kokoro not installed) with clear log and failure result. |
| 1.4.4 | `radioshaq/radioshaq/api/routes/transcripts.py` | Use TTS plugin and config | In `play_transcript_over_radio`, replace `text_to_speech_elevenlabs(text, output_path=temp_path)` with `synthesize_speech` using provider and options from request app config. |
| 1.4.5 | `radioshaq/radioshaq/api/routes/radio.py` | Use TTS plugin for send-tts | No change to endpoint body; internally when building task for radio_tx, TTS is invoked inside radio_tx with config; optional: extend `SendTTSBody` with `voice_id` / `provider` override and pass through to a one-off synthesize call if we want per-request override. |
| 1.4.6 | `radioshaq/scripts/demo/inject_audio.py` | Support `--tts kokoro` and config-driven provider | Add `"kokoro"` to `--tts` choices; if `args.tts == "kokoro"`: call `synthesize_speech(..., provider_id="kokoro", voice=args.tts_voice, ...)`; if `args.tts == "elevenlabs"`: keep current or use `synthesize_speech(..., provider_id="elevenlabs", ...)`. Add args for kokoro (e.g. `--tts-voice`, `--tts-lang-code`, `--tts-speed`) and pass to backend. |

---

## Project 2: ASR plugin (protocol, backends, registry, config, call sites, Scribe)

### Activity 2.1: ASR protocol and registry

| # | File | Task | Line-level subtasks |
|---|------|------|---------------------|
| 2.1.1 | `radioshaq/radioshaq/audio/asr_plugin/base.py` (new) | Define `ASRBackend` Protocol | Method `transcribe(audio_path: str \| Path, *, language: str \| None, **kwargs) -> str`; docstring. |
| 2.1.2 | `radioshaq/radioshaq/audio/asr_plugin/__init__.py` (new) | Registry and public API | `_backends: dict[str, ASRBackend]`; `register_asr_backend(model_id: str, backend: ASRBackend)`; `get_asr_backend(model_id: str) -> ASRBackend \| None`; `transcribe_audio(audio_path, model_id=..., language=..., **kwargs) -> str` that looks up backend and calls `transcribe`. |
| 2.1.3 | `radioshaq/radioshaq/audio/asr_plugin/backends/__init__.py` (new) | Backend package | Re-export `VoxtralASRBackend`, `WhisperASRBackend`, `ScribeASRBackend`. |

### Activity 2.2: Voxtral and Whisper backends

| # | File | Task | Line-level subtasks |
|---|------|------|---------------------|
| 2.2.1 | `radioshaq/radioshaq/audio/asr_plugin/backends/voxtral.py` (new) | Implement Voxtral backend | Class `VoxtralASRBackend` implementing `ASRBackend`; move logic from current `asr.py` `transcribe_audio_voxtral` into `transcribe(audio_path, language=...)`; same HF model id, PEFT, device_map. |
| 2.2.2 | `radioshaq/radioshaq/audio/asr_plugin/backends/whisper.py` (new) | Implement Whisper backend | Class `WhisperASRBackend` implementing `ASRBackend`; load model on first use (e.g. whisper.load_model("base")); call `model.transcribe(audio_path)`; return text; lazy-import whisper, raise if not installed. |
| 2.2.3 | `radioshaq/radioshaq/audio/asr.py` | Refactor to delegate to plugin | Replace body of `transcribe_audio_voxtral` with `asr_plugin.transcribe_audio(audio_path, model_id="voxtral", language=language)`; preserve function signature. |
| 2.2.4 | `radioshaq/radioshaq/audio/asr_plugin/__init__.py` | Register Voxtral and Whisper | `register_asr_backend("voxtral", VoxtralASRBackend())` in try/except (optional extra audio); `register_asr_backend("whisper", WhisperASRBackend())` in try/except (whisper optional). |

### Activity 2.3: ElevenLabs Scribe ASR backend (API)

| # | File | Task | Line-level subtasks |
|---|------|------|---------------------|
| 2.3.1 | `radioshaq/radioshaq/audio/asr_plugin/backends/scribe.py` (new) | Implement Scribe backend | Class `ScribeASRBackend` implementing `ASRBackend`; call ElevenLabs Speech-to-Text API (e.g. POST transcript endpoint; see ElevenLabs Scribe docs); read `api_key` from kwargs or `ELEVENLABS_API_KEY`; upload file or send URL, get transcript text; support language hint if API allows. |
| 2.3.2 | `radioshaq/radioshaq/audio/asr_plugin/__init__.py` | Register Scribe backend | `register_asr_backend("scribe", ScribeASRBackend())` (no heavy deps; httpx only). |
| 2.3.3 | `radioshaq/radioshaq/config/schema.py` | ASR model id includes scribe | Ensure `audio.asr_model` accepts `"scribe"` (string field; no enum change needed if it's free-form or extend allowed values in validator). |

### Activity 2.4: Wire ASR plugin into all call sites

| # | File | Task | Line-level subtasks |
|---|------|------|---------------------|
| 2.4.1 | `radioshaq/radioshaq/specialized/radio_rx_audio.py` | Use ASR plugin by model id | In `_transcribe_segment`: replace `if self.config.asr_model == "voxtral": ... else: whisper` with `backend = get_asr_backend(self.config.asr_model)`; if backend is None raise or fallback; call `transcribe_audio(temp_path, model_id=self.config.asr_model, language=self.config.asr_language)` (or run in executor for sync backend). Same in `_execute_transcribe_file` (around lines 609–617): use `transcribe_audio(..., model_id=self.config.asr_model, ...)`. |
| 2.4.2 | `radioshaq/radioshaq/api/routes/messages.py` | Use ASR plugin in from-audio and whitelist | In `message_from_audio` (lines 266–270): replace direct `transcribe_audio_voxtral` with `transcribe_audio(temp_path, model_id=config.audio.asr_model, language=asr_lang)`; handle backend not available (503). In whitelist audio path (lines 158–161): same replacement. |
| 2.4.3 | `radioshaq/radioshaq/api/routes/callsigns.py` | Use ASR plugin | In transcript-from-file handler (lines 144–146): replace `transcribe_audio_voxtral` with `transcribe_audio(temp_path, model_id=config.audio.asr_model, language=asr_lang)`. |
| 2.4.4 | `radioshaq/scripts/demo/inject_audio.py` | Use ASR plugin | In `transcribe_audio(audio_path, asr=...)`: map `asr` to `model_id` ("voxtral", "whisper", "scribe"); call `asr_plugin.transcribe_audio(audio_path, model_id=model_id, language="en")`; remove local `transcribe_audio_voxtral` / `transcribe_audio_whisper` or keep as thin wrappers. Add `--asr scribe` option. |

### Activity 2.5: ASR config and docs

| # | File | Task | Line-level subtasks |
|---|------|------|---------------------|
| 2.5.1 | `radioshaq/radioshaq/config/schema.py` | Document asr_model values | In `AudioConfig.asr_model` description, list: `voxtral` (local, default), `whisper` (local), `scribe` (ElevenLabs API). |
| 2.5.2 | `docs/configuration.md` | Document ASR and TTS options | Add subsection for TTS: provider (elevenlabs | kokoro), ElevenLabs voice/model/format, Kokoro voice/lang/speed; env ELEVENLABS_API_KEY when using elevenlabs or scribe. ASR: asr_model voxtral | whisper | scribe; scribe requires ELEVENLABS_API_KEY. |

---

## Project 3: Config schema and reference docs

### Activity 3.1: Schema and example config

| # | File | Task | Line-level subtasks |
|---|------|------|---------------------|
| 3.1.1 | `radioshaq/radioshaq/config/schema.py` | Add TTS config block | Add `class TTSConfig(BaseModel)` with `provider: Literal["elevenlabs", "kokoro"] = "elevenlabs"`; `elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"`; `elevenlabs_model_id: str = "eleven_multilingual_v2"`; `elevenlabs_output_format: str = "mp3_44100_128"`; `kokoro_voice: str = "af_heart"`; `kokoro_lang_code: str = "a"`; `kokoro_speed: float = 1.0`. Add `tts: TTSConfig \| None = None` to top-level Config (or under `radio` if preferred). |
| 3.1.2 | `radioshaq/config.example.yaml` | Add tts section | Under `radio:` or top-level, add commented `tts:` block with provider, elevenlabs_*, kokoro_* keys and short comments. |
| 3.1.3 | `docs/reference/.env.example` | TTS/ASR env vars | Ensure `ELEVENLABS_API_KEY` is documented for TTS (elevenlabs) and ASR (scribe); add any `RADIOSHAQ_TTS__*` or `RADIOSHAQ_AUDIO__ASR_MODEL` examples. |

---

## Project 4: Setup, deploy, and launch scripts

### Activity 4.1: Setup scripts (Bash and PowerShell)

| # | File | Task | Line-level subtasks |
|---|------|------|---------------------|
| 4.1.1 | `radioshaq/infrastructure/local/setup.sh` | Mention optional audio and TTS extras | After "RadioShaq and dev/test deps installed", add echo: "Optional: uv sync --extra audio (ASR: Voxtral, Whisper; Scribe uses API). Optional: uv sync --extra tts_kokoro (local TTS: Kokoro)." Or add optional prompt: "Install audio extras? [y/N]" and if yes run `uv sync --extra audio` (and optionally `--extra tts_kokoro`). |
| 4.1.2 | `radioshaq/infrastructure/local/setup.ps1` | Same for PowerShell | Mirror the optional extras message or prompt and `uv sync --extra audio` / `--extra tts_kokoro` when user opts in. |
| 4.1.3 | Default config in setup scripts | Add tts defaults to generated config | In the here-doc / string that writes default config.yaml, add `tts:` block with `provider: elevenlabs` and commented elevenlabs/kokoro keys so new installs have a template. |

### Activity 4.2: Deploy and Lambda

| # | File | Task | Line-level subtasks |
|---|------|------|---------------------|
| 4.2.1 | `radioshaq/infrastructure/aws/scripts/deploy_lambda.sh` | Document optional extras for Lambda | In comments or README in that dir: note that `pip install --target STAGING .` does not install optional extras; for Lambda with local ASR/TTS, install with `pip install --target STAGING ".[audio,tts_kokoro]"` (and ensure Lambda runtime has enough memory for Voxtral/Kokoro if used). Default Lambda path: no audio/tts_kokoro (API-only: ElevenLabs TTS + Scribe ASR with env ELEVENLABS_API_KEY). |
| 4.2.2 | `radioshaq/ecosystem.config.js` (if present) or `infrastructure/local/ecosystem.config.js` | Post-deploy install | If post-deploy uses `pip install -e .`, add note in comment that production may need `pip install -e ".[audio]"` or `".[audio,tts_kokoro]"` for full local stack; or keep as-is and document in docs. |

### Activity 4.3: Launch and CLI

| # | File | Task | Line-level subtasks |
|---|------|------|---------------------|
| 4.3.1 | `radioshaq/radioshaq/cli.py` | No change required | Launch commands do not need to start a separate TTS/ASR process; backends load on first use. Optionally in `radioshaq setup` flow: prompt for TTS provider (elevenlabs vs kokoro) and ASR model (voxtral, whisper, scribe) and write to config. |
| 4.3.2 | `radioshaq/README.md` and `docs/quick-start.md` | Document TTS/ASR and extras | State that voice TX can use ElevenLabs (set ELEVENLABS_API_KEY) or Kokoro (uv sync --extra tts_kokoro); ASR can be Voxtral/Whisper (uv sync --extra audio) or Scribe (API, ELEVENLABS_API_KEY). Point to configuration.md for tts.* and audio.asr_model. |

---

## Project 5: Remove kokoro-demo and finalize

### Activity 5.1: Delete kokoro-demo and reference Kokoro in radioshaq

| # | File | Task | Line-level subtasks |
|---|------|------|---------------------|
| 5.1.1 | Delete `kokoro-demo/` | Remove folder | Delete entire `kokoro-demo/` directory (app.py, en.txt, frankenstein5k.md, gatsby5k.md, packages.txt, requirements.txt). |
| 5.1.2 | `radioshaq/radioshaq/audio/tts_plugin/backends/kokoro.py` | Implement backend (see 1.3.1) | Ensure implementation uses same KPipeline/KModel usage as former kokoro-demo (lang codes, voice names, chunking); no dependency on deleted files; sample texts or docs can live in radioshaq tests or docs if needed. |
| 5.1.3 | Repo root docs or .github | Remove references to kokoro-demo | If any README or workflow references kokoro-demo, remove or update to point to radioshaq TTS (Kokoro backend). |

### Activity 5.2: Audio module public API

| # | File | Task | Line-level subtasks |
|---|------|------|---------------------|
| 5.2.1 | `radioshaq/radioshaq/audio/__init__.py` | Expose plugin APIs and keep compatibility | Add `synthesize_speech`, `transcribe_audio` (from plugins) to `__all__`; in `__getattr__`, add cases for `synthesize_speech` -> tts_plugin, `transcribe_audio` -> asr_plugin; keep `text_to_speech_elevenlabs` and `transcribe_audio_voxtral` as deprecated wrappers that delegate to plugins. |

### Activity 5.3: Tests and lint

| # | File | Task | Line-level subtasks |
|---|------|------|---------------------|
| 5.3.1 | `radioshaq/tests/unit/test_tts_plugin.py` (new) | Unit tests for TTS plugin | Test register/get backend; test synthesize_speech with mock backend; test elevenlabs backend with respx/httpx mock; test kokoro backend skipped when kokoro not installed. |
| 5.3.2 | `radioshaq/tests/unit/test_asr_plugin.py` (new) | Unit tests for ASR plugin | Test register/get backend; test transcribe_audio with mock backend; test voxtral/scribe with mocks. |
| 5.3.3 | Lint and type-check | Run ruff and mypy on new files | Fix any issues in `audio/tts_plugin/`, `audio/asr_plugin/`, and touched routes/specialized modules. |

---

## File summary (new vs modified)

**New files**

- `radioshaq/radioshaq/audio/tts_plugin/base.py`
- `radioshaq/radioshaq/audio/tts_plugin/__init__.py`
- `radioshaq/radioshaq/audio/tts_plugin/backends/__init__.py`
- `radioshaq/radioshaq/audio/tts_plugin/backends/elevenlabs.py`
- `radioshaq/radioshaq/audio/tts_plugin/backends/kokoro.py`
- `radioshaq/radioshaq/audio/asr_plugin/base.py`
- `radioshaq/radioshaq/audio/asr_plugin/__init__.py`
- `radioshaq/radioshaq/audio/asr_plugin/backends/__init__.py`
- `radioshaq/radioshaq/audio/asr_plugin/backends/voxtral.py`
- `radioshaq/radioshaq/audio/asr_plugin/backends/whisper.py`
- `radioshaq/radioshaq/audio/asr_plugin/backends/scribe.py`
- `radioshaq/tests/unit/test_tts_plugin.py`
- `radioshaq/tests/unit/test_asr_plugin.py`

**Modified files**

- `radioshaq/radioshaq/audio/tts.py` (delegate to plugin)
- `radioshaq/radioshaq/audio/asr.py` (delegate to plugin)
- `radioshaq/radioshaq/audio/__init__.py` (export plugin APIs, keep compat)
- `radioshaq/radioshaq/config/schema.py` (TTSConfig, tts section; asr_model docs)
- `radioshaq/radioshaq/specialized/radio_tx.py` (_transmit_voice: use synthesize_speech + config)
- `radioshaq/radioshaq/specialized/radio_rx_audio.py` (_transcribe_segment, _execute_transcribe_file: use transcribe_audio + asr_model)
- `radioshaq/radioshaq/api/routes/transcripts.py` (play: use synthesize_speech)
- `radioshaq/radioshaq/api/routes/messages.py` (from-audio + whitelist audio: use transcribe_audio)
- `radioshaq/radioshaq/api/routes/callsigns.py` (transcript from file: use transcribe_audio)
- `radioshaq/scripts/demo/inject_audio.py` (--tts kokoro, --asr scribe, use plugins)
- `radioshaq/config.example.yaml` (tts section)
- `radioshaq/pyproject.toml` (tts_kokoro extra)
- `radioshaq/infrastructure/local/setup.sh` (optional extras message/prompt)
- `radioshaq/infrastructure/local/setup.ps1` (same)
- `radioshaq/infrastructure/aws/scripts/deploy_lambda.sh` (comments for extras)
- `docs/configuration.md` (TTS and ASR options)
- `docs/reference/.env.example` (TTS/ASR env)
- `radioshaq/README.md`, `docs/quick-start.md` (TTS/ASR and extras)

**Deleted**

- `kokoro-demo/` (entire directory)

---

## Order of implementation (recommended)

1. **Project 3 (config)** – Add TTSConfig and tts section so other code can depend on it.
2. **Project 1 (TTS plugin)** – Protocol, ElevenLabs backend, registry, then Kokoro backend; refactor tts.py; wire radio_tx, transcripts, inject_audio.
3. **Project 2 (ASR plugin)** – Protocol, Voxtral/Whisper backends, Scribe backend, registry; refactor asr.py; wire radio_rx_audio, messages, callsigns, inject_audio.
4. **Project 5** – Delete kokoro-demo; audio __init__; tests; lint.
5. **Project 4** – Setup scripts, deploy comments, docs.

This plan keeps backward compatibility (existing function names delegate to plugins), follows the compliance plugin pattern, and ensures setup and deploy scripts and docs cover both API-only and local TTS/ASR options.
