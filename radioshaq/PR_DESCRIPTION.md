# PR: SMS/WhatsApp relay, emergency approval, contact preferences & testing improvements

## Summary

This PR adds **SMS and WhatsApp** support (Twilio), **emergency message approval** (operator-in-the-loop), **contact preferences and notify-on-relay** (per-channel opt-out), consolidates docs into a single **Response & compliance** page, and improves **CI and test reliability** (Postgres + migrations, test fixes).

**Latest commits:**
- **e542fd6** — adds sms and whatsapp + emergency contact
- **501ea54** — improves testing

---

## 1. SMS & WhatsApp (Twilio)

- **Config:** `twilio.account_sid`, `twilio.auth_token`, `twilio.from_number`, `twilio.whatsapp_from` (env `RADIOSHAQ_TWILIO__*` or YAML). Documented in [Configuration → Twilio](docs/configuration.md#twilio-sms--whatsapp).
- **Outbound:** Single outbound dispatcher sends via SMS/WhatsApp when the MessageBus consumer is enabled. SMS and WhatsApp agents use the same Twilio client; factory passes `client=` to `WhatsAppAgent` (fixed parameter name).
- **Setup:** `radioshaq setup --reconfigure` captures Twilio credentials (including auth token) before clearing secrets and writes them to `.env`; TTS reconfigure path now returns and persists the ElevenLabs API key.

---

## 2. Emergency approval (operator receive & transmit)

- **Purpose:** Operator **receives** emergency requests and **transmits** by approving; messages are queued until approval.
- **Config:** `RADIOSHAQ_EMERGENCY_CONTACT__ENABLED`, `RADIOSHAQ_EMERGENCY_CONTACT__REGIONS_ALLOWED`. See [Response & compliance](docs/response-compliance-and-monitoring.md).
- **API:**  
  - `GET /emergency/pending-count`, `GET /emergency/events`, `GET /emergency/events/stream` (SSE)  
  - `POST /emergency/events/{id}/approve`, `POST /emergency/events/{id}/reject`  
  - Relay with `emergency: true` and SMS/WhatsApp target queues for approval; API route returns `queued_for_approval` + `event_id` (no KeyError).
- **Web UI:** Emergency page (list pending, approve/reject, notes), polling + audio alert + browser notifications when pending count goes 0→N; i18n (EN/FR/ES).
- **Backend:** Coordination events stored in DB; `extra_data` updates use a new dict so SQLAlchemy persists audit fields (`approved_at`, `approved_by`, `sent_at`, `rejected_at`). Relay service and orchestrator relay tool receive full `Config` for `emergency_contact`.

---

## 3. Relay (radio + SMS/WhatsApp)

- **Relay route:** When `target_channel` is `sms` or `whatsapp`, `target_band` is not looked up in band plans (avoids KeyError); `target_freq` default 0 for non-radio.
- **Relay delivery worker:**  
  - Only **marks transcript delivered** when delivery actually succeeded: radio path after inject (+ optional TX); SMS/WhatsApp path only when `publish_outbound` returns true (avoids marking delivered when queue is full; failed items stay pending for retry).  
  - Notify-on-relay uses **per-channel opt-out** (see below).

---

## 4. Contact preferences & per-channel opt-out

- **API:** `GET/PATCH /callsigns/registered/{callsign}/contact-preferences` for notify-on-relay (SMS/WhatsApp phones, consent). New migration adds `notify_opt_out_at_sms` and `notify_opt_out_at_whatsapp`.
- **Opt-out:** `record_opt_out(callsign, channel)` and `record_opt_out_by_phone(phone, channel)` set only the **channel-specific** timestamp and clear that channel’s phone. No single global `notify_opt_out_at` for the worker.
- **Worker:** Notify-on-relay checks `notify_opt_out_at_sms` / `notify_opt_out_at_whatsapp` per channel; opting out of SMS does not block WhatsApp and vice versa.
- **Reversing opt-out:** `set_contact_preferences` clears `notify_opt_out_at_sms` when a non-empty SMS phone is set, and `notify_opt_out_at_whatsapp` when a non-empty WhatsApp phone is set.

---

## 5. Documentation

- **Single page:** “Response & compliance” ([response-compliance-and-monitoring.md](docs/response-compliance-and-monitoring.md)) covers: operator response (emergency, relay, contact preferences), compliance (radio restricted bands, band plans, country mapping; messaging consent/opt-out), and monitoring (Prometheus, health, WebSocket).
- **Removed:** Standalone `monitoring.md`; nav entry is now “Response & compliance”. [compliance-regulatory.md](docs/compliance-regulatory.md) is a short stub pointing to that page.
- **Configuration:** Twilio, TTS (ElevenLabs/Kokoro), ASR (voxtral/whisper/scribe), compliance/region table and `band_plan_region` documented in [Configuration](docs/configuration.md). API reference updated (GIS, emergency, metrics link).

---

## 6. CI & test harness

- **Workflows:** `test-ci`, `publish-nightly`, `publish-pypi` use a **Postgres service** (port 5434), **Wait for Postgres**, and **Run database migrations** before tests so the schema (including `notify_opt_out_at_sms` / `notify_opt_out_at_whatsapp`) is current.
- **Test client:** Any test using the `client` fixture triggers a **session-scoped migration run** (`_run_db_migrations`) so DB-using tests (e.g. callsigns) see the latest schema; if migrations fail (e.g. no Postgres), the session is skipped.
- **Test fixes:**  
  - Relay delivery notify test: assertion relaxed so multiple `get_contact_preferences` calls (worker loop) are allowed; still asserts at least one call with the destination callsign.  
  - Setup reconfigure mock: `_run_reconfigure_prompts` now returns 11 values (including `elevenlabs_key_reconfigure`); mock in `test_run_setup_reconfigure_mocked_merges_config` updated accordingly.

---

## 7. Other fixes and tweaks

- **Factory:** `WhatsAppAgent` is constructed with `client=sms_client` (not `twilio_client`) to match `WhatsAppAgent.__init__(client=..., from_number=...)`.
- **Setup:** Reconfigure TTS branch captures and returns the ElevenLabs key; caller uses it for `write_env(elevenlabs_api_key=...)` so the key is not lost.
- **Relay API:** When the service returns `queued_for_approval`, the route returns `ok`, `queued_for_approval`, `event_id`, `target_channel` instead of accessing missing keys.
- **Coordination event `extra_data`:** `update_coordination_event` uses `dict(row.extra_data or {})` so SQLAlchemy detects the change and persists audit fields.
- **Gitignore:** `.ruff_cache/`, `.tmp_build/`, `.tmp_pytest/`, `dist-investigate/`; cache/temp patterns; “RadioShaq” comment. **LICENSE.md** moved to repo root (GPL text only).

---

## Migration and compatibility

- **DB:** Run `alembic upgrade head` (or `uv run alembic-upgrade`) so `registered_callsigns` has `notify_opt_out_at_sms` and `notify_opt_out_at_whatsapp`. Existing rows keep `notify_opt_out_at`; legacy behaviour is “both channels opted out” when that timestamp is set and per-channel columns are null.
- **Config:** New options under `emergency_contact`, `twilio`, `tts`; existing configs remain valid. Optional: set `TEST_DATABASE_URL` for tests if not using default `postgresql+asyncpg://...@127.0.0.1:5434/radioshaq`.

---

## How to test

- **Unit + integration:** From `radioshaq/`: `uv run pytest tests/unit tests/integration -v`. Requires Postgres on port 5434 (or set `TEST_DATABASE_URL`) for tests that use the DB; migrations run automatically when the `client` fixture is used.
- **Emergency flow:** Enable emergency contact in config, create a relay with `emergency: true` and SMS/WhatsApp target; use Emergency page or API to approve/reject.
- **Notify-on-relay:** Set contact preferences with SMS/WhatsApp phones and `notify_on_relay: true`; trigger a radio relay for that callsign and confirm a short SMS/WhatsApp is sent (Twilio configured). Opt out via `POST /internal/opt-out` and confirm only that channel stops.

---

## Checklist

- [x] SMS/WhatsApp send via Twilio (config, agents, dispatcher)
- [x] Emergency approval API and Web UI (pending count, list, approve, reject, SSE)
- [x] Relay to SMS/WhatsApp and emergency queue; route handles `queued_for_approval`
- [x] Contact preferences API; per-channel opt-out and reversal in setup
- [x] Docs: Response & compliance page; Configuration (Twilio, TTS, ASR, compliance)
- [x] CI: Postgres service, migrations, web UI build (test-ci)
- [x] Tests: migration fixture, relay/setup/callsign assertions fixed
