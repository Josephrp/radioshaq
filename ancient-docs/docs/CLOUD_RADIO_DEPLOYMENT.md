# Deploying SHAKODS on the cloud with a radio transceiver

Radios (HackRF, RTL-SDR, IC-7300, etc.) are **physical USB/serial devices**. They cannot be attached to a typical cloud VM (AWS EC2, GCP, Azure). So “deploy on cloud with a radio” means: **run the control plane in the cloud, run the radio stack on an edge device** that has the transceiver.

---

## Architecture: cloud vs edge

| Layer | Where it runs | What runs there | Hardware |
|--------|----------------|------------------|----------|
| **Cloud** | AWS / GCP / Azure | SHAKODS API, MessageBus, orchestrator, Lambda (message ingestion) | None — no radio |
| **Edge (radio)** | Raspberry Pi, NUC, or PC with USB | `remote_receiver` (RX) and/or SHAKODS with radio (TX) | HackRF, RTL-SDR, or CAT rig |

- **Cloud** handles: API, auth, REACT orchestrator, message bus, Lambda forwarding WhatsApp/SMS → `/bus/inbound`, optional DB. No SDR or rig attached.
- **Edge** handles: SDR receive (and optionally SDR/CAT transmit). The edge device must have the transceiver plugged in and runs either `remote_receiver` only (RX → upload to HQ) or full SHAKODS with `radio.enabled` (TX/RX at the station).

---

## Option 1: Cloud HQ + edge remote receiver (recommended pattern)

**Cloud**

1. Deploy the SHAKODS API (and optional DB) on a VM or container (e.g. ECS, App Runner, or a small EC2).
   - Expose the API (e.g. `https://hq.yourdomain.com`).
   - Ensure the app has a **MessageBus** and the **inbound consumer** running (so messages from Lambda are processed by the orchestrator).
2. Deploy the Lambda message handler (SQS or API Gateway) and set:
   - `SHAKODS_HQ_URL=https://hq.yourdomain.com`
   - Lambda POSTs to `{HQ_URL}/internal/bus/inbound` (or the path your API uses for bus ingestion).
3. No HackRF/RTL-SDR on the cloud — the API does not do any local SDR I/O.

**Edge (receiver only)**

1. On a **Raspberry Pi** (or any Linux host with USB):
   - Attach **RTL-SDR** or **HackRF**.
   - Install and run **remote_receiver**:
     - `SDR_TYPE=rtlsdr` or `SDR_TYPE=hackrf`
     - `HQ_URL=https://hq.yourdomain.com`
     - `STATION_ID=RECV-PI-01`, `JWT_SECRET` / `HQ_TOKEN` as needed.
2. remote_receiver streams/upload to HQ; the cloud API only receives data from the edge, it does not open the SDR.

**Result:** Messages (e.g. WhatsApp) hit Lambda → HQ API → orchestrator. Receive path: edge SDR → remote_receiver → HQ. Transmit path: if you add a **second edge** running SHAKODS with a rig/HackRF (see Option 2), the orchestrator can dispatch TX tasks to that station (e.g. via a dedicated “field” API or agent that talks to the edge).

---

## Option 2: Cloud HQ + edge station with transceiver (TX and RX)

Same cloud setup as Option 1. In addition:

**Edge (station with radio)**

1. On a **PC or NUC** that has the transceiver (HackRF for SDR TX/RX, or IC-7300/FT-450D via CAT):
   - Run **SHAKODS** in field mode with `radio.enabled` and `radio.tx_enabled` (and optional `sdr_tx` for HackRF).
   - This instance can either:
     - **A)** Call back into the cloud HQ API (e.g. poll for tasks or receive commands via a queue), or  
     - **B)** Be the **same** machine that also runs the “HQ” API locally (no cloud; everything on one box with the radio).
2. For **remote receiver** (separate Pi): still run `remote_receiver` with `HQ_URL` pointing at the cloud HQ (or at this field station if it’s the HQ).

**Result:** Cloud handles ingestion and orchestration; the edge station with the transceiver executes TX and, if desired, local RX; optional separate Pi runs remote_receiver and pushes to HQ.

---

## Option 3: Single machine “cloud” with radio (colo / bare metal)

If your “cloud” is a **server in a colo or a bare-metal provider** where you can attach USB:

1. Install SHAKODS API + orchestrator + MessageBus on that server.
2. Plug **HackRF** (or RTL-SDR) into the server’s USB.
3. Run **remote_receiver** on the same machine (or run the SDR/TX path inside the same app if you add that mode).
4. Optionally run Lambda (or another ingestion path) in real AWS that forwards to this server’s public URL.

**Result:** One machine is both “HQ” and the radio host. No separate edge device; the “cloud” is the box that has the radio.

---

## Option 4: Remote SDR over the network (no local USB in cloud)

Some services expose a **remote SDR** (e.g. WebSDR, or a custom gateway that exposes I/Q over the network). In that case:

- The **cloud** code would talk to the remote SDR via HTTP/WebSocket instead of opening local USB.
- Your codebase would need a **client** backend that implements the same interface as `HackRFBackend` / `RtlSdrBackend` but over the network (not implemented today).

This avoids putting hardware in the cloud but requires integrating a remote-SDR API and possibly dealing with latency and access control.

---

## Summary

| Goal | Approach |
|------|----------|
| “Cloud” API + message ingestion | Deploy SHAKODS API + Lambda in AWS (or similar); set `SHAKODS_HQ_URL` so Lambda POSTs to `/internal/bus/inbound`. |
| Use a **radio transceiver** with that cloud | Run the **radio** on an **edge** device (Pi/PC/NUC) with the HackRF or RTL-SDR plugged in. Run `remote_receiver` (and/or SHAKODS with radio) there, with `HQ_URL` pointing at your cloud API. |
| Everything on one machine | Run API + orchestrator + remote_receiver (and optional SDR TX) on a single host that has the transceiver (e.g. colo or bare metal). |

So: **deploy the app and message bus in the cloud; deploy the transceiver and SDR/rig stack on an edge device** that connects to that cloud API. There is no way to plug a HackRF into a standard AWS/GCP/Azure VM; the hybrid split is required.
