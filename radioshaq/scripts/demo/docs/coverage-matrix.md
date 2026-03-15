# Live HackRF + LLM demo coverage matrix

This document maps **system capabilities** to **demo scenarios** so the suite exercises all major agents and radio pipelines (excluding Twilio). Use it to plan runs and verify coverage.

## Capabilities (rows)

| Capability | Agents / classes | Endpoints | External deps |
|------------|------------------|-----------|----------------|
| **HackRF RX path** | Remote receiver (HackRF backend), `stream_receiver_ws.py` | `POST /receiver/upload`, receiver WebSocket | HackRF hardware, pyhackrf2 |
| **Receiver upload store + inject** | Transcript storage, injection queue | `POST /receiver/upload` (HQ stores/injects) | Postgres, JWT |
| **Analog voice RX (radio_rx_audio)** | `RadioAudioReceptionAgent`, `TriggerFilter`, `ConfirmationManager` | Voice monitoring (capture → ASR → bus), optional API | ASR plugin, message bus |
| **Injection queue (no RF)** | `RadioReceptionAgent`, `get_injection_queue()` | `POST /inject/message`, `POST /messages/inject-and-store` | None (in-memory) |
| **From-audio ingestion** | ASR plugin, transcript storage, optional inject | `POST /messages/from-audio` | ASR (e.g. ElevenLabs Scribe), Postgres |
| **Relay (radio band translation)** | Relay service, transcript storage | `POST /messages/relay` (target_channel=radio) | Postgres, callsign registry |
| **Callsign registry / allowlist** | Callsign repo, config allowed_callsigns | `POST /callsigns/register`, `GET/PATCH /callsigns/registered/*` | Postgres (if DB-backed) |
| **Whitelist agent (LLM)** | `WhitelistAgent`, Judge, orchestrator | `POST /messages/whitelist-request` | LLM provider (Mistral/OpenAI/etc.) |
| **Orchestrator + Judge** | `AgentRegistry`, Judge, react loop, bridge | `POST /messages/process`, bus consumer | LLM, message bus |
| **HackRF TX (SDR)** | `RadioTransmissionAgent`, SDR transmitter | `POST /radio/send-audio`, `POST /radio/send-tts` | HackRF, voice_tx extra, TTS for send-tts |
| **TX compliance** | `is_tx_allowed`, `is_tx_spectrum_allowed`, compliance plugin | Used inside radio TX routes | Band plan config |
| **SchedulerAgent** | `SchedulerAgent` | Via bus / orchestrator tasks | Message bus, optional rig/TX |
| **GIS / propagation** | `GISAgent`, `PropagationAgent` | `GET /radio/propagation`, GIS routes | Optional DB/GIS |
| **SMS/WhatsApp relay** | `SMSAgent`, `WhatsAppAgent`, outbound dispatcher | `POST /messages/relay` (sms/whatsapp) | **Twilio (excluded from this suite)** |

## Demo scenarios (columns) and coverage

| Demo | Doc | Script | HackRF RX | Store+inject | radio_rx_audio | Injection queue | From-audio | Relay radio | Callsign reg | Whitelist LLM | Orchestrator/Judge | HackRF TX | Scheduler | GIS/Prop |
|------|-----|--------|-----------|--------------|----------------|-----------------|------------|-------------|--------------|---------------|--------------------|-----------|-----------|----------|
| **Full HackRF (existing)** | demo-hackrf-full.md | stream_receiver_ws, run_demo | ✓ | ✓ | — | — | — | ✓ | — | — | — | optional | — | optional |
| **Option C (no Twilio)** | demo-option-c-no-twilio.md | run_full_live_demo_option_c.py --no-twilio | — | ✓ | — | ✓ | ✓ | ✓ | ✓ | — | — | ✓ | — | optional |
| **Voice RX audio** | demo-voice-rx-audio.md | run_voice_rx_audio_demo.py | optional | ✓ | ✓ | — | — | — | — | — | ✓ | optional | — | — |
| **Radio RX injection** | demo-radio-rx-injection.md | run_radio_rx_injection_demo.py | — | — | — | ✓ | — | — | — | — | ✓ | — | — | — |
| **HackRF TX audio** | demo-hackrf-tx-audio.md | run_hackrf_tx_audio_demo.py | — | — | — | — | — | — | — | — | — | ✓ | — | — |
| **Voice-to-voice loop** | demo-voice-to-voice-loop.md | run_voice_to_voice_loop_demo.py | — | ✓ | ✓ | — | ✓ | — | — | — | ✓ | ✓ | — | — |
| **Whitelist + registry** | demo-whitelist-and-registry.md | run_whitelist_flow_demo.py | — | — | — | — | — | — | ✓ | ✓ | ✓ | — | — | — |
| **Orchestrator + Judge** | demo-orchestrator-judge.md | run_orchestrator_judge_demo.py | — | — | — | ✓ | — | — | — | — | ✓ | — | — | optional |
| **Scheduler** | demo-scheduler.md | run_scheduler_demo.py | — | — | — | optional | — | — | — | — | — | optional | ✓ | — |
| **GIS location + propagation** | demo-gis-location.md | run_gis_demo.py | — | — | — | — | — | — | — | — | optional | — | — | ✓ |

**Legend:** ✓ = exercised; — = not in scope; optional = used if configured.

## External services summary (no Twilio)

- **LLM**: One provider (Mistral, OpenAI, etc.) for orchestrator, whitelist, judge. **Live demos use real LLM** (no stub).
- **ASR**: e.g. ElevenLabs Scribe or local model for from-audio and voice_rx_audio.
- **TTS**: e.g. ElevenLabs or Kokoro for send-tts and voice-to-voice.
- **Postgres**: Transcript storage, callsign registry (recommended for full demos).
- **Message bus**: Required for orchestrator consumer, relay outbound, voice_rx_audio publish.
- **HackRF**: **Real hardware** for demos that use RX stream or SDR TX. Receiver needs `SDR_TYPE=hackrf`, pyhackrf2, and device attached; HQ TX needs `radio.sdr_tx_enabled=true` and attached HackRF. Use `--require-hardware` in demo scripts to fail fast if SDR TX is not configured.

## Must-have for v1

- Option C no-Twilio (from-audio, relay radio, inject-and-store, TX).
- Voice RX audio (trigger + ASR + response path).
- Radio RX injection (queue + band-aware monitor).
- HackRF TX audio (send-audio + compliance).
- Whitelist + registry (callsign registration + whitelist-request).
- Orchestrator + Judge (process + agent routing).
- Scheduler (one scheduled task execution).

All of the above are covered by the demo docs and `run_*_demo.py` scripts in this directory.
