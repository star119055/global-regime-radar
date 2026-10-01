# Shadow Mode — 2026-10-01T06:13:26.737798+00:00

**Status:** PENDING_DATA
**Dataset:** `27e4e76b3751526fd3d5eb0bbe8ecc59c3a7a6c4a81a20681c0c5d09b5bf6031`
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
| A | 0.500 | 0.499 | 0.498 | 0.002 |
| B | 0.696 | 0.612 | 0.638 | 0.084 |
| C1 | 0.500 | 0.500 | 0.500 | 0.000 |
| C2 | 0.500 | 0.500 | 0.500 | 0.000 |
| C3 | 0.560 | 0.637 | 0.607 | 0.077 |
| D | 0.336 | 0.508 | 0.416 | 0.173 |
