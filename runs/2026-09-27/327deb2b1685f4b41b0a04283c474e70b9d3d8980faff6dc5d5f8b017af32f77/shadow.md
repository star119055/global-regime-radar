# Shadow Mode — 2026-09-27T11:39:09.427558+00:00

**Status:** PENDING_DATA
**Dataset:** `5548d278f3aa60fbd653d55b8d72f8701dce8c278a13d128b1d686c3597efa13`
**Config:** `27595ddfeac277d556532c465da7c31e674d2dfe8d25f63979bde0fa23d3423d`
**Feature set:** `live-v4`

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
- source:lbnl_queued_up:HTTPError:HTTP Error 403: Forbidden
- A:coverage=0.000<0.400
- C1:coverage=0.000<0.400
- C2:coverage=0.000<0.400
- C3:coverage=0.333<0.400

## Engine comparison
| State | Baseline0 | Baseline1 | UKF | Max spread |
|---|---:|---:|---:|---:|
| A | 0.500 | 0.500 | 0.500 | 0.000 |
| B | 0.601 | 0.601 | 0.627 | 0.026 |
| C1 | 0.500 | 0.500 | 0.500 | 0.000 |
| C2 | 0.500 | 0.500 | 0.500 | 0.000 |
| C3 | 0.637 | 0.637 | 0.649 | 0.012 |
| D | 0.509 | 0.509 | 0.511 | 0.002 |
