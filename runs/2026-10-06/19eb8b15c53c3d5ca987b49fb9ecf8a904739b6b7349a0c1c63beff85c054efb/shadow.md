# Shadow Mode — 2026-10-06T06:36:54.175457+00:00

**Status:** PENDING_DATA
**Dataset:** `1c31583610ae1bbe1b41de9bf873a11b6cc9b15be71dbd972cbb306d19094df5`
**Config:** `27595ddfeac277d556532c465da7c31e674d2dfe8d25f63979bde0fa23d3423d`
**Feature set:** `live-v5`

> Diagnostic only — not promotion-eligible while required state coverage is incomplete.

## Missing requirements
- A:apcr_did:missing
- A:llier:missing
- A:geoi:missing
- B:dealer_balance_sheet:missing
- C1:hormuz_disruption:missing
- C1:crop_balance:missing
- C1:hydro_gas:missing
- C2:external_debt_stress:missing
- C2:reserve_adequacy:missing
- C2:fx_stress:missing
- C3:transformer_lead_time:missing
- D:regulatory_intervention:missing
- D:asset_gap:missing
- A:coverage=0.000<0.400
- C1:coverage=0.000<0.400
- C2:coverage=0.000<0.400

## Engine comparison
| State | Baseline0 | Baseline1 | UKF | Max spread |
|---|---:|---:|---:|---:|
| A | 0.500 | 0.499 | 0.519 | 0.021 |
| B | 0.446 | 0.585 | 0.600 | 0.155 |
| C1 | 0.500 | 0.500 | 0.500 | 0.000 |
| C2 | 0.500 | 0.500 | 0.500 | 0.000 |
| C3 | 0.560 | 0.636 | 0.602 | 0.076 |
| D | 0.448 | 0.507 | 0.400 | 0.107 |
