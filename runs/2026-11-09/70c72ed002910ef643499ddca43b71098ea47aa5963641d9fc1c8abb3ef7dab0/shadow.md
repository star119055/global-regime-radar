# Shadow Mode — 2026-11-09T06:56:53.595488+00:00

**Status:** PENDING_DATA
**Dataset:** `ba720e43e942deb22cbbadb58ef1a4efd2ca03df89e6981833496f12c5a5b9d8`
**Config:** `27595ddfeac277d556532c465da7c31e674d2dfe8d25f63979bde0fa23d3423d`
**Feature set:** `live-v5`

> Diagnostic only — not promotion-eligible while required state coverage is incomplete.

## Missing requirements
- A:apcr_did:missing
- A:llier:missing
- A:geoi:missing
- B:auction_quality_stress:missing
- B:auction_dealer_takedown_stress:missing
- B:dealer_balance_sheet:missing
- C1:hormuz_disruption:missing
- C1:crop_balance:missing
- C1:hydro_gas:missing
- C2:external_debt_stress:missing
- C2:reserve_adequacy:missing
- C2:fx_stress:missing
- C3:transformer_lead_time:missing
- D:issuance_duration:missing
- D:regulatory_intervention:missing
- D:asset_gap:missing
- source:treasury_auctions:ValueError:could not convert string to float: 'null'
- A:coverage=0.000<0.400
- C1:coverage=0.000<0.400
- C2:coverage=0.000<0.400
- D:coverage=0.250<0.400

## Engine comparison
| State | Baseline0 | Baseline1 | UKF | Max spread |
|---|---:|---:|---:|---:|
| A | 0.500 | 0.495 | 0.535 | 0.040 |
| B | 0.559 | 0.574 | 0.595 | 0.036 |
| C1 | 0.500 | 0.500 | 0.500 | 0.000 |
| C2 | 0.500 | 0.500 | 0.500 | 0.000 |
| C3 | 0.551 | 0.629 | 0.587 | 0.078 |
| D | 0.430 | 0.506 | 0.405 | 0.101 |
