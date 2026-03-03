# Connecting your station to SHAKODS

This guide explains how to connect your physical radios (station principale + portable) and optional remote receiver to the SHAKODS codebase for deployment.

---

## Overview

| Deployment | What runs where | Hardware connection |
|------------|------------------|---------------------|
| **Station principale (HF + VHF/UHF)** | SHAKODS API + orchestrator on one PC | IC-7300 (and optionally TYT TH-9800) via USB CAT |
| **Station portable** | SHAKODS on laptop; can switch rig | FT-450D or FT-817ND via USB (SCU-17 for FT-450D) |
| **Remote receiver** | `remote_receiver` on Raspberry Pi | RTL-SDR USB dongle |

The codebase talks to rigs via **Hamlib** (CAT): one `rig_model` + one `port` per rig. Digital modes use **FLDIGI** (optional). The remote receiver uses **pyrtlsdr** (RTL-SDR), no Hamlib.

---

## 1. Station principale — IC-7300 (+ optional TYT)

### Hardware

- **Icom IC-7300**: USB cable (built-in USB). Plug into the PC that runs SHAKODS.
- **TYT TH-9800**: If you want SHAKODS to control it, connect its programming/CAT cable (if supported) to a second USB port. *Note: TYT TH-9800 CAT support in Hamlib may be limited; check `rigctl -l`.*
- **LDG AT-100Pro II**: Between IC-7300 and antenna. No software connection; the IC-7300’s own tuner or the LDG is used from the radio front panel or via rig commands if the LDG is connected through the rig.

### Software on the PC

1. **Hamlib** (for CAT):
   - **Windows**: Install [Hamlib for Windows](https://github.com/Hamlib/Hamlib/releases) or use WSL and install `hamlib-utils`. Alternatively run `rigctld` in WSL and point SHAKODS at it (see “Using rigctld daemon” below).
   - **Linux**: `sudo apt install libhamlib-utils` (or build from source). Verify with `rigctl -l` (list rigs).
2. **Python**: SHAKODS uses `pyhamlib` when available; if not, you can use `use_daemon: true` and run `rigctld` separately.

### Config (station principale)

In `shakods/.shakods/config.yaml` (or your config file), set:

```yaml
mode: field
station_id: MAIN-01

radio:
  enabled: true
  rig_model: 3073    # Icom IC-7300 (Hamlib)
  port: /dev/ttyUSB0 # Linux: IC-7300 USB. Windows: COM3 (or whatever Device Manager shows)
  baudrate: 115200   # IC-7300 USB is typically 115200
  use_daemon: false  # true if you run rigctld yourself
  # If use_daemon: true:
  # daemon_host: localhost
  # daemon_port: 4532
  fldigi_enabled: false  # set true if you use FLDIGI for digital
  packet_enabled: false
```

**Windows:** Use the actual COM port, e.g. `port: COM3`. Find it in Device Manager → Ports (COM & LPT) after plugging the IC-7300.

**Hamlib rig model numbers** (run `rigctl -l` on your system for the full list):

| Rig | Hamlib model ID |
|-----|------------------|
| Icom IC-7300 | **3073** |
| Yaesu FT-450D | **127** |
| Yaesu FT-817 / FT-817ND | **120** |
| Yaesu FT-818 | **121** |
| TYT TH-9800 | Check `rigctl -l` (may not be listed) |

### Using rigctld daemon (optional)

If you prefer not to use pyhamlib on the same machine, run rigctld and point SHAKODS at it:

```bash
# Linux example: IC-7300 on /dev/ttyUSB0
rigctld -m 3073 -r /dev/ttyUSB0 -t 4532
```

Then in config:

```yaml
radio:
  enabled: true
  rig_model: 3073
  use_daemon: true
  daemon_host: localhost
  daemon_port: 4532
```

### Run SHAKODS (station principale)

From the **shakods** directory:

```bash
# Start API (and orchestrator) — radio is used by agents when tasks are dispatched
uv run python -m shakods.api.server
# Or with PM2: pm2 start infrastructure/local/pm2.config.js
```

API: `http://localhost:8000`. Use `/auth/token` to get a JWT, then call `/messages` or your workflows; the Radio TX agent will use the configured rig (IC-7300) when a transmission task is executed.

### Audio out to rig (voice TX with real audio)

To **send real audio** (TTS or file) over the radio, the PC must feed audio into the rig’s **line in** (or data interface, e.g. SCU-17):

- **Cabling:** Connect the PC’s audio output (or a virtual audio cable) to the rig’s “Line In” / “Data In” / “ACC” audio input. On IC-7300 this is often the rear 3.5 mm or the USB sound device; on FT-450D with SCU-17, use the SCU-17’s sound device.
- **Config:** Set `radio.audio_output_device` to the name or index of the sound device that goes to the rig (e.g. “CABLE Output (VB-Audio Virtual Cable)” or the device index). Optionally set `radio.voice_use_tts: true` so the agent will generate speech from the message when no file is provided.
- **Dependencies:** Install voice TX playback: `uv sync --extra voice_tx` (sounddevice, soundfile, pydub). See [AUDIO_TX_PLAN.md](AUDIO_TX_PLAN.md) for the full flow and agent tool.

---

## 2. Station portable — FT-450D or FT-817ND

### Hardware

- **Yaesu FT-450D**: Connect **SCU-17** (USB CAT + sound card) to the radio and to the laptop. One USB from SCU-17 to the PC.
- **Yaesu FT-817ND**: Same idea if you use a USB-CAT cable (e.g. SCU-17 or a generic USB–serial cable if the 817 has a serial CAT port).

### Config (portable)

Same structure as above, but rig and port for the portable rig:

**FT-450D:**

```yaml
mode: field
station_id: PORTABLE-01

radio:
  enabled: true
  rig_model: 127   # Yaesu FT-450D
  port: COM4      # Windows: check Device Manager. Linux: /dev/ttyUSB0 or /dev/ttyACM0
  baudrate: 38400  # typical for Yaesu
  fldigi_enabled: true   # if you run FLDIGI for digital modes
  fldigi_host: localhost
  fldigi_port: 7362
```

**FT-817ND:**

```yaml
radio:
  enabled: true
  rig_model: 120   # Yaesu FT-817
  port: COM4      # or /dev/ttyUSB0
  baudrate: 38400
```

Run SHAKODS the same way: `uv run python -m shakods.api.server` from the **shakods** directory (with config pointing at this rig).

---

## 3. Remote receiver (RTL-SDR on Raspberry Pi)

This is the **remote_receiver** project, not the main shakods app. It listens with an RTL-SDR and can send received data to the HQ API.

### Hardware

- Raspberry Pi (4 or Zero 2 W) with power and network.
- RTL-SDR dongle in a USB port.
- Antenna connected to the dongle.

### Software on the Pi

```bash
cd remote_receiver
uv sync
# Optional: uv sync --extra sdr   # if pyrtlsdr is an extra
```

### Environment variables

Create a `.env` or export before starting:

| Variable | Description | Example |
|----------|-------------|---------|
| `JWT_SECRET` | Same secret as HQ (so the receiver can authenticate) | `your-shared-secret` |
| `STATION_ID` | Unique ID for this receiver | `RECV-PI-01` |
| `HQ_URL` | SHAKODS HQ API base URL | `https://hq.example.com` or `http://192.168.1.10:8000` |
| `HQ_TOKEN` | Optional; JWT or API token for HQ uploads | (from `/auth/token`) |
| `RTLSDR_INDEX` | RTL-SDR device index if you have multiple USB SDRs | `0` |

### Run remote receiver

```bash
uv run uvicorn receiver.server:app --host 0.0.0.0 --port 8765
```

HQ must be reachable from the Pi at `HQ_URL`. The receiver will use the SDR and, if configured, upload signal data to the HQ API.

### Deploy script

From the repo root (or `remote_receiver`):

```bash
./remote_receiver/scripts/deploy_receiver.sh
```

Use this to automate install/run on the Pi (adjust the script for your Pi user/path if needed).

---

## 4. One config per deployment

- **Station principale**: One `config.yaml` (or env) with `rig_model: 3073`, `port` for the IC-7300, `station_id: MAIN-01`, `mode: field` (or `hq` if this PC is HQ).
- **Portable (FT-450D)**: Another config (or same file on the laptop) with `rig_model: 127`, `port` for the SCU-17, `station_id: PORTABLE-01`.
- **Portable (FT-817ND)**: Same idea with `rig_model: 120`.
- **Remote receiver**: No `config.yaml`; it uses env vars only (`JWT_SECRET`, `STATION_ID`, `HQ_URL`, `RTLSDR_INDEX`).

You can keep separate config files (e.g. `config.main.yaml`, `config.portable.yaml`) and select one when starting:

```bash
# Linux / WSL
SHAKODS_CONFIG=config.portable.yaml uv run python -m shakods.api.server

# Or copy the active one to .shakods/config.yaml before starting
```

---

## 5. Quick reference

| Goal | Where | Config / env |
|------|--------|----------------|
| IC-7300 at home | PC running SHAKODS | `radio.rig_model: 3073`, `radio.port: COM3` or `/dev/ttyUSB0`, `radio.enabled: true` |
| FT-450D in the field | Laptop | `radio.rig_model: 127`, `radio.port: COM4` (or Linux port), `radio.enabled: true` |
| FT-817ND in the field | Laptop | `radio.rig_model: 120`, `radio.port: ...`, `radio.enabled: true` |
| RTL-SDR receiver | Raspberry Pi | `remote_receiver` + `JWT_SECRET`, `STATION_ID`, `HQ_URL`, `RTLSDR_INDEX` |

Install Hamlib (and optionally run `rigctld`) on the machine that runs SHAKODS. Connect one rig per CAT port; use the correct `rig_model` and `port` for that rig. The same codebase runs on station principale and portable; only config and the connected radio change.

---

## HackRF compatibility

### HackRF transmit (SHAKODS main)

When **HackRF TX** is enabled in SHAKODS, the radio TX agent can transmit via HackRF (tone or I/Q) instead of, or in addition to, a CAT rig. **TX is off by default.**

**Config (shakods):**

```yaml
radio:
  sdr_tx_enabled: true    # Must be set explicitly to allow HackRF TX
  sdr_tx_backend: hackrf
  sdr_tx_device_index: 0
  sdr_tx_serial: null     # Or set to HackRF serial to pick one device
  sdr_tx_max_gain: 47     # 0–47 dB
  sdr_tx_allow_bands_only: true
  tx_audit_log_path: /path/to/tx_audit.jsonl   # Optional; logs every TX
  tx_allowed_bands_only: true
  restricted_bands_region: FCC
```

**Compliance:** Before any TX (CAT or SDR), the code checks `is_tx_allowed(frequency)`: the frequency must be inside an allowed band (e.g. from `BAND_PLANS`) and **not** in a restricted band (FCC §15.205). Every SDR TX is logged via `log_tx(...)`; if `tx_audit_log_path` is set, CAT TX is also logged. You are responsible for licensing and regulations; the software enforces band restrictions and audit logging.

**Dependencies:** HackRF TX requires **python_hackrf** and system **libhackrf >= 2024.02.1**. Install with `uv sync --extra hackrf` (if the shakods project adds a `hackrf` extra) or `pip install python-hackrf`. See [HACKRF_IMPLEMENTATION_PLAN.md](HACKRF_IMPLEMENTATION_PLAN.md).

---

### What is HackRF?

**HackRF One** is a USB 2.0 SDR that can both **receive and transmit** (half-duplex: one at a time) from **1 MHz to 6 GHz**. Main specs:

- **RX/TX**: 1 MHz–6 GHz; half-duplex (switch between RX and TX).
- **Sample rate**: 2–20 Msps (quadrature).
- **Resolution**: 8-bit I/Q.
- **TX power**: up to ~15 dBm (varies by band); **RX max input** about -5 dBm (do not exceed).
- **Software**: libhackrf (C); Python via **pyhackrf** (PyPI) or **SoapySDR** with SoapyHackRF.

So it covers HF and beyond (unlike RTL-SDR’s ~24–1766 MHz receive-only) and can transmit, but it is a different device and driver stack than RTL-SDR.

### Is HackRF compatible with this codebase?

**Yes.** The **remote_receiver** supports multiple SDR backends via env:

- **`SDR_TYPE=rtlsdr`** (default): RTL-SDR; set `RTLSDR_INDEX`, `RTLSDR_SAMPLE_RATE`.
- **`SDR_TYPE=hackrf`**: HackRF receive; set `HACKRF_INDEX` or `HACKRF_SERIAL`, optional `HACKRF_SAMPLE_RATE`. Requires `uv sync --extra hackrf` (python_hackrf).

The **shakods** main app can use HackRF for **transmit** when `radio.sdr_tx_enabled: true` and `sdr_tx_backend: hackrf`. TX is off by default and guarded by band allowlist and restricted-band checks; see [HACKRF_IMPLEMENTATION_PLAN.md](HACKRF_IMPLEMENTATION_PLAN.md).

### Remote receiver: SDR backends

To make HackRF **receive** with the existing remote_receiver design you’d add a second backend that fulfils the same `SDRInterface` contract:

1. **Same API**: `initialize()`, `set_frequency(frequency_hz)`, `receive(duration_seconds)` (async generator of `SignalSample`), `scan_frequency(...)`.
2. **Backend selection**: e.g. env `SDR_TYPE=rtlsdr` (default) or `SDR_TYPE=hackrf`; optional `HACKRF_SERIAL` or device index.
3. **HackRF implementation**: Use **pyhackrf** (or SoapySDR with SoapyHackRF) to open the device, set center frequency and sample rate, read I/Q in a loop (or callback), convert to `SignalSample` (e.g. compute strength from I/Q). Run that in an async loop so `receive()` can yield samples without blocking.

No change is required to the rest of remote_receiver (server, auth, HQ client); they only see `SDRInterface`. So HackRF is **compatible in principle** with the architecture; it just needs this extra backend and env switch.

**Transmit:** SHAKODS currently does **TX** via **Hamlib** (CAT) to a transceiver (IC-7300, FT-450D, etc.), not via an SDR. Using HackRF for TX would mean a new path: SDR TX block (modulate and send I/Q via HackRF). That would be a separate feature (and must respect regulations and licensing). For compliance requirements and a full implementation plan, see **[HACKRF_IMPLEMENTATION_PLAN.md](HACKRF_IMPLEMENTATION_PLAN.md)**.

### Summary

| Question | Answer |
|----------|--------|
| Can I use HackRF with remote_receiver? | **Yes.** Set `SDR_TYPE=hackrf`, install `uv sync --extra hackrf`. |
| Can HackRF be used for TX in SHAKODS? | **Yes**, when `radio.sdr_tx_enabled: true` and `sdr_tx_backend: hackrf`. TX is off by default; band and audit compliance apply. See [HACKRF_IMPLEMENTATION_PLAN.md](HACKRF_IMPLEMENTATION_PLAN.md). |
| Frequency coverage vs RTL-SDR? | HackRF: 1 MHz–6 GHz RX/TX. RTL-SDR: ~24–1766 MHz RX only (V3/V4 have HF via direct sampling or upconverter). |
