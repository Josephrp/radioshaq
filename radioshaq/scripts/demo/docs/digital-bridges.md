# Digital bridges (FLDIGI, WSJT-X/FT8, Direwolf/APRS)

RadioShaq aims to be comprehensive across bands and modes. For several widely-used **digital** modes, the most reliable approach is to integrate with the de-facto standard software rather than re-implement full PHY stacks immediately.

This doc describes the recommended “bridge” components and how to hook them into RadioShaq.

## FLDIGI (PSK31 / RTTY / etc.)

- **What it does**: Digital text modems + decode/encode.
- **How RadioShaq uses it**: XML-RPC control (set modem, RX text, TX text).
- **Code**: `radioshaq/radioshaq/radio/digital_modes.py` (`FLDIGIInterface`)
- **Config** (HQ/field):
  - `radio.fldigi_enabled`
  - `radio.fldigi_host`
  - `radio.fldigi_port`

### Audio routing
FLDIGI still needs audio. Common patterns:
- **CAT rig**: Rig’s USB audio codec → FLDIGI soundcard input/output.
- **SDR**: SDR demodulated audio → virtual audio device → FLDIGI.

On Windows this typically uses **VB-Audio Virtual Cable** (or similar). On Linux/macOS, use PulseAudio/Jack/Loopback.

## WSJT-X / `jt9` (FT8 decode)

- **What it does**: Weak-signal modes. FT8 is commonly handled by WSJT-X tooling.\n- **Recommended CLI**: `jt9 -8 <wavfile>`\n- **Why**: Correctness, mature decoder, avoids re-implementing LDPC + sync.\n\n### Demo script\n+- `radioshaq/scripts/demo/ft8_decode_wav.py` runs `jt9` on a WAV file and prints decodes.\n\n### Notes\n+- `jt9` expects **12 kHz** audio WAVs in many common setups. If your capture is 48 kHz, resample to 12 kHz before decoding.\n+- Useful `jt9` flags:\n+  - `-8` (FT8)\n+  - `-f <Hz>` RX frequency offset (default 1500)\n+  - `-L/-H` decode frequency window\n+\n## Direwolf (AX.25 / APRS)\n\n- **What it does**: Packet modem and APRS decode/encode.\n- **How RadioShaq uses it**:\n+  - **KISS TCP** for frames (RX/TX)\n+  - Audio routing via sound device (Direwolf reads audio from your rig/virtual cable)\n+- **Code**: `radioshaq/radioshaq/radio/packet_radio.py` (KISS TX; RX callback hooks)\n\n### Audio routing\n+- **CAT rig**: Rig’s data audio → Direwolf input.\n+- **SDR**: SDR demodulated NFM audio (1200/9600 AFSK) → virtual audio device → Direwolf.\n+\n+## Where this plugs into the “comprehensive” architecture\n+\n+- Analog demod/mod is handled in-process (SDR DSP).\n+- Digital modem families are bridged via:\n+  - FLDIGI XML-RPC\n+  - WSJT-X `jt9` CLI\n+  - Direwolf KISS TCP\n+\n+This keeps RadioShaq practical and interoperable while still allowing future native implementations.\n+
