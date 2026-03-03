# HackRF implementation plan: compliance and code additions

This document covers **regulatory compliance** for HackRF use, **current code behaviour**, and a **step-by-step plan** to add full HackRF compatibility (receive and transmit) to the SHAKODS codebase.

---

## Compliance notice

**User responsibility:** You are responsible for licensing and regulatory compliance. The software enforces band restrictions (allowlist and restricted-band blocklist) and logs transmissions for accountability. When SDR TX is used, ensure you operate only where permitted (e.g. amateur bands with a valid licence).

---

## Part 1: Required compliance

### 1.1 Regulatory context

- **HackRF One** can TX and RX from 1 MHz to 6 GHz. It is **not** certified as a radio product; the manufacturer states that the user is responsible for legal use.
- **Transmitting** is only legal when:
  - **Amateur bands**: with a valid amateur licence and rules (callsign, power, mode, etc.).
  - **ISM / Part 15**: only where allowed, with power and modulation limits.
  - **Other bands**: only with explicit licence or authority.
- **FCC Part 15 restricted bands** (47 CFR §15.205): intentional radiation is **prohibited** in many bands (e.g. 0.09–0.11 MHz, 1.705–1.8 MHz, 108–121.94 MHz, 2200–2300 MHz, etc.). Transmitting there is illegal regardless of power.
- **EU / France**: similar principles (CEPT, national rules); restricted bands and licensing apply.

### 1.2 Compliance requirements for this codebase

To keep HackRF use legal and defensible, the **software** should:

| Requirement | Description |
|-------------|-------------|
| **1. TX off by default** | HackRF transmit must be **disabled** unless the user explicitly enables it (e.g. config or env). |
| **2. Band allowlist for TX** | Transmit only on frequencies that fall within **allowed** bands (e.g. amateur bands from `shakods.radio.bands.BAND_PLANS`). Reject TX requests outside these ranges. |
| **3. Restricted-band blocklist** | Do **not** transmit in known restricted bands (FCC §15.205 and/or CEPT). Reject even if inside an amateur band if it overlaps a restricted segment (if any). |
| **4. Power / level limits** | HackRF TX output is ~15 dBm max. Config should allow a **max TX gain** or “effective power” cap; document that the user must stay within licence limits. |
| **5. Audit logging** | Log every **transmit** event (timestamp, frequency, duration, mode, operator/callsign if available) for accountability and inspection. |
| **6. Clear documentation** | In UI and docs: user is responsible for licence and regulations; software only enforces band/restrictions and logging. |

**Receive-only** (e.g. remote_receiver with HackRF): no transmit compliance is needed for the RX path; only normal use of the device. Optional: document that listening on certain bands may be subject to local laws.

---

## Part 2: Current code implementation

### 2.1 Remote receiver (`remote_receiver/`)

| Component | Current behaviour | HackRF relevance |
|-----------|-------------------|-------------------|
| **`receiver/radio_interface.py`** | Defines `SDRInterface` and `SignalSample`. **Only RTL-SDR** is used: `import rtlsdr`, `RtlSdr(device_index)`, `center_freq`, `sample_rate`. `receive()` **does not read real I/Q** from the dongle; it yields placeholder `SignalSample` with `strength_db=-100.0` in a time loop. `scan_frequency` calls `set_frequency` and `receive()`. | Need a second backend (HackRF) implementing the same interface. For HackRF, `receive()` must **read I/Q** (e.g. via pyhackrf or SoapySDR), compute power/strength, and yield real `SignalSample`s. |
| **`receiver/server.py`** | `ReceiverService.from_env()` builds `SDRInterface(device_index=int(RTLSDR_INDEX))`. No other SDR type. Stream and upload use `radio.set_frequency`, `radio.receive()`, `_queue_for_hq(signal)`. | Need to choose backend from env (e.g. `SDR_TYPE=rtlsdr` or `hackrf`) and pass backend-specific args (e.g. `HACKRF_SERIAL` or index). |
| **`receiver/signal_processor.py`** | Stub: `is_interesting(sample, threshold_db)`, `decode_digital(sample)`. No change needed for HackRF. | None. |
| **`pyproject.toml`** | Optional deps: `sdr = ["pyrtlsdr"]`. | Add optional `hackrf` (e.g. `pyhackrf` or `SoapySDR`) and document. |

**Gap:** Single hard-coded RTL-SDR backend; no abstraction over “SDR type”. No real I/Q streaming in `receive()` even for RTL-SDR.

### 2.2 SHAKODS main (`shakods/`)

| Component | Current behaviour | HackRF relevance |
|-----------|-------------------|-------------------|
| **`radio/cat_control.py`** | Hamlib CAT: `set_frequency`, `set_ptt`, `set_mode`, `get_state`. Used for **transmit** via rig. | Remains for IC-7300, FT-450D, etc. HackRF TX is a **separate path** (no CAT). |
| **`radio/rig_manager.py`** | Wraps one or more `HamlibCATControl` rigs; `set_frequency`, `set_ptt`, `set_mode`, `get_state`. | TX today is **only** via RigManager (CAT). For HackRF TX we need either a second “transmitter” abstraction or extend the agent to use “SDR transmitter” when configured. |
| **`radio/bands.py`** | `BAND_PLANS` (160m–70cm), `get_band_for_frequency()`, `get_band_plan()`, `is_frequency_in_band()`. **Not used** to guard TX in `radio_tx.py`. | **Must** be used for compliance: only allow TX on frequencies in `BAND_PLANS` (and not in restricted list). |
| **`specialized/radio_tx.py`** | `RadioTransmissionAgent`: voice (PTT + rig), digital (FLDIGI), packet (KISS). All go through `rig_manager` for frequency/mode; no frequency check. | Add optional **SDR TX path**: when `sdr_tx` is configured (HackRF), call a new “SDR transmitter” module that modulates and sends I/Q, **after** compliance checks. |
| **`config/schema.py`** | `RadioConfig`: `enabled`, `rig_model`, `port`, `max_power_watts`, `tx_enabled`, `rx_enabled`. No SDR/HackRF options. | Add `sdr_tx_enabled`, `sdr_tx_backend` (e.g. `hackrf`), `sdr_tx_max_gain`, optional serial/index. Optionally `sdr_tx_allow_bands` (default: from BAND_PLANS). |
| **Orchestrator / registry** | Agents registered by name/capability; `RadioTransmissionAgent` gets `rig_manager`, `digital_modes`, `packet_radio` in constructor. No transmitter abstraction. | Where orchestrator/agents are built, inject optional `sdr_transmitter` (HackRF backend). Agent uses it when task requests SDR TX or when only SDR TX is configured. |

**Gap:** No SDR TX path; no frequency/band enforcement before TX; no HackRF-specific config.

### 2.3 Summary of code gaps

1. **remote_receiver**: RTL-SDR only; `receive()` is a stub (no real I/Q). Need backend abstraction + HackRF backend + real I/Q for both.
2. **shakods**: TX is CAT-only; no band/restricted check; no SDR TX module; no HackRF config.
3. **Compliance**: No central “allowed to transmit on this frequency?” or “restricted band?” check; no TX audit log.

---

## Part 2.5: HackRF library comparison (which enables transmit and what we need)

We need: **RX** (tune, read I/Q or power, stream), **TX** (tune, send **custom** I/Q e.g. tone/CW/modulated), **gains**, **frequency 1 MHz–6 GHz**, **sample rate 2–20 Msps**. Below is which libraries actually support this.

| Library | PyPI / install | Receive | Transmit | Custom I/Q for TX? | Notes |
|--------|----------------|---------|----------|--------------------|-------|
| **pyhackrf** (dressel) | `pip install pyhackrf` | Yes: `read_samples()`, `start_rx(callback)` | **No** | N/A | In source, `hackrf_start_tx` / `hackrf_stop_tx` are **commented out**; only RX is exposed. |
| **pyhackrf2** (eizemazal) | `pip install pyhackrf2` | Yes: `read_samples()`, `start_rx(pipe_function)`, sweep | Yes: `start_tx()` / `stop_tx()` | **Replay only** | TX **replays** from internal buffer filled by a prior `start_rx()`. No documented API to **write** custom I/Q into the buffer for TX. Good for RX and "record then replay"; not for generating tones/CW/modulation. |
| **python_hackrf** (GvozdevLeonid) | `pip install python-hackrf` | Yes (full libhackrf) | Yes | **Yes (callback)** | TX is **callback-based**: callback receives `hackrf_transfer` (buffer, length); you **fill the buffer** with I/Q (int8 interleaved) and return. So we can feed **custom** I/Q (tone, CW, modulated). Requires **libhackrf 2024.02.1+**. |
| **SoapySDR + SoapyHackRF** | Build from source (no pip) | Yes: `setupStream(RX)`, `readStream()` | Yes: `setupStream(TX)`, `writeStream()` | **Yes** | Full C++ API in Python: `writeStream(stream, [numpy_array], num_samples)` to send any I/Q. Requires building SoapySDR and SoapyHackRF; not a single `pip install`. Best flexibility; heavier install. |

### Operations we need vs library support

| Operation | pyhackrf | pyhackrf2 | python_hackrf | SoapySDR |
|-----------|----------|-----------|---------------|----------|
| RX: init, set freq, set sample rate | Yes | Yes | Yes | Yes |
| RX: read I/Q (sync or callback) | Yes | Yes | Yes | Yes |
| RX: gains (LNA, VGA) | Yes | Yes | Yes | Yes |
| TX: init, set freq, set sample rate | No (commented out) | Yes | Yes | Yes |
| TX: send **custom** I/Q (tone, CW, etc.) | No | No (replay only) | **Yes (callback)** | **Yes (writeStream)** |
| TX: gains (TXVGA) | No | Yes | Yes | Yes |
| Enumerate / open by serial | Yes | Yes | Yes | Yes |
| Pip-installable | Yes | Yes | Yes | No (build from source) |

### Recommendation for this codebase

- **Receive (remote_receiver):** Use **pyhackrf2** or **python_hackrf** for simplicity and pip install. Both support `read_samples()` or callback RX; pyhackrf2 has a simple `read_samples()` and async `start_rx(pipe_function)`.
- **Transmit (shakods SDR TX path):** Use **python_hackrf** or **SoapySDR** so we can feed **custom** I/Q (tone, CW, or modulated). **python_hackrf** is preferable if we want a single pip-installable stack; **SoapySDR** if we already depend on it or need multi-SDR support.
- **Single-library option:** Use **python_hackrf** for both RX and TX: one dependency, pip install, and it supports custom TX via the callback. Requirement: system **libhackrf >= 2024.02.1** (0.9).

---

## Part 2.6: Library reference documentation (request before implementing)

Before implementing Phase 2 (backends) and Phase 3 (SDR TX), use the following references.

### python_hackrf (GvozdevLeonid) – recommended for RX + TX

| What | Where | Notes |
|------|--------|--------|
| **README / install** | [python_hackrf GitHub](https://github.com/GvozdevLeonid/python_hackrf) (raw [README](https://raw.githubusercontent.com/GvozdevLeonid/python_hackrf/master/README.md)) | Requires libhackrf 2024.02.1+; `pip install git+https://github.com/GvozdevLeonid/python_hackrf.git`; Windows needs HackRF in `C:\Program Files\HackRF` or env vars. |
| **CLI transfer** | Same README – “python_hackrf transfer” | RX/TX file; `-r` receive, `-t` transmit; `-f` freq Hz; `-s` sample rate MHz (2–20); `-x` TX VGA gain 0–47; data as **complex64** in files. |
| **Programmatic API** | Library ports “all functions from libhackrf” | Use **libhackrf** API below for function names; Python bindings expose the same (e.g. open by serial/index, set_freq, set_sample_rate, start_rx/start_tx with callback). |
| **TX callback buffer** | libhackrf `hackrf_transfer` (see below) | TX callback receives `transfer->buffer`; fill with **int8 interleaved I/Q** (I, Q, I, Q, …); `buffer_length` / `valid_length` in bytes. |

### libhackrf (C API – maps to python_hackrf)

| What | Where | Notes |
|------|--------|--------|
| **API reference** | [libHackRF-API.md (hackrf-wiki)](https://github.com/dodgymike/hackrf-wiki/blob/master/libHackRF-API.md), [raw](https://raw.githubusercontent.com/dodgymike/hackrf-wiki/master/libHackRF-API.md) | Init: `hackrf_init`, `hackrf_open` / `hackrf_open_by_serial` / `hackrf_device_list_open`. Radio: `hackrf_set_freq`, `hackrf_set_sample_rate`, `hackrf_set_lna_gain`, `hackrf_set_vga_gain`, `hackrf_set_txvga_gain` (0–47). RX: `hackrf_start_rx(device, callback, rx_ctx)`, `hackrf_stop_rx`. TX: `hackrf_start_tx(device, callback, tx_ctx)`, `hackrf_stop_tx`. |
| **Callback struct** | Same doc – “Data Structures” | `hackrf_transfer`: `device`, `buffer` (uint8_t*), `buffer_length`, `valid_length`, `rx_ctx`, `tx_ctx`. Callback: `int (*hackrf_sample_block_cb_fn)(hackrf_transfer* transfer)`. |
| **Buffer format** | [HackRF buffer format](https://hackrf-dev.greatscottgadgets.narkive.com/29i7Kivv) / hackrf_transfer.c | **int8 signed interleaved I/Q** (I, Q, I, Q, …). TX: fill buffer with same format. |

### pyrtlsdr (RTL-SDR backend – Phase 2.2)

| What | Where | Notes |
|------|--------|--------|
| **API** | [pyrtlsdr docs](https://pyrtlsdr.readthedocs.io/) | `RtlSdr(device_index)`, `center_freq`, `sample_rate`, `read_samples(num_samples)` (returns numpy array); use for real I/Q in `receive()`. |

### Optional: pyhackrf2 (alternative RX-only)

| What | Where | Notes |
|------|--------|--------|
| **API** | [pyhackrf2 PyPI](https://pypi.org/project/pyhackrf2/) | `start_rx(pipe_function=...)`, `read_samples()`; TX is replay-only (no custom I/Q), so not suitable for Phase 3 TX. |

### FCC §15.205 restricted bands (for Phase 1.1)

Use the official table for `is_restricted(freq_hz)`: [47 CFR § 15.205](https://www.ecfr.gov/current/title-47/chapter-I/subchapter-A/part-15/subpart-C/section-15.205) (ecfr.gov). Ranges run from 0.090–0.110 MHz through >38.6 GHz; store as `(low_hz, high_hz)` and reject TX if frequency falls in any range.

### What to request if still needed

- **python_hackrf**: If the Python bindings for `hackrf_start_rx` / `hackrf_start_tx` and the callback signature (how `hackrf_transfer` is passed into Python) are not obvious from the repo, open the package source (e.g. `hackrf.pyx` or `.py` wrappers) and/or the [PySDR HackRF tutorial](https://pysdr.org/content/hackrf.html) for usage.

---

## Part 3: Implementation plan (complete HackRF compatibility)

### Phase 1: Compliance layer (shakods)

**Goal:** Reusable checks and audit log so that **any** TX path (CAT or SDR) can be guarded.

| Step | Task | Details |
|------|------|---------|
| 1.1 | **Restricted bands list** | Add `shakods/radio/compliance.py`. Define a list of (low_hz, high_hz) for FCC §15.205 restricted bands (and optionally CEPT) that **must not** be used for TX. Provide `is_restricted(freq_hz) -> bool`. |
| 1.2 | **TX allowlist** | In `compliance.py`, add `is_tx_allowed(freq_hz, band_plan_source=BAND_PLANS) -> bool`: True only if frequency is inside an allowed band (e.g. BAND_PLANS) and **not** in restricted list. Optionally take a config flag “allow_tx_only_amateur_bands” (default True). |
| 1.3 | **TX audit log** | In `compliance.py`, add `log_tx(timestamp, frequency_hz, duration_sec, mode, operator_id, rig_or_sdr)` writing to a file or structured logger (e.g. JSON lines). Config: path or “logger only”. |
| 1.4 | **Config** | In `RadioConfig`, add `tx_audit_log_path: str | None`, `tx_allowed_bands_only: bool = True`. Optionally `restricted_bands_region: str = "FCC"` (for future CEPT). |

**Deliverable:** Any code that is about to TX can call `is_tx_allowed(freq)`, `is_restricted(freq)`, and `log_tx(...)`.

---

### Phase 2: Remote receiver – SDR backend abstraction

**Goal:** One interface, multiple backends (RTL-SDR, HackRF).

| Step | Task | Details |
|------|------|---------|
| 2.1 | **Abstract base** | In `remote_receiver/receiver/radio_interface.py`, introduce `SDRBackend` protocol or ABC: `initialize()`, `set_frequency(hz)`, `receive(duration_sec)` (async generator of `SignalSample`), `close()`. Keep `SignalSample` and `is_interesting` as-is. |
| 2.2 | **RTL-SDR backend** | Implement `RTL-SDRBackend` (or `RtlSdrBackend`): move current init/set_frequency logic; in `receive()`, **actually read** I/Q in chunks (e.g. `rtlsdr.read_samples()` in a thread or async loop), compute power → dB, yield `SignalSample`. Handle device_index from env. |
| 2.3 | **HackRF RX backend** | Implement `HackRFBackend` (new file e.g. `receiver/backends/hackrf_rx.py`): use **pyhackrf2** or **python_hackrf** (see Part 2.5). `initialize()`: open device (by index or serial). `set_frequency(hz)`, `receive(duration_sec)`: read I/Q via `read_samples()` or callback, convert to power/dB, yield `SignalSample`. Respect HackRF frequency range (1e6–6e9) and sample rate (2–20e6). |
| 2.4 | **Factory** | In `radio_interface.py`, add `create_sdr_from_env() -> SDRBackend`: read `SDR_TYPE` (default `rtlsdr`). If `hackrf`, build `HackRFBackend` with `HACKRF_INDEX` or `HACKRF_SERIAL`; else build RTL-SDR backend with `RTLSDR_INDEX`. Return backend. |
| 2.5 | **Wire in server** | In `receiver/server.py`, replace direct `SDRInterface(...)` with a thin `SDRInterface` that wraps `create_sdr_from_env()` and delegates to the backend. Or make `SDRInterface` take a backend in constructor; `from_env()` calls `create_sdr_from_env()` and passes it. |
| 2.6 | **Dependencies** | In `remote_receiver/pyproject.toml`, keep `sdr = ["pyrtlsdr"]`, add optional `hackrf = ["pyhackrf2"]` or `["python-hackrf"]` (see Part 2.5; **python_hackrf** preferred if TX will use same lib). Document in README: `uv sync --extra sdr --extra hackrf` for HackRF. |

**Deliverable:** `SDR_TYPE=hackrf` (and optional index/serial) makes remote_receiver use HackRF for RX; RTL-SDR remains default and works with real I/Q once 2.2 is done.

---

### Phase 3: SHAKODS – HackRF transmit path (optional, guarded)

**Goal:** Allow TX via HackRF when explicitly enabled, only on allowed bands, with audit logging.

| Step | Task | Details |
|------|------|---------|
| 3.1 | **Config** | In `RadioConfig`, add: `sdr_tx_enabled: bool = False`, `sdr_tx_backend: str = "hackrf"`, `sdr_tx_device_index: int = 0`, `sdr_tx_max_gain: int = 47` (or equivalent), `sdr_tx_allow_bands_only: bool = True`. |
| 3.2 | **SDR transmitter module** | New `shakods/radio/sdr_tx.py`: class `SDRTransmitter` (protocol or ABC). Method `transmit_iq(frequency_hz, samples_iq, sample_rate)` or higher-level `transmit_cw(freq, duration_sec)` / `transmit_tone(freq, duration_sec)` for simple tests. Implementation `HackRFTransmitter`: use **python_hackrf** (or SoapySDR) so we can feed **custom** I/Q (see Part 2.5). Open HackRF, set freq/gain; for TX use callback (python_hackrf) or `writeStream()` (SoapySDR) to send I/Q. **Before any TX**: call `compliance.is_tx_allowed(frequency_hz)` and `compliance.is_restricted(frequency_hz)`; if not allowed, raise; after TX call `compliance.log_tx(...)`. |
| 3.3 | **Modulation** | For “voice” or “digital” over HackRF, we need baseband I/Q. Options: (a) integrate a small modulator (e.g. FM/AM tone) for testing; (b) pipe audio to an external modulator (GNU Radio, etc.) and read I/Q file/stream; (c) only support “CW” or “tone” in the first version. Plan: add `sdr_tx.transmit_tone(freq, duration_sec)` and optionally `transmit_iq(freq, iq_samples, sample_rate)` for future use. |
| 3.4 | **Radio TX agent** | In `radio_tx.py`, add optional `sdr_transmitter: SDRTransmitter | None = None`. In `_transmit_voice` (and digital/packet if we add SDR path): if `sdr_transmitter` is set and config says use SDR for this task (or fallback when no rig_manager), then run compliance checks, then call `sdr_transmitter.transmit_*`. Otherwise use existing rig_manager path. Enforce that **either** rig_manager **or** sdr_transmitter is used per task, not both. |
| 3.5 | **Wire and default off** | Where agents are created (orchestrator/worker or app lifespan), if `config.radio.sdr_tx_enabled` and backend is `hackrf`, build `HackRFTransmitter` with config and inject into `RadioTransmissionAgent`. Default: `sdr_tx_enabled=False` so that no HackRF TX is possible without explicit opt-in. |
| 3.6 | **Band check for CAT** | In `radio_tx.py`, before **any** TX (rig or SDR), call `compliance.is_tx_allowed(frequency_hz)` (and optionally `is_restricted`). If not allowed, return error and do not key the rig or SDR. Use `config.radio.tx_allowed_bands_only`. |

**Deliverable:** With `sdr_tx_enabled=true` and HackRF connected, tasks can trigger HackRF TX only on allowed bands, with audit log; CAT path also guarded by band/restricted checks.

---

### Phase 4: Documentation and env reference

| Step | Task | Details |
|------|------|---------|
| 4.1 | **HARDWARE_CONNECTION.md** | Update HackRF section: add “HackRF transmit” subsection describing config, compliance (allowlist, restricted, audit log), and that TX is off by default. |
| 4.2 | **remote_receiver README** | Document `SDR_TYPE`, `HACKRF_INDEX`, `HACKRF_SERIAL`; `uv sync --extra hackrf`. |
| 4.3 | **Compliance notice** | In docs and, if applicable, in API response when SDR TX is used: “User is responsible for licensing and regulatory compliance; software enforces band restrictions and logs transmissions.” |

---

### Phase 5: Testing and CI

| Step | Task | Details |
|------|------|---------|
| 5.1 | **Compliance unit tests** | `tests/unit/test_compliance.py`: `is_restricted()` for known restricted frequencies; `is_tx_allowed()` for in-band vs out-of-band; `log_tx` does not raise and writes (or logs). |
| 5.2 | **Backend tests** | Mock or “no hardware” tests: `RTL-SDRBackend` and `HackRFBackend` with a stub/open that fails gracefully when no device; `create_sdr_from_env()` returns correct type for `SDR_TYPE=rtlsdr` vs `hackrf`. |
| 5.3 | **Integration (optional)** | With a real HackRF: manual test of remote_receiver RX and, if implemented, one TX on an amateur frequency with TX enabled and audit log checked. |

---

## Part 4: File and dependency summary

### New files

| Path | Purpose |
|------|---------|
| `shakods/shakods/radio/compliance.py` | Restricted bands, `is_tx_allowed`, `is_restricted`, `log_tx`. |
| `remote_receiver/receiver/backends/__init__.py` | Backend exports. |
| `remote_receiver/receiver/backends/rtlsdr_backend.py` | RTL-SDR backend with real I/Q in `receive()`. |
| `remote_receiver/receiver/backends/hackrf_backend.py` | HackRF RX backend (pyhackrf or SoapySDR). |
| `shakods/shakods/radio/sdr_tx.py` | `SDRTransmitter` protocol and `HackRFTransmitter` with compliance. |
| `shakods/tests/unit/test_compliance.py` | Unit tests for compliance. |

### Modified files

| Path | Changes |
|------|---------|
| `remote_receiver/receiver/radio_interface.py` | Abstract `SDRBackend`; `create_sdr_from_env()`; `SDRInterface` wraps chosen backend. |
| `remote_receiver/receiver/server.py` | Use factory for SDR from env. |
| `remote_receiver/pyproject.toml` | Optional dep `hackrf`. |
| `shakods/shakods/config/schema.py` | `RadioConfig`: SDR TX and compliance options. |
| `shakods/shakods/specialized/radio_tx.py` | Band/compliance check before TX; optional `sdr_transmitter` and SDR TX path. |
| `shakods/shakods/radio/__init__.py` | Export compliance and SDR TX if present. |
| `docs/HARDWARE_CONNECTION.md` | HackRF TX config and compliance. |
| `remote_receiver/README.md` | Env vars for HackRF. |

### Optional dependencies

- **remote_receiver:** `pyhackrf` (or `SoapySDR` + SoapyHackRF system libs).
- **shakods:** `pyhackrf` (or SoapySDR) only when `sdr_tx_enabled=true` and backend is HackRF; can be an extra.

---

## Part 5: Order of implementation (recommended)

1. **Phase 1** (compliance) – no hardware; unblocks safe TX for both CAT and future SDR.
2. **Phase 2** (remote_receiver backends) – HackRF **receive** and real RTL-SDR I/Q; no TX.
3. **Phase 4.1–4.3** (docs) – as you add each feature.
4. **Phase 3** (HackRF TX in shakods) – after Phase 1 and 2; keep TX off by default.
5. **Phase 5** (tests) – unit tests with Phase 1 and 2; optional integration with Phase 3.

This order gives you compliant, audited behaviour first, then full HackRF RX compatibility, then optional HackRF TX with the same compliance layer.
