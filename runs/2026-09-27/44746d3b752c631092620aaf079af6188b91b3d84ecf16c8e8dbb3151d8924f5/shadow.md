# Shadow Mode — 2026-09-27T11:13:26.875598+00:00

**Status:** PENDING_DATA
**Dataset:** `19085786417b88e1c02697e0ef5f9bb5bb8fb8a0cc8e2434d4e4ab532c9e6538`
**Config:** `27595ddfeac277d556532c465da7c31e674d2dfe8d25f63979bde0fa23d3423d`
**Feature set:** `live-v3`

> Diagnostic only — not promotion-eligible while required state coverage is incomplete.

## Missing requirements
- A:apcr:missing
- A:llier:missing
- A:ai_capital_cycle:missing
- B:dealer_balance_sheet:missing
- C1:hormuz_disruption:missing
- C1:crop_balance:missing
- C1:hydro_gas:missing
- C2:external_debt_stress:missing
- C2:reserve_adequacy:missing
- C2:fx_stress:missing
- C3:transformer_lead_time:missing
- C3:interconnection_execution:missing
- D:regulatory_intervention:missing
- D:asset_gap:missing
- A:coverage=0.000<0.400
- C1:coverage=0.000<0.400
- C2:coverage=0.000<0.400
- C3:coverage=0.333<0.400

## Engine comparison
| State | Baseline0 | Baseline1 | UKF | Max spread |
|---|---:|---:|---:|---:|
| A | 0.500 | 0.500 | 0.500 | 0.000 |
| B | 0.601 | 0.601 | 0.606 | 0.005 |
| C1 | 0.500 | 0.500 | 0.500 | 0.000 |
| C2 | 0.500 | 0.500 | 0.500 | 0.000 |
| C3 | 0.637 | 0.637 | 0.608 | 0.030 |
| D | 0.509 | 0.509 | 0.508 | 0.001 |
