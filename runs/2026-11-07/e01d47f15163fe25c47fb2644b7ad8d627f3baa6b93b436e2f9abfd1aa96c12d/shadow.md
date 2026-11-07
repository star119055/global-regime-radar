# Shadow Mode — 2026-11-07T06:18:17.160018+00:00

**Status:** PENDING_DATA
**Dataset:** `6da44ae902e10853b88e88e9ed1f709fdcae2fef5cc9e533c853e3a846c4cbe6`
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
| A | 0.500 | 0.495 | 0.537 | 0.041 |
| B | 0.559 | 0.573 | 0.591 | 0.032 |
| C1 | 0.500 | 0.500 | 0.500 | 0.000 |
| C2 | 0.500 | 0.500 | 0.500 | 0.000 |
| C3 | 0.551 | 0.629 | 0.588 | 0.078 |
| D | 0.430 | 0.506 | 0.407 | 0.099 |
