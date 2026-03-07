# Compliance and regulatory references

This page documents the regulatory sources used by the compliance plugin for restricted bands and band plans. **Operators are responsible for verifying national rules** (e.g. ANFR, Ofcom, ACMA, IFT).

---

## Backend overview

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

---

## FCC (United States)

- **Rule:** 47 CFR §15.205 — Restricted bands of operation.
- **Meaning:** Intentional radiators must not operate in the listed bands; only spurious emission limits (§15.209) apply.
- **Source:** Code of Federal Regulations, title 47, chapter I, subchapter A, part 15, subpart C, section 15.205. The list in code is maintained from the official eCFR/Cornell text.

---

## CEPT / EU (France, UK, Spain, etc.)

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

---

## Band plans

- **ITU Region 2 (Americas):** Default in `bands.py`; 2m 144–148 MHz, 70cm 420–450 MHz.  
  [IARU R2 band plans](https://www.iaru-r2.org/en/reference/band-plans/).

- **ITU Region 1 (Europe, Africa, Middle East):** 2m 144–146 MHz, 70cm 430–440 MHz.  
  [IARU R1 band plans](https://www.iaru-r1.org/on-the-air/band-plans/).

- **ITU Region 3 (Asia–Pacific):** IARU R3 band plan: 2m 144–148 MHz, 70cm 430–440 MHz (secondary in R3; 440–450 only in Australia/Philippines per RR 5.270). Used by **ITU_R3** and **AU** backends. [IARU R3-004 (2019)](https://www.iaru.org/).

---

## Country → backend mapping

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
