# Shadow Mode — 2026-10-25T05:00:07.938556+00:00

**Status:** PENDING_DATA
**Dataset:** `932540464988e470eb90e2247334151fbf744d182430b5ce50a7eae873122bbc`
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
- C3:capex_deflator:missing
- D:regulatory_intervention:missing
- D:asset_gap:missing
- source:bls_transformer_ppi:HTTPError:HTTP Error 503: Service Unavailable
- source:bls_switchgear_ppi:HTTPError:HTTP Error 503: Service Unavailable
- A:coverage=0.000<0.400
- C1:coverage=0.000<0.400
- C2:coverage=0.000<0.400
- C3:coverage=0.333<0.400

## Engine comparison
| State | Baseline0 | Baseline1 | UKF | Max spread |
|---|---:|---:|---:|---:|
| A | 0.500 | 0.497 | 0.538 | 0.041 |
| B | 0.666 | 0.568 | 0.579 | 0.097 |
| C1 | 0.500 | 0.500 | 0.500 | 0.000 |
| C2 | 0.500 | 0.500 | 0.500 | 0.000 |
| C3 | 0.422 | 0.632 | 0.592 | 0.210 |
| D | 0.539 | 0.506 | 0.413 | 0.126 |
