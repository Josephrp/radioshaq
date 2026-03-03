# SHAKODS: Materials & Purchasing Guide (Ship to France / Pay in USD)

Options for each piece of equipment, with links. **France delivery** and **paying in USD** where possible (PayPal, Wise, or US retailers). Unlimited budget assumed.

**Connecting this gear to the codebase:** see **[docs/HARDWARE_CONNECTION.md](docs/HARDWARE_CONNECTION.md)** for deployment (CAT/Hamlib config, rig model numbers, remote_receiver on Pi, and one config per station).

---

## Paying in USD from France

- **PayPal**: Many EU/UK shops accept PayPal; you can fund in USD and PayPal converts (check “pay in seller currency” vs “pay in USD” to compare).
- **Wise (ex-TransferWise) card**: Hold and spend USD at mid-market rate; useful for US sites.
- **US retailers + forwarder**: Use a US address (e.g. [Global Shopaholics](https://globalshopaholics.com/en-fr/), others); shop in USD, then forward to France (~$23+ per shipment).

---

## Easier: complete / all-in-one units

If you prefer **less assembly and configuration**, these are “radio in a box” or “receiver in a box” options. You still add antenna + power (and network for receivers); no separate Pi, dongle, or rig stacking unless noted.

### Receiver side (listen only — remote receiver / SDR)

| Product | What it is | Setup | Where (France / EU) | Link |
|--------|------------|--------|----------------------|------|
| **KiwiSDR 2** | Complete HF receiver (10 kHz–30 MHz). Built-in computer (BeagleBone), GPS, case, web interface. **No PC or Pi needed.** Plug: 5 V PSU, Ethernet, antenna. Use from any browser. | Easiest: power + Ethernet + antenna. Optional integration with SHAKODS `remote_receiver` (API/stream). | WIMO (Germany, EU) — €497; KiwiSDR NZ ships worldwide (~$395 USD). | [WIMO](https://www.wimo.com/en/kiwisdr-2) · [KiwiSDR NZ](https://kiwisdr.nz/products/kiwisdr2-1) |
| **SDRplay RSPdx** | Wideband SDR receiver (1 kHz–2 GHz). USB to PC/Raspberry Pi. No computer included; you run SDRuno/SDRconnect or your own stack. | Add USB cable + antenna + PC or Pi. Simpler than “naked” RTL-SDR (better filtering, 14-bit). | SDRplay site, WIMO, Passion Radio (check for RSP1B/RSPdx). | [SDRplay RSPdx](https://www.sdrplay.com/RSPdx/) · [WIMO](https://www.wimo.com/en/radios/ham-radio) |
| **RTL-SDR V4 + antenna kit** | Dongle + dipole/tripod in one box. Still need a PC or Pi to run `remote_receiver`. | Plug dongle + antenna into Pi/PC; install OS + `remote_receiver`. | WIMO, Passion Radio, AliExpress (see §2 below). | [WIMO RTL-SDR V4 kit](https://www.wimo.com/en/rtl-sdr-v4-kit) |
| **Elektor Pi 5 + RTL-SDR V4 bundle** | Raspberry Pi 5 + RTL-SDR V4 + book. Single purchase; you install OS and `remote_receiver`. | One box for “receiver host + SDR”; you add PSU, antenna, network. | Elektor (EU). | [Elektor bundle](https://www.elektor.com/products/raspberry-pi-5-rtl-sdr-v4-bundle) |

**Best “easiest” receiver:** **KiwiSDR 2** — no Pi, no dongle, no driver mess. Power + Ethernet + HF antenna; use the built-in web UI. You can later point SHAKODS at it if you add API/stream support.

---

### Emitter / field station (transmit + receive)

| Product | What it is | Setup | Where (France / EU) | Link |
|--------|------------|--------|----------------------|------|
| **Xiegu X6100** | All-in-one portable HF/50 MHz SDR: radio + built-in battery + ATU + display. 10 W. | Add antenna (e.g. whip or wire). USB for CAT/digital; compatible with Hamlib/FLDIGI. | Xiegu.eu, WIMO, Radioddity (US). | [Xiegu.eu](https://xiegu.eu/product/xiegu-x6100-hf-50mhz-portable-sdr-transceiver) · [WIMO](https://www.wimo.com/en/xiegu-x6100) |
| **Yaesu FTX-1 Optima MAX** | HF + 50 + 144 + 430 MHz, 100 W (with amp) or ~6 W portable with battery. All-mode SDR, tuners, Bluetooth headset, cage. | Add antenna(es) + optional PSU/amp for 100 W. One radio for base + field. | EU dealers (e.g. Handelsonderneming Veenstra); Passion Radio may list. | [Veenstra FTX-1](https://www.handelsondernemingveenstra.nl/en/yaesu/4021-yaesu-ftx-1f-all-mode-hfvhfuhf-transceiver-.html) |
| **FlexRadio Aurora AU-510M** | Desktop “everything in one”: 500 W amp, tuner, PSU, Maestro touchscreen. 30 kHz–54 MHz. | Add antenna + mains. No separate amp/tuner/PSU. | FlexRadio; EU dealers. | [FlexRadio Aurora AU-510M](https://flexradio.com/products/aurora-au-510m-signature-series) |
| **FlexRadio Aurora AU-520** | Same idea, no built-in display; for remote/rack. 4 slices, 4 panadapters. | Add antenna + mains + remote client (PC/tablet). | FlexRadio. | [FlexRadio Aurora AU-520](https://flexradio.com/products/aurora-au-520-signature-series) |

**Best “easiest” emitter (portable):** **Xiegu X6100** — one box, battery, tuner, CAT; add antenna and go. **Best “easiest” base (no budget limit):** **FlexRadio Aurora** — transceiver + amp + tuner + PSU in one chassis.

---

### Summary

- **Easiest receiver:** KiwiSDR 2 (power + Ethernet + antenna; use from browser).
- **Easiest portable emitter:** Xiegu X6100 (add antenna; USB for SHAKODS/Hamlib).
- **Easiest base station:** FlexRadio Aurora or a single rig like IC-7300 with internal tuner (see §1).

SHAKODS `remote_receiver` today targets RTL-SDR/pyrtlsdr (and optionally a CAT rig). KiwiSDR 2 can still be used as a separate “ready-made remote receiver”; integrating it into SHAKODS would need a small adapter (e.g. call KiwiSDR’s API or stream from it).

---

## Budget options (lower-cost choices)

Same roles as above, but **cheaper** options. Trade-offs: less power (QRP), fewer bands, weaker filtering/sensitivity, or more DIY. Links target France/EU where possible.

### Budget transceiver (emitter)

| Product | Rough price | Notes | Where |
|--------|-------------|--------|--------|
| **Xiegu G106** | ~€349 (WIMO) / ~£190 (UK) | 5 W HF QRP SDR, SSB/CW/AM. CAT possible; good for digital/FT8. | [WIMO](https://www.wimo.com/en/xiegu-g106-qrp-transceiver) · [Xiegu.eu](https://xiegu.eu/product/xiegu-g106-hf-qrp-sdr-transceiver) · [Ham Radio UK](https://www.hamradio.co.uk/g106) |
| **Xiegu G1M** | ~€279 | 5–8 W, 4 bands (80/40/30/20 m). Replaced by G1M G-Core; check stock. | [Xiegu.eu](https://xiegu.eu/product/xiegu-g1m-qrp-5-band-hf-transceiver) |
| **Xiegu G90** | ~€410–490 | 20 W, built-in ATU, full HF. Already in §1; best budget "real" rig. | [WIMO](https://www.wimo.com/en/xiegu-g90) · [Xiegu.eu](https://xiegu.eu/product/xiegu-g90-hf-20w-sdr-transceiver) |
| **Hambuilder HBR4HFS V3** | ~$161 (≈€150) | 25 W, 80/40/30/20 m. Indonesia; worldwide ship (contact for EU). Often out of stock. | [Hambuilder](https://hambuilder.com/product/hbr4hfs-v3-0-25w-quad-band-hf-transceiver/) |

**Budget pick:** **Xiegu G106** (QRP) or **G90** (20 W + tuner). **Ultra-budget:** Hambuilder if in stock (confirm CAT/Hamlib support).

---

### Budget SDR receiver (receiver station)

| Product | Rough price | Notes | Where |
|--------|-------------|--------|--------|
| **RTL-SDR Blog V4** (dongle only) | ~$30 USD | Best value "real" SDR; HF upconverter, TCXO. Need antenna + PC/Pi. | [RTL-SDR shop](https://www.rtl-sdr.com/shop/) (non-EU); EU: [eBay](https://www.ebay.com/str/rtlsdrblog) · [AliExpress FR](https://fr.aliexpress.com/store/1101427871) |
| **Nooelec NESDR Mini 2+** | ~$35 / ~€47 | RTL2832U + R820T2, TCXO. US shop or Amazon EU. | [Nooelec](https://www.nooelec.com/store/sdr/sdr-receivers/nesdr-mini-2.html) · Amazon.be (search NESDR Mini) |
| **Nooelec NESDR Mini** | ~$25–35 | R820T (no R820T2), basic. | [Nooelec](https://www.nooelec.com/store/sdr/sdr-receivers/nesdr/nesdr-mini.html) |
| **Generic RTL-SDR** | ~€10–20 | RTL2832U + R820T/R820T2, often MCX. No TCXO, no bias-T; works with pyrtlsdr. Risk of fakes. | Amazon.fr / Amazon.nl: search "RTL-SDR RTL2832U" (e.g. Luxtech, no-name). |

**Budget pick:** **RTL-SDR Blog V4 dongle** or **Nooelec NESDR Mini 2+**. **Ultra-budget:** Generic dongle from Amazon (check reviews; prefer R820T2).

---

### Budget receiver host (SBC)

| Product | Rough price | Notes | Where |
|--------|-------------|--------|--------|
| **Raspberry Pi Zero 2 W** | ~€16–20 | 512 MB RAM, WiFi. Can run `remote_receiver` with RTL-SDR (lightweight stack). | [Kubii](https://www.kubii.com/en/nano-computers/3455-2110-raspberry-pi-zero-2-w-wh.html) · [welectron](https://www.welectron.com/Raspberry-Pi-Zero-2-W_1) · [Electrokit](https://www.electrokit.com/en/raspberry-pi-zero-2-w-no-pin-header) |
| **Orange Pi Zero 2W** | ~$24–28 | 1–4 GB RAM, more CPU than Pi Zero 2. Less standard Linux support; may need extra setup. | AliExpress, Amazon (search "Orange Pi Zero 2W"; prefer official store). |
| **Raspberry Pi 4 (2 GB)** | ~€45–55 | If 4 GB not needed; same software as 4 GB. | Kubii, Kiwi Electronics (search "Raspberry Pi 4 2GB"). |

**Budget pick:** **Pi Zero 2 W** for receiver if you keep workloads light (e.g. one SDR, no heavy decoding). Else **Pi 4 (2 GB)**.

---

### Budget antenna

| Option | Rough cost | Notes | Link / DIY |
|--------|------------|--------|-------------|
| **DIY EFHW (40–10 m)** | ~€5–30 | Wire + toroid + capacitor + connector. 49:1 unun; no tuner on resonant bands. | [OH8STN DIY €4-style](https://oh8stn.org/blog/2021/12/06/diy-4-qrp-multiband-endfed-half-wave-ultra-simple-lightweight-40-20-10-30-17-12/) · [HamCalc 49:1 design](https://hamcalc.com/articles/end-fed-half-wave-design) |
| **Random wire + 9:1 unun** | ~€10–25 | Any long wire + 9:1 balun; **tuner required**. | [W3ATB cheap HF antenna](https://w3atb.com/cheap-hf-antenna/) |
| **Simple wire (multiband lengths)** | ~€5 or less | Single wire (e.g. 29–107 ft); tuner + counterpoise. | Same refs; wire from hardware store. |
| **Budget commercial EFHW** | ~€40–80 | Pre-built 40/20/15/10 m; lower than MyAntennas. | eBay, AliExpress (search "EFHW 40m"), or Passion Radio (entry-level antennas). |

**Budget pick:** **DIY EFHW** (40 m half-wave ~20 m wire + 49:1) or **random wire + 9:1** if you have a tuner.

---

### Budget "complete" receiver (minimal stack)

- **Cheapest usable:** **Generic RTL-SDR** (~€15) + **Raspberry Pi Zero 2 W** (~€18) + **DIY wire antenna** (~€5) + 5 V PSU + microSD. **Total ~€45–55.** You install Raspberry Pi OS and `remote_receiver` (or lightweight SDR stack).
- **Better quality:** **RTL-SDR Blog V4 dongle** (~€35) + **Pi Zero 2 W** or **Pi 4 (2 GB)** + same antenna/PSU. **Total ~€70–90.**

---

### Budget "complete" emitter (minimal stack)

- **QRP:** **Xiegu G106** (~€349) or **G1M** (~€279) + **DIY EFHW** or wire + tuner. **Total ~€300–380.**
- **More power:** **Xiegu G90** (~€450) + same antenna. **Total ~€480–520.**
- **Ultra-budget (if in stock):** **Hambuilder HBR4HFS** (~$161) + DIY antenna. Confirm CAT for SHAKODS/Hamlib.

---

### Budget summary

| Role | Budget choice | Ultra-budget |
|------|----------------|--------------|
| **Receiver (SDR)** | RTL-SDR Blog V4 or Nooelec NESDR Mini 2+ | Generic RTL-SDR (Amazon) |
| **Receiver host** | Raspberry Pi Zero 2 W or Pi 4 (2 GB) | Pi Zero 2 W |
| **Emitter** | Xiegu G106 (QRP) or G90 (20 W) | Xiegu G1M or Hambuilder HBR4HFS |
| **Antenna** | DIY EFHW or random wire + 9:1 | DIY wire only |

---

## 1. Transceiver (Emitter / Field station)

CAT-capable HF (and optionally 50 MHz) transceiver for the Radio TX agent and Hamlib.

| # | Model | Where | Link | Notes |
|---|--------|------|------|--------|
| 1 | **Icom IC-7300** | Passion Radio (France) | https://www.passion-radio.com/hf-transceiver/ic7300-1110.html | EUR, ships France; 100W HF+50MHz SDR, USB, built-in tuner. |
| 2 | **Icom IC-7300** | Radioworld UK | https://www.radioworld.co.uk/icom-ic-7300 | GBP, worldwide shipping; same radio. |
| 3 | **Icom IC-7300** | Ham Radio Outlet (US) | https://www.hamradio.com/detail.cfm?pid=71-002065 | USD; confirm international shipping or use forwarder. |
| 4 | **Yaesu FT-891** | Passion Radio (France) | https://www.passion-radio.com/ham-radio-equipment/ft891-461.html | EUR, France; 100W compact mobile/base. |
| 5 | **Yaesu FT-891** | Radioworld UK | https://www.radioworld.co.uk/yaesu-ft-891 | GBP, worldwide; often “ship to France” option. |
| 6 | **Yaesu FT-891** | Ham Radio Outlet (US) | https://www.hamradio.com/detail.cfm?pid=71-002216 | USD; confirm international or forwarder. |
| 7 | **Icom IC-7300MK2** | Passion Radio (France) | https://www.passion-radio.com/hf-transceiver/ic7300mk2-3083.html | EUR; updated 7300, HDMI/USB-C. |
| 8 | **Xiegu G90** | WIMO (Germany) | https://www.wimo.com/en/xiegu-g90 | EUR, EU shipping; 20W portable, built-in tuner, budget option. |
| 9 | **Xiegu G90** | Xiegu.eu | https://xiegu.eu/product/xiegu-g90-hf-20w-sdr-transceiver | EUR; official EU distributor, ships to France. |

**Recommendation:** For “pay in USD”: use **Ham Radio Outlet** (or DX Engineering / GigaParts) with a US forwarder. For “no forwarder”: **Passion Radio** or **Radioworld UK** (PayPal often lets you choose currency).

---

## 2. RTL-SDR Dongle (Receiver station)

RTL-SDR Blog V3 or V4 for `remote_receiver` (pyrtlsdr). Prefer **V3** for maximum software compatibility (e.g. older guides); **V4** has HF upconverter and is also supported.

| # | Product | Where | Link | Notes |
|---|---------|--------|------|--------|
| 1 | **RTL-SDR Blog V3** (dongle + antenna kit) | RTL-SDR official (eBay) | https://www.ebay.com/str/rtlsdrblog | USD; EU customers use eBay (VAT handled by eBay). |
| 2 | **RTL-SDR Blog V3/V4** | AliExpress FR (official store) | https://fr.aliexpress.com/store/1101427871 | Store ID 1101427871; EUR/local; VAT via AliExpress; fast to France. |
| 3 | **RTL-SDR Blog V4** (TCXO, Bias-T, R828D) | Passion Radio (France) | https://www.passion-radio.com/rtl-sdr-stick/r828d-v4-2402.html | EUR, France; 500 kHz–1766 MHz. |
| 4 | **RTL-SDR Blog V3** (dongle only) | SDRStore.eu (Germany) | https://www.sdrstore.eu/software-defined-radio/instruments/rtl-sdr/rtl-sdr-blog-rtl-sdr-v3-r820t2-rtl2832u-1ppm-tcxo-sma-rtlsdr-software-defined-radio-dongle-only-en/ | EUR; EU shipping. |

**Official RTL-SDR shop (non-EU):** https://www.rtl-sdr.com/shop/ — for non-EU only; EU must use eBay/AliExpress or local resellers (VAT).

---

## 3. Raspberry Pi 4 (4GB) — Receiver host

For running `remote_receiver` (FastAPI, pyrtlsdr, auth, HQ client).

| # | Where | Link | Notes |
|---|--------|------|--------|
| 1 | **Kubii** (France, official Pi distributor) | https://www.kubii.com/en/nano-computers/2772-raspberry-pi-4-model-b-4gb-5056561800349.html | EUR; France/EU; free delivery from €75. |
| 2 | **Kiwi Electronics** (EU) | https://www.kiwi-electronics.com/en/raspberry-pi-4-model-b-4gb-4268 | EUR; competitive price; EU shipping. |
| 3 | **Pimoroni** (UK) | https://shop.pimoroni.com/products/raspberry-pi-4 | GBP; EU plug option; ships to France. |
| 4 | **Amazon.fr** | Search “Raspberry Pi 4 4 Go” | EUR; check seller is official/trusted; fast delivery in France. |

---

## 4. Antenna (Emitter and/or Receiver)

One option per style; pick by band (HF vs VHF/UHF) and space.

| # | Type | Where | Link | Notes |
|---|------|--------|------|--------|
| 1 | **EFHW 40–10 m** (end-fed half wave) | MyAntennas (EU) | https://myantennas.com/wp/product/efhw-4010-1k-icas/ | EUR; 40/20/15/10 m; 1 kW; EU shipping. |
| 2 | **EFHW 80–10 m** | MyAntennas (EU) | https://myantennas.com/wp/product/efhw-8010/ | EUR; 80–10 m; check shop opening (they had a temporary closure). |
| 3 | **OCF dipole 80–6 m** | CommsDepot (US) | https://commsdepot.com/product/80-6m-100w-hf-ham-radio-antenna-ocf-off-center-fed-dipole-n9sab-free-shipping/ | USD; US free ship; to France use forwarder. |
| 4 | **HF antennas** (various) | Passion Radio (France) | https://www.passion-radio.com/ (search “antenne HF” or “antenna”) | EUR; France; multiple brands. |
| 5 | **HF / VHF antennas** | Radioworld UK | https://www.radioworld.co.uk/ (antenna section) | GBP; worldwide shipping. |

For **RTL-SDR only**: RTL-SDR Blog dipole kit (with V3/V4 bundle) or any simple VHF/UHF antenna (e.g. telescopic/dipole from Passion Radio, SDRStore, or Amazon.fr).

---

## 5. USB–serial cable (if transceiver has no USB)

Only if your rig has serial CAT (e.g. CI-V, Yaesu) and no built-in USB.

| # | Where | Link | Notes |
|---|--------|------|--------|
| 1 | **Amazon.fr** | Search “câble USB serial FTDI” or “USB to serial adapter” | EUR; FTDI or Prolific; France delivery. |
| 2 | **Passion Radio** | https://www.passion-radio.com/ (accessories / câbles) | EUR; often rig-specific cables. |
| 3 | **Radioworld UK** | https://www.radioworld.co.uk/ (cables / interfaces) | GBP; international shipping. |
| 4 | **Amazon.com** (via forwarder) | Search “USB to serial FTDI” | USD; use US forwarder for France. |

---

## 6. Power supply (Raspberry Pi)

5 V, 3 A USB-C (official or equivalent), EU plug for France.

| # | Where | Link | Notes |
|---|--------|------|--------|
| 1 | **Pimoroni** (with Pi or kit) | https://shop.pimoroni.com/products/raspberry-pi-4-essentials-kit | GBP; EU plug option; includes Pi, PSU, case, microSD. |
| 2 | **Kubii** | https://www.kubii.com/ (search “alimentation Raspberry Pi 4”) | EUR; official or compatible 5V 3A USB-C. |
| 3 | **Amazon.fr** | Search “alimentation officielle Raspberry Pi 4” or “Raspberry Pi 4 power supply” | EUR; prefer official or well-reviewed 5V 3A. |
| 4 | **Kiwi Electronics** | https://www.kiwi-electronics.com/ (Raspberry Pi power) | EUR; EU plug. |

---

## 7. MicroSD card (32 GB+ Class 10) — Receiver

For Raspberry Pi OS and `remote_receiver` software.

| # | Where | Link | Notes |
|---|--------|------|--------|
| 1 | **Amazon.fr** | Search “microSD 32 Go Class 10” (e.g. SanDisk, Samsung) | EUR; 32 GB or 64 GB; Class 10 or A1/A2. |
| 2 | **Kubii** | https://www.kubii.com/ (microSD Raspberry) | EUR; often sold with Pi. |
| 3 | **Pimoroni** | Included in Essentials Kit or buy separately | GBP; reliable cards. |
| 4 | **Amazon.com** (via forwarder) | Search “SanDisk 32GB microSD Class 10” | USD; use forwarder for France. |

---

## 8. Optional: USB sound card (digital modes / receiver)

For FLDIGI/WSJTX/Direwolf with a rig (audio in/out PC ↔ rig). Many modern rigs have built-in USB audio; add this if not.

| # | Where | Link | Notes |
|---|--------|------|--------|
| 1 | **Amazon.fr** | Search “carte son USB externe” (e.g. Behringer UCA202, Sabrent) | EUR; simple stereo USB; France. |
| 2 | **Passion Radio** | https://www.passion-radio.com/ (interfaces / sound) | EUR; sometimes ham-oriented interfaces. |
| 3 | **Radioworld UK** | https://www.radioworld.co.uk/ (sound card / interface) | GBP; international shipping. |
| 4 | **Amazon.com** (via forwarder) | Search “USB sound card Behringer” | USD; use forwarder. |

---

## Quick “by role” lists

**Emitter only (field, pay in USD when possible)**  
- Transceiver: Ham Radio Outlet (US) + forwarder, or Radioworld UK / Passion Radio (PayPal in USD if offered).  
- Antenna: MyAntennas or Passion Radio.  
- Cable: Passion Radio or Amazon.fr.

**Receiver only (remote station in France)**  
- RTL-SDR: Passion Radio or AliExpress FR (official store).  
- Raspberry Pi 4: Kubii or Kiwi Electronics.  
- PSU + microSD: Kubii, Pimoroni, or Amazon.fr.

**Full link (emitter + receiver)**  
- Combine one option from each section above; prefer French/EU vendors for receiver to avoid customs; use US + forwarder for transceiver if you want to pay in USD.

---

## Cost estimate: example station (France)

Rough total for a **station principale** + **station portable** as specified below. Prices in EUR (TTC / incl. when known), France or EU retailers; used where noted. Adjust for current availability and promotions.

### Station principale

| Item | Description | Estimated price (EUR) |
|------|-------------|------------------------|
| **Icom IC-7300** | HF + 50 MHz SDR, 100 W, tuner intégré | ~1 295 – 1 350 |
| **LDG AT-100Pro II** | Autotuner 1–125 W, 160–6 m | ~305 – 365 |
| **Diamond HF-40-cl** | Antenne 40 m mobile/base | ~67 |
| **Dipole 20 m** | 2 × 5 m en V à plat (balcon) — fil + connecteurs/balun | ~20 – 60 (DIY) |
| **End-fed verticale 15 m** | Verticale fil 15 m | ~30 – 80 (DIY / kit) |
| **ML-145 retaillée 10 m** | Sirio ML-145 (CB/10 m) coupée pour 10 m | ~60 – 85 |
| **TYT TH-9800** | Quad 10/6/2 m/70 cm, 50 W | ~250 – 320 |
| **Diamond X30** | Verticale 144/430 MHz | ~56 |
| **Nissei NS-1230D** | Alimentation 13,8 V 25–30 A | ~155 – 176 * |
| **Sous-total station principale** | | **~2 238 – 2 767** |

\* Nissei NS-1230D parfois en rupture (Passion Radio) ; alternative NS-30SD ou NS-1230M ~155 €.

### Station portable

| Item | Description | Estimated price (EUR) |
|------|-------------|------------------------|
| **Yaesu FT-450D** | HF 100 W, ATU intégré (occasion) | ~400 – 650 |
| **Yaesu SCU-17** | Interface USB CAT + son pour FT-450D | ~129 |
| **Yaesu ATAS-120** | Antenne auto-tune HF/VHF/UHF | ~295 – 380 |
| **End-fed verticale portable** | Un fil par bande (20 m, 15 m) | ~30 – 70 (DIY / kit) |
| **Yaesu FT-817ND** | QRP HF/VHF/UHF (occasion) | ~400 – 500 |
| **End-fed verticale QRP** | Un fil par bande | ~20 – 50 (DIY) |
| **Spiderbeam mat 10 m** | Mât télescopique alu 10 m (portable ou HD) | ~499 |
| **Sous-total station portable** | | **~1 773 – 2 229** |

### Total estimé (ensemble des deux stations)

| | EUR (arrondi) |
|--|----------------|
| **Station principale** | **~2 250 – 2 770** |
| **Station portable** | **~1 770 – 2 230** |
| **Total** | **~4 020 – 5 000** |

- Fourchettes hautes = neuf + antennes commerciales ; basses = occasion (FT-450D, FT-817ND) + DIY antennes.
- Câbles, connecteurs, support du dipole 20 m et petit matériel non détaillés : compter ~50 – 150 € en plus.

---

*Document generated for SHAKODS; links checked as of 2025. Verify shipping and payment options on each site before ordering.*
