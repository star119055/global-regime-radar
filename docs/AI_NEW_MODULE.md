# AI / GPU / Private-Credit New Module

The AI module is deliberately switchable and is disabled by default in the Core Model.

Its purpose is to test whether modern AI capital-cycle variables add information after
the older financial and macro system has already been evaluated.

## 1. APCR

The authoritative APCR candidate uses a **frozen baseline-treatment
Difference-in-Differences contract**:

```text
Productivity(i,t)
  = intercept
  + beta * (BaselineAIIntensity(i) * Post(t))
  + entity fixed effects
  + period fixed effects
  + error
```

`BaselineAIIntensity(i)` is fixed once per matched NAICS entity from the
approved Census BTOS baseline window. It is not allowed to vary mechanically
with the outcome period.

This corrects an important identification ambiguity in the original prototype.
Using contemporaneous `AIIntensity(i,t) * Post(t)` would be a fixed-effects
interaction/association unless a separate treatment assignment design were
defined; the authoritative APCR path does not label that construction as DiD.

The reported quantity is `beta`, an **interaction coefficient**, not proof of
causal AI productivity. Parallel trends, treatment measurement, composition
effects and other identification assumptions remain separate validation gates.

The initial source contract is:

- treatment: Census BTOS current AI-use share by common two-digit NAICS sector;
- outcome: BLS Detailed Industry Productivity annual labor productivity;
- pre outcomes: at least two annual periods before `post_start_year`;
- post outcomes: at least one annual period;
- every entity must have both pre and post outcomes;
- current revised BLS history cannot be silently used as a historical
  point-in-time vintage.

The BTOS core AI wording changed on November 17, 2025 from AI use in
"producing goods or services" to AI use in "any business function". Census
created a new time series because a level shift accompanied the change.
Therefore those regimes are explicitly distinct and cannot be pooled into the
frozen treatment baseline.

The executable contract is stored in `config/apcr_panel.yaml`. APCR remains
Missing in live A until the panel, release vintages, beta-to-activation
normalization and prospective validation gates all pass.

### APCR candidate diagnostics

Once the frozen BTOS treatment panel and the BLS Major Industry current
productivity snapshot are complete, the research probe may estimate a
non-authoritative APCR candidate.

The candidate must report:

- the full two-way fixed-effect interaction coefficient;
- its equivalent effect per +10 percentage points of baseline AI share;
- leave-one-sector-out coefficients for every aligned sector;
- a pre-period placebo using only 2021-2023 with 2023 as pseudo-post;
- the absolute placebo/main beta ratio;
- all promotion blockers.

The current BLS API history is a revised snapshot, not a historical
point-in-time vintage. A positive coefficient is therefore not enough to enable
A. In particular, a material pre-period placebo is evidence that sector-specific
trends may be confounding the treatment interaction.

No placebo threshold or beta-to-activation mapping is frozen at this stage.

The next deconfounding diagnostic estimates a separate 2021-2023 linear
productivity trend for every sector. It then evaluates 2024 in two equivalent
ways:

1. extrapolate each sector's pretrend to 2024 and regress the actual-minus-
   predicted residual on frozen baseline AI intensity;
2. fit the full panel with entity fixed effects, year fixed effects and
   entity-specific linear trends.

Those two trend-adjusted coefficients must agree numerically. The probe also
reports the correlation between baseline AI intensity and pre-period sector
productivity trends. A large correlation, or a sharp collapse from the raw beta
to the trend-adjusted beta, is treated as evidence of confounding rather than
as something to tune away.

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


## 7. BTOS AI research context sidecar

The 2026 Census BTOS AI supplement is retained prospectively as **research
context**, not as a substitute for APCR-DiD.

The frozen sidecar currently records:

- 18% firm-weighted AI use;
- 32% employment-weighted AI use;
- 22% expected firm use within six months;
- unconditional firm-weighted `Sintegration = 0.053`;
- unconditional firm-weighted `Simpact = 0.043`;
- unconditional firm-weighted `Sinvest = 0.030`.

The registry is conservatively gated at the June 18, 2026 BTOS supplemental
data release. Historical decisions before that timestamp cannot use the
snapshot.

The Census paper defines `Simpact` as realized impact intensity and
`Sinvest` as operational investment depth. Neither is a Difference-in-
Differences productivity contribution estimate. The paper also treats the
reported performance associations as descriptive rather than causal.

Therefore the sidecar has:

```text
authoritative_state_input = false
A_coverage_increment = 0
blocked_indicator_keys = [apcr_did, llier, geoi]
```

This keeps observational context visible without double counting it into the
A state. A genuine APCR-DiD pipeline must still combine point-in-time AI
adoption treatment data with productivity outcomes under an explicit panel
identification contract.


## 8. LLIER large-load execution candidate

LLIER is a separate A-state candidate from APCR.

Its authoritative form is cohort-based:

```text
LLIER(c,h)
  = baseline MW from cohort c observed energized by horizon h
    / eligible baseline MW in cohort c
```

Current ERCOT public monthly queue reports are retained as research context
only. They publish useful aggregate status buckets, but aggregate MW cannot show
that the same projects moved between stages.

Therefore the current source boundary remains:

```text
llier authoritative_state_input = false
A_coverage_increment = 0
```

The executable contract is frozen in `config/llier.yaml`. Promotion requires
stable project identity, repeatable project-level status history, a predeclared
cancellation/withdrawal policy, and explicit handling of the July 2026 ERCOT
LLIS-to-Batch-Zero process break.
