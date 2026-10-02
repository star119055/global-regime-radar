# Shadow Mode — 2026-10-02T05:56:39.190270+00:00

**Status:** PENDING_DATA
**Dataset:** `98c1e818c89da074dfe9500067f29201527ca3c18443e5ce0dd95a2112a4ed80`
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
| A | 0.500 | 0.499 | 0.500 | 0.001 |
| B | 0.560 | 0.609 | 0.635 | 0.075 |
| C1 | 0.500 | 0.500 | 0.500 | 0.000 |
| C2 | 0.500 | 0.500 | 0.500 | 0.000 |
| C3 | 0.560 | 0.637 | 0.606 | 0.077 |
| D | 0.338 | 0.508 | 0.410 | 0.170 |
