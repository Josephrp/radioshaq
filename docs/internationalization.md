# Internationalization (i18n) and Voxtral Language Support

This document summarizes language support in the repository and how to internationalize it based on **Voxtral-supported languages**.

---

## 1. Voxtral-supported languages

Voxtral (Mistral’s speech model used for ASR in this repo) supports:

- **Transcription (Hugging Face / local):**  
  Strong performance in **English, Spanish, French, Portuguese, Hindi, German, Dutch, Italian**.  
  It also supports **automatic language detection** if the `language` argument is omitted.

- **Mistral API (Voxtral Mini Transcribe V2):**  
  **13 languages** with explicit codes:  
  **en**, **zh** (Chinese), **hi** (Hindi), **es** (Spanish), **ar** (Arabic), **fr** (French), **pt** (Portuguese), **ru** (Russian), **de** (German), **ja** (Japanese), **ko** (Korean), **it** (Italian), **nl** (Dutch).

- **Language parameter format:**  
  **ISO 639-1** two-letter codes (e.g. `en`, `es`, `fr`). Providing the language improves accuracy; omitting it uses auto-detection.

**Suggested canonical list for this repo (13 languages):**

| Code | Language  | Code | Language   |
|------|-----------|------|------------|
| `en` | English   | `ja` | Japanese   |
| `es` | Spanish   | `ko` | Korean     |
| `fr` | French    | `it` | Italian    |
| `de` | German    | `nl` | Dutch      |
| `pt` | Portuguese| `zh` | Chinese    |
| `hi` | Hindi     | `ru` | Russian    |
| `ar` | Arabic    |      |            |

---

## 2. Current state in the repository

### 2.1 ASR (Voxtral) and `asr_language`

- **Config:**  
  `audio.asr_language` exists in schema, YAML examples, and docs (default `en`).  
  Env override: `RADIOSHAQ_AUDIO__ASR_LANGUAGE`.

- **Where it’s used:**  
  - `radioshaq/radioshaq/specialized/radio_rx_audio.py` correctly uses `self.config.asr_language` when calling `transcribe_audio_voxtral(..., language=self.config.asr_language)`.

- **Where it’s not used (hardcoded `"en"`):**  
  - `radioshaq/radioshaq/api/routes/messages.py` — two calls to `transcribe_audio_voxtral(..., language="en")`.  
  - `radioshaq/radioshaq/api/routes/callsigns.py` — one call `transcribe_audio_voxtral(temp_path, language="en")`.  
  - `radioshaq/scripts/demo/inject_audio.py` — uses `language="en"` (script; could take CLI arg or env).

So the **voice RX pipeline** is already localized via config; the **HTTP API** (messages and callsigns) is not.

### 2.2 Web UI

- **No i18n framework:**  
  No react-i18next, react-intl, or similar. All copy is hardcoded English.

- **User-facing strings:**  
  In components such as `AudioConfigPage`, `MessagesPage`, `RadioPage`, `CallsignsPage`, `TranscriptsPage`, `SettingsPage`, `Layout`, etc. (labels, titles, errors, buttons).

- **Audio config:**  
  `AudioConfig` (and GET `/config/audio`) already includes `asr_language`. The UI could show an ASR language dropdown; no backend change required for that field.

### 2.3 API (REST)

- **Error and response messages:**  
  All in English (`detail="..."`, etc.).  
  No `Accept-Language` handling or locale-specific messages.

### 2.4 Documentation

- **MkDocs:**  
  `.github/mkdocs.yml` sets `language: en`.  
  Docs under `docs/` are English-only. MkDocs Material supports multiple locales if you add translations.

---

## 3. How to internationalize (aligned with Voxtral)

### 3.1 ASR language (quick win)

- **Use config everywhere:**  
  In `messages.py` and `callsigns.py`, get `config` (e.g. via existing `get_config(request)`) and pass `language=config.audio.asr_language` (or equivalent from your config shape) into every `transcribe_audio_voxtral` call instead of `language="en"`.

- **Optional validation:**  
  Add a small set of allowed ISO 639-1 codes (e.g. the 13 Voxtral languages above) in config or a shared constant; validate `asr_language` at load time or when updating audio config, and fall back to `"en"` or auto (e.g. `None`) if invalid.

- **Optional auto-detect:**  
  Allow `asr_language` to be empty or a sentinel (e.g. `"auto"`) and, in `radioshaq/radioshaq/audio/asr.py`, call `processor.apply_transcription_request(audio=..., model_id=...)` without `language` so Voxtral auto-detects.

### 3.2 Web UI (full i18n)

- **Add i18n library:**  
  e.g. `react-i18next` + `i18next` (and optionally `i18next-http-backend` if you load JSON from the server).

- **Scope and languages:**  
  Start with the 13 Voxtral languages as the supported UI locales. Add namespaces if needed (e.g. `common`, `audio`, `messages`, `callsigns`).

- **Workflow:**  
  1. Extract all user-visible strings into translation keys.  
  2. Add JSON (or similar) files per locale under e.g. `web-interface/src/locales/<code>.json`.  
  3. Set default locale from browser or user preference; allow language switcher in layout/settings.  
  4. Use `t('key')` (or equivalent) in components instead of literal strings.

- **ASR language selector:**  
  On the Audio config page, add a dropdown for “ASR language” with the 13 codes (and optionally “Auto”). Send updates via existing PATCH `/config/audio` with `asr_language`. No new API needed.

### 3.3 API messages (optional)

- **Keep English as default:**  
  Many APIs stay English-only; document that.

- **If you want localized API errors:**  
  - Read `Accept-Language` and choose a locale.  
  - Map error keys to translated strings (e.g. from JSON or gettext).  
  - Return translated `detail` (and possibly a stable `code`) so clients can still rely on codes.

### 3.4 Documentation

- **MkDocs Material:**  
  Use the theme’s [internationalization](https://squidfunk.github.io/mkdocs-material/setup/setting-up-language-switcher/) and add a `locales` structure (e.g. `en`, `es`, `fr`, …).  
  Duplicate or translate `docs/` content per locale.  
  Prioritize the same 13 languages if you want doc and ASR/UI languages aligned.

---

## 4. Implemented (en, fr, es)

- **Backend**
  - `radioshaq/radioshaq/constants.py`: `ASR_SUPPORTED_LANGUAGE_CODES = ("en", "fr", "es")`, `ASR_LANGUAGE_AUTO = "auto"`, `ASR_LANGUAGE_VALUES` for validation.
  - `radioshaq/radioshaq/config/schema.py`: `AudioConfig.asr_language` validated/normalized to one of en/fr/es/auto; default `"en"`.
  - `radioshaq/radioshaq/audio/asr.py`: When `language` is `"auto"`, Voxtral is called without a language (auto-detect). Otherwise uses the given ISO 639-1 code.
  - API routes (`messages.py`, `callsigns.py`) use `config.audio.asr_language` for all Voxtral transcription calls.
- **Web UI**
  - **i18n:** `react-i18next` + `i18next`; locale files under `radioshaq/web-interface/src/locales/` for **en**, **fr**, **es**.
  - **Language switcher:** In the main nav (Layout); preference stored in `localStorage` (`radioshaq_ui_lang`); fallback to browser language.
  - **ASR language:** Dropdown on the Audio config page with options Auto, English, Français, Español; PATCH `/config/audio` with `asr_language`.
  - All main pages and the license gate use `t()` for titles, labels, errors, and buttons (Audio, Callsigns, Messages, Transcripts, Radio, Settings, License).

## 5. Suggested further work

1. **UI:** Add more languages (e.g. remaining Voxtral 13) and translate remaining strings (e.g. ResponseModeSelector, ConfirmationQueue, ApiStatus).  
2. **API (optional):** Add Accept-Language and translated error messages if required.  
3. **Docs (optional):** Add MkDocs locales and translate key pages.

---

## 6. References

- [Hugging Face – Voxtral](https://huggingface.co/docs/transformers/main/en/model_doc/voxtral) (transcription mode, language param, auto-detect).  
- [Mistral – Audio transcription](https://docs.mistral.ai/capabilities/audio_transcription) (13 languages, Voxtral Mini Transcribe V2).  
- Config in this repo: `radioshaq/radioshaq/config/schema.py` (`AudioConfig.asr_language`), `docs/configuration.md`.
