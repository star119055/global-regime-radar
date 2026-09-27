# V6.1 Implementation Specification

## 1. Non-negotiable invariants

- Backtests must select only observations with `available_at <= decision_time`.
- Missing observations remain missing and must never be coerced to zero.
- Staleness increases measurement variance; it must not mechanically pull a macro state toward zero.
- Raw features, indicators and latent states are separate layers.
- A raw feature can feed multiple indicators, but duplicated contribution to the same latent state must be prevented by attribution groups.
- Revised values cannot be used before their historical publication time.

## 2. Signal model

For observation `i` with half-life `tau_i`:

`freshness_i = exp(-ln(2) * age_i / tau_i)`

The value itself remains the standardized observation. Freshness and source confidence control measurement uncertainty:

`measurement_variance_i = base_variance_i / max(freshness_i * confidence_i, epsilon)`

## 3. Implementation phases

### PR-D1 Data Contract
Schema, source registry, vintage rules, missing-data contract, publication-lag contract and no-look-ahead tests.

### PR-D2 Financial Core ETL
Treasury auction, NY Fed, OFR/CFTC and real-yield sources.

### PR-D3 Stress Engine V0
Funding, price discovery and intermediation sub-states plus L1-L4 hysteresis.

### PR-D4 Macro / Physical ETL
NOAA, USDA, EIA, interconnection queues, QRA, IMF/QEDS.

### PR-D5 Walk-Forward Harness
Dataset hashing, parameter freeze, sensitivity tests, publication lag, revision lag and 20% missing-data stress test.

### PR-D6 AI New Module
APCR, GEOI and enhanced PCCB. Validate only for periods with real data.

## 4. Backtest universes

- Core-1: 2006-2009
- Core-2: 2010-2019
- Core-3: 2020-2023
- New-Module: 2024-2026

Feature availability is versioned. Newer features must not be synthesized into older periods.

## 5. Evaluation

Primary metrics:

- Episode recall
- False-alarm episodes per year
- Median lead time
- Time in warning
- State transition count
- State dwell time
- Monotonicity of future stress conditional on state intensity
- Missing-data robustness

Do not call activation intensity "probability calibration" unless a separate probabilistic crisis mapping is explicitly estimated.
