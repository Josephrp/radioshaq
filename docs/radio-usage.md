# Radio Usage

RadioShaq can control real ham radios for voice, digital, and packet. This page explains how to connect and use physical hardware: main station rigs, portable rigs, remote receive-only stations, voice TX/RX, and optional SDR TX. The app talks to rigs via **Hamlib** (CAT), optionally to **FLDIGI** for digital modes and to a **KISS TNC** for packet; a separate **remote receiver** service can use an RTL-SDR to feed audio or data into your setup.

---

## Who this is for

- **Station principale** — One PC running the API and orchestrator, with a single rig (e.g. IC-7300) for both TX and RX. Typical for a fixed shack or demo.
- **Portable** — Laptop + radio (e.g. FT-450D, FT-817) in the field; same software, different rig model and port.
- **Remote receiver** — A listen-only node (e.g. Raspberry Pi + RTL-SDR) that streams to HQ or a field station; runs a separate receiver service, not the main RadioShaq API.

In all cases you configure **one rig per RadioShaq instance** (one `rig_model`, one `port`). Digital and packet are optional add-ons.

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

A **listen-only** station: no TX, only RX. The main RadioShaq app usually runs elsewhere (field or HQ). A separate **remote_receiver** service runs on the Pi and sends audio or transcripts to the main app.

- **Hardware:** Raspberry Pi, RTL-SDR USB dongle, antenna.
- **Software:** Run the `remote_receiver` service (from the `remote_receiver` directory in the monorepo). Configure env: `JWT_SECRET`, `STATION_ID`, `HQ_URL`, and optionally `RTLSDR_INDEX`.
- **Run:** e.g. `uv run uvicorn receiver.server:app --host 0.0.0.0 --port 8765` from the remote_receiver directory.

The main RadioShaq API does not connect to the RTL-SDR directly; the receiver service does and forwards data.

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
| RTL-SDR receiver | Run `remote_receiver` with `JWT_SECRET`, `STATION_ID`, `HQ_URL`, `RTLSDR_INDEX` |
| Voice TX | `radio.audio_output_device` = device to rig; optional `radio.voice_use_tts: true` |
| Voice RX | `radio.audio_input_enabled: true` + `audio.*` (input_device, VAD, ASR, response_mode, trigger_phrases) |
| HackRF TX | `radio.sdr_tx_enabled: true`, `radio.sdr_tx_backend: hackrf`; optional `tx_audit_log_path` |

For every option and env var, see [Configuration](configuration.md).
