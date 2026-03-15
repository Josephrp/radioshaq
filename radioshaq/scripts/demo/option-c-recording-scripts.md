# Option C recording scripts (WAV → ASR → transcripts → inject/relay)

This doc proposes **spoken scripts + filenames** for the prerecorded WAV files you’ll place in a folder and upload via:

- `POST /messages/from-audio` (used by `scripts/demo/run_full_live_demo_option_c.py`)

Goal: exercise **whitelisting**, **transcript storage**, **inject**, **relay**, and **notify/SMS/WhatsApp** flows without requiring a second RF receiver.

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

## Callsign registry / whitelisting notes

Several endpoints enforce callsign allowlists:

- `/messages/from-audio` rejects if `source_callsign` (and destination if provided) is not allowed.
- `/messages/relay` rejects if `source_callsign` or `destination_callsign` are not allowed.

To make these recordings usable in a demo, register the callsigns you will use:

- `POST /callsigns/register` for `FLABC-1` and `F1XYZ-1`.

If `radio.callsign_registry_required=true` and you have **no** registered callsigns, most store/relay flows will be blocked by design.
