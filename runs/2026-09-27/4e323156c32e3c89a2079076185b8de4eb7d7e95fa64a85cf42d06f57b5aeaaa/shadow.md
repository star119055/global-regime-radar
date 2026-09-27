# Shadow Mode — 2026-09-27T11:20:30.599156+00:00

**Status:** PENDING_DATA
**Dataset:** `41e281a0f5c4f0a0fc81708a594e8685754509b7f037f6e03d6da0fcd1fb037c`
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
| B | 0.637 | 0.601 | 0.625 | 0.036 |
| C1 | 0.500 | 0.500 | 0.500 | 0.000 |
| C2 | 0.500 | 0.500 | 0.500 | 0.000 |
| C3 | 0.637 | 0.637 | 0.630 | 0.008 |
| D | 0.509 | 0.509 | 0.510 | 0.001 |
