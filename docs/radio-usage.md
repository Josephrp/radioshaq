# Radio Usage

RadioShaq can control real ham radios for voice, digital, and packet. This page explains how to connect and use physical hardware: main station rigs, portable rigs, remote receive-only stations, voice TX/RX, and optional SDR TX. The app talks to rigs via **Hamlib** (CAT), optionally to **FLDIGI** for digital modes and to a **KISS TNC** for packet; a separate **remote receiver** service can use an RTL-SDR to feed audio or data into your setup.

---

## Who this is for

- **Station principale** — One PC running the API and orchestrator, with a single rig (e.g. IC-7300) for both TX and RX. Typical for a fixed shack or demo.
- **Portable** — Laptop + radio (e.g. FT-450D, FT-817) in the field; same software, different rig model and port.
- **Remote receiver** — A listen-only node (e.g. Raspberry Pi + RTL-SDR) that streams to HQ or a field station; run with `radioshaq run-receiver` (same install as the main API).

In all cases you configure **one rig per RadioShaq instance** (one `rig_model`, one `port`). Digital and packet are optional add-ons.

---



## Example conversations (transcripts)

The following transcripts show what you can expect when operators interact with the station via the API or MessageBus (with `sender_id` / `callsign` set). Memory and first-contact logic are enabled so the station can welcome new callers and keep context across turns. Optional [radio-format](configuration.md#radio) wrapping can add call signs and “Over” / “K” to replies.

### First contact and short radio chat

Operator **W1ABC** sends messages via **POST /messages/process** with `sender_id: "W1ABC"`. No prior conversation; the station responds with a welcome and short, procedural replies.

| Turn | Speaker | Content |
|------|--------|--------|
| 1 | User (W1ABC) | W1ABC calling the field station. Anyone copy? |
| 2 | Station | W1ABC, this is the field station. Copy you. How can I help—relay, info, or something else? Over. |
| 3 | User | Just checking in. Can you do a quick signal report? |
| 4 | Station | I can’t measure your signal from here—I’m the station AI. If you have a human op nearby they can give you a report. I can relay messages or help with coordination. What do you need? Over. |
| 5 | User | Okay, maybe later. 73. |
| 6 | Station | 73 W1ABC. Standing by. Out. |

Use case: **API or MessageBus** with `sender_id`/`callsign`; memory enabled. The station uses first-contact hint and conversation history so later turns stay on topic.

---

### Whitelist request (gated access)

Operator **K5ABC** requests access to gated services (e.g. cross-band relay) via **POST /messages/whitelist-request** (text or audio). The orchestrator runs the whitelist flow; approved callers are registered and can use from-audio / inject-and-store.

| Turn | Speaker | Content |
|------|--------|--------|
| 1 | User | Hi, I’m K5ABC. I’d like to use the cross-band relay. |
| 2 | Station | You’re approved and whitelisted as K5ABC. You can use gated services like messaging between bands. |

Use case: **Whitelist** entry point; optional TTS so the reply can be played over the air. The station evaluates the request and, if approved, registers the callsign.

---

### Relay or coordination request

Operator asks to relay a message or schedule a contact. The station uses the **relay_message_between_bands** tool (or you can call **POST /messages/relay**). The message is stored; the recipient (e.g. W1ABC) polls `GET /transcripts?callsign=W1ABC&destination_only=true&band=40m` to retrieve it. Optional site config can enable inject or TX on the target band.

| Turn | Speaker | Content |
|------|--------|--------|
| 1 | User (W2XYZ) | W2XYZ. Need a relay to 40 meters for W1ABC, message: “Net at 1900 UTC on 7.185.” |
| 2 | Station | W2XYZ, copy. I’ll pass that to 40 meters for W1ABC: net at 1900 UTC on 7.185. Stand by. |
| 3 | Station | Relay sent. W1ABC can pick it up on transcripts. Anything else? Over. |

Use case: **API / MessageBus** with `sender_id`; the orchestrator calls the relay tool (or you POST /messages/relay). Delivery is poll-based unless the site enables relay_inject_target_band or relay_tx_target_band.

---

### Voice RX (listen and fixed ack)

When using the **voice RX** pipeline (audio in → ASR → trigger filter), the station only processes segments that match trigger phrases (and optionally `trigger_callsign`). The **reply** is currently a fixed acknowledgment, not an LLM-generated message.

| Over the air (user) | Station (reply) |
|---------------------|-----------------|
| “Field station, N0CALL, this is K5ABC, how copy?” | “Acknowledged: Field station N0CALL this is K5ABC how copy… Standing by.” |

Use case: **Voice RX** with `response_mode: auto_respond` (or confirm_first). For LLM-generated replies over the air, the voice RX path would need to call the orchestrator with the transcript and source callsign; that is not the default today.

---

### How to get these behaviors

- **First contact + chat:** Use **POST /messages/process** with `message` and `sender_id` (or `callsign`). Enable memory in config so the station loads context and first-contact hint when there’s no prior history.
- **Whitelist:** Use **POST /messages/whitelist-request** with text or audio; optionally send `callsign` in the body. Enable the bus consumer if replies go through the MessageBus.
- **MessageBus radio replies:** Control whether outbound bus replies transmit and whether they use TTS with `radio.radio_reply_tx_enabled` and `radio.radio_reply_use_tts`.
- **Radio-style call-out:** Set `radio.station_callsign` and optionally `radio.response_radio_format_enabled: true` so replies are wrapped as “STATION de CALLSIGN … Over.” See [Configuration](configuration.md) and the user-flow investigation in the repo for details.

---

## How the app talks to the rig

- **CAT (Hamlib)** — Frequency, mode, PTT, and status. You must set `radio.enabled: true`, `radio.rig_model` (Hamlib ID), and `radio.port` (e.g. `COM3` or `/dev/ttyUSB0`). Use `rigctl -l` to look up model numbers. Optionally run **rigctld** and set `radio.use_daemon: true` with `daemon_host` and `daemon_port`.
- **FLDIGI** — For digital modes: set `radio.fldigi_enabled: true` and `fldigi_host` / `fldigi_port`.
- **Packet** — KISS TNC: set `radio.packet_enabled: true` and `packet_callsign`, `packet_kiss_host`, `packet_kiss_port`.

---

## Main station (e.g. IC-7300)

A typical home or shack setup: one PC, one rig, API and orchestrator on the same machine.

- **Hardware:** Icom IC-7300 via USB (built-in CAT). Optionally a second rig on another port (then you’d run a second instance or switch config).
- **Config:** In YAML or env: `radio.enabled: true`, `radio.rig_model: 3073` (IC-7300), `radio.port: COM3` (Windows) or `/dev/ttyUSB0` (Linux). Use `RADIOSHAQ_RADIO__ENABLED=true`, `RADIOSHAQ_RADIO__RIG_MODEL=3073`, `RADIOSHAQ_RADIO__PORT=COM3` if using env.
- **Hamlib:** Install Hamlib; `rigctl -l` lists model IDs. To use the daemon: run `rigctld`, then set `radio.use_daemon: true`, `radio.daemon_host`, `radio.daemon_port`.

---

## Portable (FT-450D / FT-817)

Same RadioShaq app on a laptop, with a different rig and port.

- **Hardware:** Yaesu FT-450D with SCU-17 (USB CAT + sound), or FT-817ND with a USB-CAT cable.
- **Config:** `radio.rig_model: 127` (FT-450D) or `120` (FT-817); set `radio.port` to the correct COM or tty (e.g. `COM4`, `/dev/ttyUSB0`). Enable radio: `radio.enabled: true`.

---

## Remote receiver (RTL-SDR on Raspberry Pi)

A **listen-only** station: no TX, only RX. The main RadioShaq app usually runs elsewhere (field or HQ). Run the bundled receiver service on the Pi; it sends audio or transcripts to HQ via `POST /receiver/upload`.

- **Hardware:** Raspberry Pi, RTL-SDR USB dongle, antenna.
- **Install:** `pip install radioshaq` (optionally `pip install radioshaq[sdr]` for RTL-SDR or `radioshaq[hackrf]` for HackRF).
- **Config:** Set env: `JWT_SECRET`, `STATION_ID`, `HQ_URL`, and optionally `RTLSDR_INDEX` (or `HACKRF_INDEX`).
- **Run:** `radioshaq run-receiver` or `run-receiver` (default: host 0.0.0.0, port 8765).

The main RadioShaq API does not connect to the RTL-SDR directly; the receiver service does and forwards data to HQ.

---

## Voice TX: sending audio over the air

To send real audio (files or TTS) to the rig:

- **Cabling:** PC audio output (or a virtual cable) → rig line-in / data input. The rig’s CAT is still used for frequency, mode, and PTT.
- **Config:** Set `radio.audio_output_device` to the name or index of the sound device that feeds the rig. Optionally `radio.voice_use_tts: true` so the agent can generate speech when no audio file is provided.

The rest (band, mode, PTT) is handled by the radio_tx agent and PTT coordinator.

---

## Voice RX: hearing and responding on the air

When you want the agent to **listen** to the rig (and optionally respond), enable the voice_rx pipeline:

- Set `radio.audio_input_enabled: true` and configure the `audio.*` options: `input_device` (rig line-out), `input_sample_rate`, VAD, ASR, `response_mode` (listen_only, confirm_first, auto_respond, confirm_timeout), and `trigger_phrases`. See [Configuration](configuration.md) for the full list.

The pipeline captures audio, detects speech, transcribes with ASR, and only processes when a trigger phrase is detected. You can then choose to only transcribe, queue responses for approval, or auto-respond (with care).

---

## HackRF (optional SDR TX)

For SDR-based transmit (e.g. HackRF):

- Set `radio.sdr_tx_enabled: true` and `radio.sdr_tx_backend: hackrf`. Optionally `sdr_tx_device_index`, `sdr_tx_serial`, `sdr_tx_max_gain`. TX is off by default; band allowlist and restricted-band checks still apply.
- **Compliance:** Set `radio.tx_audit_log_path` to a file path to write a JSONL audit log of TX events.

---

## Quick reference

| Goal | What to set |
|------|-------------|
| IC-7300 at home | `radio.enabled: true`, `radio.rig_model: 3073`, `radio.port: COM3` or `/dev/ttyUSB0` |
| FT-450D portable | `radio.enabled: true`, `radio.rig_model: 127`, `radio.port: COM4` (or your tty) |
| FT-817 | `radio.rig_model: 120`, `radio.port: <your port>` |
| RTL-SDR receiver | `radioshaq run-receiver` with `JWT_SECRET`, `STATION_ID`, `HQ_URL`, `RTLSDR_INDEX` |
| Voice TX | `radio.audio_output_device` = device to rig; optional `radio.voice_use_tts: true`; for MessageBus replies also set `radio.radio_reply_use_tts` |
| Voice RX | `radio.audio_input_enabled: true` + `audio.*` (input_device, VAD, ASR, response_mode, trigger_phrases) |
| HackRF TX | `radio.sdr_tx_enabled: true`, `radio.sdr_tx_backend: hackrf`; optional `tx_audit_log_path` |

For every option and env var, see [Configuration](configuration.md).
