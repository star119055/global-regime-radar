# AI / GPU / Private-Credit New Module

The AI module is deliberately switchable and is disabled by default in the Core Model.

Its purpose is to test whether modern AI capital-cycle variables add information after
the older financial and macro system has already been evaluated.

## 1. APCR

APCR is implemented as a continuous-treatment Difference-in-Differences regression with
entity and period fixed effects:

```text
Productivity(i,t)
  = intercept
  + beta * (AIIntensity(i,t) * Post(t))
  + entity fixed effects
  + period fixed effects
  + error
```

The reported quantity is `beta`.

The implementation calls it an **interaction coefficient**, not proof of causal AI
productivity. Parallel trends, treatment measurement, composition effects and other
identification assumptions must still be tested separately.

The project gates APCR to September 11, 2023 or later because that is the first BTOS
collection period used here for public enterprise AI-adoption measurement. BLS provides
the productivity side through its public productivity databases/API.

## 2. GEOI

The frozen formula is:

```text
GEOI =
    0.40 * Z(change in performance / dollar)
  - 0.35 * Z(change in old-GPU rental yield)
  - 0.25 * Z(change in secondary GPU price)
```

A decline in rental yield or secondary price therefore raises GEOI.

**No dynamic reweighting is allowed.** If any of the three components is missing, GEOI is
Missing. This avoids turning a three-leg credit bridge into a different model whenever a
data vendor fails.

MLPerf can anchor benchmark performance, but the open-source core does not pretend that a
single authoritative public historical database exists for GPU rental yields and
secondary-market prices. Those legs require explicit external vintages.

MLCommons also notes that published benchmark results can later be modified or
invalidated, so the project preserves release artifacts rather than rebuilding old inputs
from a current dashboard.

## 3. GPU collateral bridge

The simplest transparent bridge from residual value to credit stress is balance-sheet
arithmetic:

```text
stressed_LTV = initial_LTV / (1 + collateral_price_change)
```

For example, a 50% fall in collateral value doubles LTV if debt is unchanged.

This bridge does not assume that every AI loan is GPU-collateralized. It is applied only
to exposures where the collateral linkage is evidenced.

## 4. PCCB

The frozen enhanced Private Credit Composite Basket is:

```text
PCCB =
    0.35 * Z(non-accrual)
  + 0.25 * Z(PIK)
  + 0.25 * Z(NAV markdown)
  + 0.15 * Z(gates)
```

All four components are required. Missing is not silently reweighted.

SEC EDGAR filing artifacts are the primary open raw-document layer. Companyfacts can help
with standardized XBRL facts, but this repository does not assume that non-accrual, PIK,
NAV markdown and redemption/gate disclosures map to one universal XBRL concept across
BDCs, interval funds and private vehicles.

Federal Reserve Financial Stability Reports are useful aggregate corroboration. They are
not substituted for vehicle-level raw PCCB observations.

## 5. Historical discipline

The New Module may not leak backward into Core-1/Core-2/Core-3.

Project gates:

```text
APCR: 2023-09-11, New Module only
GEOI: 2024-01-01, New Module only
PCCB enhanced: 2024-01-01, New Module only
```

The 2024 dates are conservative project validation boundaries, not claims about when the
underlying benchmark or filing systems first existed.

## 6. Evaluation

Every experiment must produce matched Core-only and Core+AI runs with the same evaluation
metric keys. The comparison layer reports metric deltas but does not declare the AI
module “better” from one score alone.

Promotion into the default model requires stable incremental value across walk-forward
folds, sensitivity tests and missing-data stress tests.
