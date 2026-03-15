# Option C recording scripts (WAV → ASR → transcripts → inject/relay)

This doc proposes **spoken scripts + filenames** for the prerecorded WAV files you’ll place in a folder and upload via:

- `POST /messages/from-audio` (used by `scripts/demo/run_full_live_demo_option_c.py` and `run_all_demos.py` with `--recordings-dir`)

Goal: exercise **whitelisting**, **transcript storage**, **inject**, **relay**, **orchestrator**, **scheduler**, **voice-to-voice**, **HackRF TX**, and **GIS (location, operators-nearby, propagation)** flows without requiring a second RF receiver. Recordings **00–05** are the core Option C set; **06–12** extend the suite for orchestrator, scheduler, voice-to-voice, trigger phrases, and second relay/TTS demos; **13–16** add geographical (set location, operators nearby, propagation request, relay with grid).

## Recording guidelines (to maximize ASR reliability)

- Speak **slowly** and **spell callsigns once** using phonetics (optional) after saying it normally.
- Prefer short sentences; avoid background noise.
- Put the **callsign first** in each recording.
- Use plain words: “relay”, “band”, “forty meters”, “two meters”, “message”, “over”.

## Suggested folder layout

Create a folder like:

`recordings/`

and put WAV files under it. The live demo script uploads **all** `*.wav` in the folder.

## Proposed recordings (filenames + what to say + what they test)

### 00_callsign_identity.wav

**Say:**

“FLABC-1. This is FLABC-1. Request acknowledged. Over.”

**Tests:** ASR baseline + transcript storage for a simple callsign.

**Expected transcript contains:** `FLABC-1`.

---

### 01_whitelist_request.wav

**Say:**

“FLABC-1. I am requesting to be whitelisted for cross band relay. I need to send emergency coordination messages. Over.”

**Tests:** content appropriate for `/messages/whitelist-request` (you can run that endpoint separately), plus ASR store/inject.

---

### 02_relay_message_40m_to_2m.wav

**Say:**

“FLABC-1 to F1XYZ-1. Relay this message from forty meters to two meters. The message is: meet at the trailhead at 1600 hours. Over.”

**Tests:** a realistic relay payload; you’ll pair this transcript text with `POST /messages/relay`.

---

### 03_notify_on_relay_opt_in.wav

**Say:**

“F1XYZ-1. Consent confirmed. Notify me on relay by SMS and WhatsApp. Over.”

**Tests:** prompts you to set contact preferences via `/callsigns/registered/{callsign}/contact-preferences`.

---

### 04_emergency_sms_relay.wav

**Say:**

“FLABC-1. Emergency message for F1XYZ-1. Please send by SMS. The message is: injured hiker, need assistance, coordinates follow. Over.”

**Tests:** relay-to-SMS path; also works with the emergency approval queue if enabled.

---

### 05_tx_payload.wav

**Say:**

“RadioShaq live demo. This audio file will be transmitted using HackRF SDR transmit. Over.”

**Tests:** `/radio/send-audio` end-to-end (HackRF TX through the deployed app).

---

## Additional recordings (extended demo suite)

These follow the same naming and style. Add them to the same `recordings/` folder; `run_all_demos.py` and `run_full_live_demo_option_c.py` upload all `*.wav` in sorted order, so they will be included automatically.

### 06_orchestrator_process.wav

**Say:**

“FLABC-1. Request for headquarters. What is the propagation from San Francisco to Los Angeles? Over.”

**Tests:** Transcript suitable for `POST /messages/process` (orchestrator / Judge). Exercises LLM routing and optional propagation/GIS agent. Use the transcript text in a follow-up process call or as a second from-audio that triggers the orchestrator.

**Expected transcript contains:** `FLABC-1`, “propagation”, “San Francisco”, “Los Angeles”.

---

### 07_scheduler_request.wav

**Say:**

“FLABC-1 to F1XYZ-1. Please schedule a call for tomorrow at 1600 UTC on forty meters. Over.”

**Tests:** Content appropriate for scheduler flow via `POST /messages/process`. Orchestrator may route to SchedulerAgent; transcript can be used to drive a process request that creates a coordination event.

**Expected transcript contains:** `FLABC-1`, `F1XYZ-1`, “schedule”, “1600”, “forty meters”.

---

### 08_voice_to_voice_reply.wav

**Say:**

“F1XYZ-1. Acknowledged. Standing by for your next traffic. Over.”

**Tests:** Short, clear phrase for voice-to-voice loop demos: from-audio → ASR → optional LLM reply → TTS → HackRF TX. Also useful as a generic “ack” transcript for relay or inject-and-store.

**Expected transcript contains:** `F1XYZ-1`, “Acknowledged”, “Standing by”.

---

### 09_relay_2m_to_70cm.wav

**Say:**

“FLABC-1 to F1XYZ-1. Relay from two meters to seventy centimeters. Message: net control, check in when ready. Over.”

**Tests:** Second relay scenario (2m → 70cm) for transcript variety and band-translation coverage. Pair with `POST /messages/relay` (source_band=2m, target_band=70cm).

**Expected transcript contains:** `FLABC-1`, `F1XYZ-1`, “two meters”, “seventy centimeters”, “net control”.

---

### 10_trigger_phrase_demo.wav

**Say:**

“Radioshaq. FLABC-1. This is a trigger phrase test. Over.”

**Tests:** When used with voice_rx_audio or from-audio, exercises trigger-phrase and optional audio-activation behaviour. “Radioshaq” and callsign first help ASR and trigger config (e.g. `trigger_phrases`, `trigger_callsign`).

**Expected transcript contains:** `Radioshaq` or “radioshaq”, `FLABC-1`.

---

### 11_pending_confirm.wav

**Say:**

“FLABC-1. Request human confirmation before sending. Message: trailhead at 1600. Over.”

**Tests:** Content that suggests confirm-first or confirm-timeout behaviour in voice_rx_audio (pending response, approve/reject via API). Good for demos that show `GET /api/v1/audio/pending` and approve flow.

**Expected transcript contains:** `FLABC-1`, “confirmation”, “trailhead”, “1600”.

---

### 12_tx_tts_demo.wav

**Say:**

“RadioShaq TTS demo. This script is for send-tts. Reply with a short acknowledgment on air. Over.”

**Tests:** Optional second TX payload; can be used for `POST /radio/send-tts` demos (message text from transcript or fixed). Keeps 05 for send-audio and this for send-tts narrative if you want two distinct WAVs.

**Expected transcript contains:** “TTS”, “send-tts”, “acknowledgment”.

---

## Geographical / GIS recordings

These transcripts exercise **operator location**, **operators nearby**, and **propagation**. Use them with `POST /messages/from-audio` then drive GIS flows via `POST /gis/location`, `GET /gis/operators-nearby`, `GET /radio/propagation`, or `POST /messages/process` (orchestrator can call GIS tools).

### 13_set_operator_location.wav

**Say:**

“FLABC-1. My position is 37.77 North, 122.42 West. Storing location for propagation. Over.”

**Tests:** Content suitable for setting operator location. Demo script or orchestrator can parse coords (or use fixed 37.77, -122.42) and call `POST /gis/location` for FLABC-1. Exercises location storage for later operators-nearby and propagation.

**Expected transcript contains:** `FLABC-1`, “position”, “37” or “122”, “location”, “propagation”.

---

### 14_operators_nearby.wav

**Say:**

“FLABC-1. Who is operating near me? Request operators within fifty kilometers. Over.”

**Tests:** Content for “operators nearby” flow. After storing at least one location (e.g. 13), call `GET /gis/operators-nearby` with that point and radius_meters=50000. Can be paired with `POST /messages/process` so the orchestrator uses the get_operator_location / operators_nearby tools.

**Expected transcript contains:** `FLABC-1`, “operating”, “near”, “fifty” or “kilometers”.

---

### 15_propagation_request.wav

**Say:**

“FLABC-1. What is the propagation from my location to headquarters? Over.”

**Tests:** Propagation query. If FLABC-1’s location is stored (13), use it as origin and a fixed HQ point as destination with `GET /radio/propagation`, or send the transcript to `POST /messages/process` so the orchestrator uses set_operator_location / propagation tools.

**Expected transcript contains:** `FLABC-1`, “propagation”, “location”, “headquarters”.

---

### 16_relay_with_location.wav

**Say:**

“FLABC-1 to F1XYZ-1. Relay from two meters. Message: meet at grid square EM78 at 1800 UTC. Over.”

**Tests:** Relay payload that includes a grid square (Maidenhead); useful for demos that combine relay with GIS (e.g. store location from grid, then relay). Pair with `POST /messages/relay` and optionally decode EM78 to lat/lon for `POST /gis/location`.

**Expected transcript contains:** `FLABC-1`, `F1XYZ-1`, “relay”, “two meters”, “grid”, “EM78”, “1800”.

---

## Summary table (all recordings)

| File | Primary use | Demo / endpoint |
|------|-------------|-----------------|
| 00_callsign_identity.wav | ASR + store | Option C, run_all_demos |
| 01_whitelist_request.wav | Whitelist content | whitelist-request, Option C |
| 02_relay_message_40m_to_2m.wav | Relay 40m→2m | relay (radio), Option C |
| 03_notify_on_relay_opt_in.wav | Contact prefs | contact-preferences (Twilio) |
| 04_emergency_sms_relay.wav | Relay to SMS | relay (sms), Option C + Twilio |
| 05_tx_payload.wav | HackRF send-audio | send-audio, run_hackrf_tx_audio_demo |
| 06_orchestrator_process.wav | Process / propagation | messages/process, orchestrator demo |
| 07_scheduler_request.wav | Schedule call | messages/process, scheduler demo |
| 08_voice_to_voice_reply.wav | Voice loop / ack | voice-to-voice, from-audio |
| 09_relay_2m_to_70cm.wav | Relay 2m→70cm | relay (radio) |
| 10_trigger_phrase_demo.wav | Trigger phrase | voice_rx_audio, trigger config |
| 11_pending_confirm.wav | Human confirm | audio/pending, confirm_first |
| 12_tx_tts_demo.wav | TTS narrative | send-tts |
| 13_set_operator_location.wav | Set location | POST /gis/location, run_gis_demo |
| 14_operators_nearby.wav | Operators nearby | GET /gis/operators-nearby, run_gis_demo |
| 15_propagation_request.wav | Propagation query | GET /radio/propagation, messages/process |
| 16_relay_with_location.wav | Relay + grid square | relay + optional GIS |

## Callsign registry / whitelisting notes

Several endpoints enforce callsign allowlists:

- `/messages/from-audio` rejects if `source_callsign` (and destination if provided) is not allowed.
- `/messages/relay` rejects if `source_callsign` or `destination_callsign` are not allowed.

To make these recordings usable in a demo, register the callsigns you will use:

- `POST /callsigns/register` for `FLABC-1` and `F1XYZ-1`.

If `radio.callsign_registry_required=true` and you have **no** registered callsigns, most store/relay flows will be blocked by design.
