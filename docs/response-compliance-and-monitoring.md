# Response & compliance

Operator response (emergency approval, relay, contact preferences), compliance (radio and messaging), and monitoring (metrics, health, WebSocket).

---

## 1. Response

### 1.1 Emergency message approval (operator confirmation)

**Purpose:** Emergency outreach is for the **operator to receive messages and transmit them**. The operator receives each emergency request (message text and destination), then transmits by approving it — the system sends the message via SMS or WhatsApp to the specified contact.

When emergency SMS/WhatsApp is enabled and approval is required, outbound emergency messages are **queued until an operator approves or rejects them**. The operator can use the **web UI** (Emergency page) or the **API**.

**Config:** Set `RADIOSHAQ_EMERGENCY_CONTACT__ENABLED=true` and `RADIOSHAQ_EMERGENCY_CONTACT__REGIONS_ALLOWED` (e.g. `["FCC","CA"]`). See `.env.example` in the repository; full details are in the project doc *Notify and emergency compliance plan* (radioshaq/docs/).

**How the operator is informed (timely relay or reject):**

1. **Audio** — When the pending count goes from 0 to greater than 0, the web UI plays a short alert sound (two beeps) so the operator is notified even if the tab is in the background.
2. **Automated polling** — The web UI polls `GET /emergency/pending-count` every 15s (and the Emergency page polls the event list every 12s). An optional **SSE stream** `GET /emergency/events/stream` sends the pending count every 10s for clients that prefer a long-lived connection.
3. **Push notification** — When new pending messages arrive (count 0 → N), the browser **Notification** API is used (if the user has clicked “Allow notifications” and permission is granted). This notifies the operator when the tab is in the background or the browser is minimised.

**API endpoints (for scripts or custom UIs):**

- **Pending count:** `GET /emergency/pending-count` — returns `{"count": N}`.
- **SSE stream:** `GET /emergency/events/stream` — Server-Sent Events; each event is `data: {"pending_count": N}` every ~10s. Requires Bearer token.
- **List pending:** `GET /emergency/events` (optional: `?status=pending`) — returns `events` and `count` with `id`, `initiator_callsign`, `target_callsign`, `notes`, `extra_data` (e.g. `emergency_contact_phone`, `emergency_contact_channel`, `message`).

**Web UI flows:** Open the **Emergency** page in the RadioShaq web interface. The page lists all pending emergency events with contact phone, channel (SMS/WhatsApp), and message text. Use **Approve & send** to transmit the message to the contact, or **Reject** to decline (no message sent). Optional notes can be added before approving or rejecting. Click **Allow notifications** to enable browser push when new requests arrive.

**How the operator transmits (confirms):**

1. **Approve and send**  
   `POST /emergency/events/{event_id}/approve`  
   Optional body: `{"notes": "optional note"}`. Requires a valid **Bearer token**. Sends the message via SMS/WhatsApp. The backend:

   - Verifies the event is `emergency` and `pending`
   - Sets `status=approved` and records `approved_at` and `approved_by` (from the JWT: `sub` or `callsign`)
   - Publishes the message to the outbound bus (SMS or WhatsApp is sent by the dispatcher)
   - Sets `sent_at` in `extra_data`

**Example (curl):**

```bash
# Check how many pending (use your JWT)
curl -s -H "Authorization: Bearer YOUR_JWT" "https://your-api/emergency/pending-count"

# List pending (use your JWT)
curl -s -H "Authorization: Bearer YOUR_JWT" "https://your-api/emergency/events"

# Approve event 42 (sends the SMS/WhatsApp)
curl -s -X POST -H "Authorization: Bearer YOUR_JWT" \
  -H "Content-Type: application/json" -d '{"notes": "Verified"}' \
  "https://your-api/emergency/events/42/approve"
```

2. **Reject (do not send)**  
   `POST /emergency/events/{event_id}/reject`  
   Optional body: `{"notes": "optional note"}`. Sets `status=rejected` and records `rejected_at`, `rejected_by`; no message is sent.

**Creating emergency requests:** Use `POST /emergency/request` (body: `contact_phone`, `contact_channel` sms/whatsapp, optional `target_callsign`, `notes`) or relay with `emergency: true`. See [API Reference](api-reference.md) for endpoints.

---

### 1.2 Relay (radio, SMS, WhatsApp)

- **Radio relay:** Message is stored for the destination callsign/band; optionally injected or transmitted on the target band (site config).
- **SMS/WhatsApp relay:** Set `target_channel=sms` or `whatsapp` and `destination_phone` (E.164). The relay is stored and delivered by the relay_delivery worker and outbound dispatcher.
- **Emergency relay:** Set `emergency=true` with SMS/WhatsApp target. If the region is allowed and approval is required, the message is **queued for approval** (coordination event); an operator must call `POST /emergency/events/{id}/approve` before it is sent. See §1.1.

API: `POST /messages/relay`. See [API Reference](api-reference.md).

---

### 1.3 Contact preferences and notify-on-relay

Whitelisted callsigns can opt in to receive a **short SMS or WhatsApp notification** when a message is left for them on radio (notify-on-relay).

- **Get/set preferences:** `GET /callsigns/registered/{callsign}/contact-preferences`, `PATCH /callsigns/registered/{callsign}/contact-preferences` (set `notify_sms_phone`, `notify_whatsapp_phone`, `notify_on_relay`, `consent_source`; in strict regions, `consent_confirmed=true` when enabling).
- **Opt-out:** When a recipient replies STOP, call `POST /internal/opt-out` with `phone` or `callsign` and `channel` (sms/whatsapp) so the system records opt-out and stops notifications.

Details (consent, opt-out, region behaviour) are in the project doc *Notify and emergency compliance plan* (radioshaq/docs/).

---

## 2. Compliance

### 2.1 Radio (restricted bands and band plans)

The compliance plugin enforces **restricted bands** and **band plans** by region (FCC, CEPT, CA, AU, ZA, etc.). Configure:

- `RADIOSHAQ_RADIO__RESTRICTED_BANDS_REGION` — e.g. `FCC`, `CA`, `CEPT`, `FR`, `UK`, `AU`, `ZA`. Drives which bands are disallowed for transmission.
- `RADIOSHAQ_RADIO__BAND_PLAN_REGION` — optional override (e.g. `ITU_R1`, `ITU_R3`); leave blank to use the backend default for the region.

**Operators are responsible for verifying national rules** (e.g. ANFR, Ofcom, ACMA, IFT).

#### Backend overview

| Backend | Region | Restricted bands source | Band plan | Official references |
|---------|--------|-------------------------|-----------|----------------------|
| **FCC** | US (and baseline for some R2) | 47 CFR §15.205 | ITU R2 (Americas) | [ecfr.gov §15.205](https://www.ecfr.gov/current/title-47/chapter-I/subchapter-A/part-15/subpart-C/section-15.205), [law.cornell.edu](https://www.law.cornell.edu/cfr/text/47/15.205) |
| **CEPT** | EU harmonised | ECC/ETSI (see below) | IARU R1 | ERC/REC 70-03, EU 2006/771/EC, ETSI EN 300 220 |
| **FR** | France | Same as CEPT | IARU R1 | CEPT + national ANFR |
| **UK** | United Kingdom | Same as CEPT (Ofcom) | IARU R1 | CEPT; Ofcom UKFAT |
| **ES** | Spain | Same as CEPT | IARU R1 | CEPT + national authority |
| **BE** | Belgium | Same as CEPT | IARU R1 | CEPT TR 61-01/61-02; BIPT/IBPT |
| **CH** | Switzerland | Same as CEPT | IARU R1 | CEPT; BAKOM |
| **LU** | Luxembourg | Same as CEPT | IARU R1 | CEPT; ILNAS |
| **MC** | Monaco | Same as CEPT | IARU R1 | CEPT |
| **ITU_R1** | Band plan only | — | IARU R1 | [IARU R1 band plans](https://www.iaru-r1.org/on-the-air/band-plans/) |
| **ITU_R3** | Band plan only | — | IARU R3 (2m 144–148 MHz, 70cm 430–440 MHz) | IARU R3-004 (2019); [IARU R3](https://www.iaru.org/) |
| **CA** | Canada (ITU R2) | FCC §15.205 baseline; RSS-210 §7.1, Annexes A/B (ISED) | ITU R2 | ISED RSS-210 Issue 11; RBR-4; CEPT T/R 61-01 for reciprocal |
| **MX** | Mexico (ITU R2) | FCC §15.205 baseline (IFT CNAF, IFT-016-2024) | ITU R2 | IFT; FCC as baseline; verify IFT |
| **AR, CL, CO, PE, VE, EC, UY, PY, BO, CR, PA, GT, DO** | R2 Americas (see table) | FCC §15.205 baseline | ITU R2 | IARU R2; verify IFT, ENACOM, SUBTEL, CRC, etc. |
| **AU** | Australia (ITU R3) | ACMA Spectrum Plan / conservative set | IARU R3 | ACMA; WIA band plan |
| **ZA** | South Africa (ITU R1) | ICASA NRFP / RFSAPs (conservative set) | IARU R1 | ICASA; SARL |
| **NG, KE, EG, MA, TN, DZ, GH, TZ, ET, SN, CI, CM, BW, NA, ZW, MZ, UG, RW, GA, ML, BF, NE, TG, BJ, CD, MG** | R1 Africa (see table) | R1 conservative (CEPT-aligned); ZA uses dedicated list | IARU R1 | Verify national regulator (NCC, CA, NTRA, ANRT, BOCRA, etc.) |
| **NZ** | New Zealand (ITU R3) | RSM PIB 21 conservative set | IARU R3 | RSM; PIB 21 |
| **JP** | Japan (ITU R3) | Conservative set (MIC/JARL) | IARU R3 | MIC; JARL |
| **IN** | India (ITU R3) | Conservative set (WPC) | IARU R3 | WPC; ARSI |

**Important:** Use **ITU_R1** and **ITU_R3** only as `band_plan_region`, not as `restricted_bands_region`. They provide band plans but no restricted-band list; setting them as restricted region would disable all restricted-band enforcement. Set `restricted_bands_region` to a country (e.g. CEPT, FR, AU) and `band_plan_region` to ITU_R1 or ITU_R3 if you need that plan.

#### FCC (United States)

- **Rule:** 47 CFR §15.205 — Restricted bands of operation.
- **Meaning:** Intentional radiators must not operate in the listed bands; only spurious emission limits (§15.209) apply.
- **Source:** Code of Federal Regulations, title 47, chapter I, subchapter A, part 15, subpart C, section 15.205. The list in code is maintained from the official eCFR/Cornell text.

#### CEPT / EU (France, UK, Spain, etc.)

CEPT does **not** publish a single “FCC 15.205 equivalent” list. EU harmonisation defines **allowed** SRD bands and conditions; “restricted” is inferred from:

1. **ERC/REC 70-03** (CEPT Recommendation on Short Range Devices)  
   - [docdb.cept.org document 845](https://docdb.cept.org/document/845) — Annexes list allowed SRD applications and bands; Appendix 3 lists national restrictions.  
   - [ECO Frequency Information System (EFIS)](https://efis.cept.org/) — National implementation status and restrictions.

2. **EU Commission Decision 2006/771/EC** (as amended)  
   - Harmonised technical conditions for SRD; annex lists frequency bands and parameters.  
   - [EUR-Lex CELEX 32006D0771](https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX:32006D0771).

3. **ETSI EN 300 220**  
   - Harmonised standard for SRD 25 MHz–1000 MHz. Defines permitted bands (e.g. 433.04–434.79 MHz, 863–876 MHz, 915–921 MHz).  
   - [ETSI EN 300 220-2](https://www.etsi.org/deliver/etsi_en/300200_300299/30022002/).

The **CEPT restricted list in code** is derived from bands that are commonly protected in EU (aeronautical, radionavigation, COSPAS-SARSAT, marine, etc.). It explicitly **omits** FCC-only ranges (e.g. 240–285 MHz, 322–335.4 MHz, US GHz blocks). National administrations (e.g. ANFR France, Ofcom UK) may add further restrictions; operators must check national rules.

#### Band plans

- **ITU Region 2 (Americas):** Default in `bands.py`; 2m 144–148 MHz, 70cm 420–450 MHz.  
  [IARU R2 band plans](https://www.iaru-r2.org/en/reference/band-plans/).

- **ITU Region 1 (Europe, Africa, Middle East):** 2m 144–146 MHz, 70cm 430–440 MHz.  
  [IARU R1 band plans](https://www.iaru-r1.org/on-the-air/band-plans/).

- **ITU Region 3 (Asia–Pacific):** IARU R3 band plan: 2m 144–148 MHz, 70cm 430–440 MHz (secondary in R3; 440–450 only in Australia/Philippines per RR 5.270). Used by **ITU_R3** and **AU** backends. [IARU R3-004 (2019)](https://www.iaru.org/).

#### Country → backend mapping

| Country / area | Recommended `restricted_bands_region` | Notes |
|----------------|----------------------------------------|--------|
| United States | `FCC` | R2 band plan default |
| Canada | `CA` or `FCC` | R2; ISED/RBR-4; CEPT reciprocal for EU visits |
| France | `FR` or `CEPT` | R1; ANFR |
| Belgium | `BE` or `CEPT` | R1; BIPT/IBPT |
| Switzerland | `CH` or `CEPT` | R1; BAKOM |
| Luxembourg | `LU` or `CEPT` | R1 |
| Monaco | `MC` or `CEPT` | R1 |
| United Kingdom | `UK` or `CEPT` | R1; Ofcom |
| Spain | `ES` or `CEPT` | R1 |
| Mexico | `MX` or `FCC` | R2; IFT |
| Argentina | `AR` or `MX` | R2; ENACOM |
| Chile | `CL` or `MX` | R2; SUBTEL |
| Colombia | `CO` or `MX` | R2; CRC |
| Peru | `PE` or `MX` | R2; MTC |
| Venezuela | `VE` or `MX` | R2; CONATEL |
| Ecuador | `EC` or `MX` | R2 |
| Uruguay | `UY` or `MX` | R2 |
| Paraguay | `PY` or `MX` | R2 |
| Bolivia | `BO` or `MX` | R2 |
| Costa Rica | `CR` or `MX` | R2 |
| Panama | `PA` or `MX` | R2 |
| Guatemala | `GT` or `MX` | R2 |
| Dominican Republic | `DO` or `MX` | R2 |
| Other Latin America / Caribbean (R2) | `MX` or `FCC` | R2; verify national regulator |
| Australia | `AU` or `ITU_R3` | IARU R3; restricted bands enforced (ACMA conservative set) — verify ACMA |
| New Zealand | `NZ` | R3; restricted bands enforced (RSM PIB 21 conservative); verify RSM |
| Japan | `JP` | R3; restricted bands enforced (conservative set); verify MIC/JARL |
| India | `IN` | R3; restricted bands enforced (conservative set); verify WPC/ARSI |
| Other R3 | `ITU_R3` | R3 band plan; verify national regulator |
| South Africa | `ZA` | R1; restricted bands enforced (ICASA NRFP); verify ICASA; SARL |
| Nigeria | `NG` | R1; restricted: R1 conservative; verify NCC |
| Kenya | `KE` | R1; restricted: R1 conservative; verify CA |
| Egypt | `EG` | R1; restricted: R1 conservative; verify NTRA |
| Morocco | `MA` | R1; restricted: R1 conservative; verify ANRT |
| Tunisia | `TN` | R1; restricted: R1 conservative; verify national authority |
| Algeria | `DZ` | R1; restricted: R1 conservative; verify national authority |
| Ghana | `GH` | R1; restricted: R1 conservative; verify NCA |
| Tanzania | `TZ` | R1; restricted: R1 conservative; verify TCRA |
| Ethiopia | `ET` | R1; restricted: R1 conservative; verify ETA |
| Senegal | `SN` | R1; restricted: R1 conservative; verify ARTP |
| Côte d'Ivoire | `CI` | R1; restricted: R1 conservative; verify ARTCI |
| Cameroon | `CM` | R1; restricted: R1 conservative; verify MINPOSTEL |
| Botswana | `BW` | R1; restricted: R1 conservative; verify BOCRA |
| Namibia | `NA` | R1; restricted: R1 conservative; verify CRAN |
| Zimbabwe | `ZW` | R1; restricted: R1 conservative; verify POTRAZ |
| Mozambique | `MZ` | R1; restricted: R1 conservative; verify INCM |
| Uganda | `UG` | R1; restricted: R1 conservative; verify UCC |
| Rwanda | `RW` | R1; restricted: R1 conservative; verify RURA |
| Gabon | `GA` | R1; restricted: R1 conservative; verify ARCEP |
| Mali, Burkina Faso, Niger, Togo, Benin | `ML`, `BF`, `NE`, `TG`, `BJ` | R1; restricted: R1 conservative; verify national regulator |
| DRC, Madagascar | `CD`, `MG` | R1; restricted: R1 conservative; verify national regulator |
| Other Africa (ITU R1) | `ZA` or country code or `ITU_R1` | R1 band plan; restricted: R1 conservative; verify national regulator |

---

### 2.2 Messaging (SMS/WhatsApp: consent, opt-out, emergency)

- **Notify-on-relay:** Consent is recorded when a user enables “notify when a message is left for me” (`notify_consent_at`, `notify_consent_source`). In strict regions (EU/UK/ZA), explicit `consent_confirmed` is required. Opt-out (STOP) is handled via `POST /internal/opt-out`.
- **Emergency:** Emergency SMS/WhatsApp is **region-gated** (`emergency_contact.regions_allowed`, e.g. FCC, CA) and **human-approved** when `approval_required=true`. Each approval and send is recorded (`approved_at`, `approved_by`, `sent_at` in event `extra_data`).

Country/region rules (US TCPA, Canada CASL, EU/UK GDPR/PECR, Australia Spam Act, South Africa POPIA, WhatsApp) and the region→profile table are documented in the project’s *Notify and emergency compliance plan* (radioshaq/docs/).

---

## 3. Monitoring

### 3.1 Prometheus `/metrics`

**Endpoint:** `GET /metrics` (no authentication).

Returns Prometheus exposition format (text/plain) with:

| Metric | Type | Description |
|--------|------|-------------|
| `radioshaq_uptime_seconds` | gauge | Process uptime in seconds |
| `radioshaq_callsigns_registered_total` | gauge | Number of registered (whitelisted) callsigns |
| `radioshaq_relay_deliveries_total` | counter | Incremented by relay_delivery worker |
| Listener/band gauges | gauge | Messages per band when band listener reports |
| `radioshaq_gpu_utilization_percent` | gauge | GPU utilization 0–100 (when `nvidia-smi` available) |
| `radioshaq_gpu_memory_used_mb` / `_total_mb` | gauge | GPU memory (when `nvidia-smi` available) |

GPU metrics are populated only when **nvidia-smi** is on the PATH. For full Prometheus client support: `uv sync --extra metrics` (from the radioshaq directory).

**Example scrape config (Prometheus):**

```yaml
scrape_configs:
  - job_name: radioshaq
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: /metrics
```

---

### 3.2 Health checks

Use **`GET /health`** for liveness and **`GET /health/ready`** for readiness (DB, orchestrator, audio agent). See [API Reference](api-reference.md).

---

### 3.3 Audio metrics (WebSocket)

When the voice_rx pipeline is running, real-time audio metrics (VAD, SNR, state) are available over a **WebSocket**. **Endpoint:** `WS /ws/audio/metrics/{session_id}`. By default the server sends a placeholder heartbeat every second (`vad_active: false`, `snr_db: null`, `state: "idle"`). When the voice_rx pipeline is wired, set `app.state.audio_metrics_latest` to a dict with `vad_active`, `snr_db`, `state`, and optional `type`; the handler sends it to connected clients once per second. The web UI can show “live” audio state; without a live signal, a placeholder or “waiting for pipeline” message may be shown.

---

## See also

- [Configuration](configuration.md) — env and config options
- [API Reference](api-reference.md) — endpoints and auth

Project docs in the repository (radioshaq/docs/): *Twilio SMS & WhatsApp*, *Notify and emergency compliance plan*, *SMS/WhatsApp implementation plan*.
