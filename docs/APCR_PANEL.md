# APCR Panel Contract v1

APCR is the first candidate authoritative input for state A.

It is intentionally separated into three layers:

1. source evidence;
2. aligned panel and interaction-coefficient estimation;
3. beta-to-state activation.

Only layers 1 and 2 are defined here. Layer 3 remains disabled.

## Identification

The frozen specification is:

```text
Productivity(i,t)
  = alpha(i)
  + lambda(t)
  + beta * BaselineAIIntensity(i) * Post(t)
  + error(i,t)
```

The treatment intensity is fixed once for each entity. A time-varying
contemporaneous adoption rate is rejected by the authoritative validator.

The reported beta is an interaction coefficient. The repository does not infer
a causal productivity effect from beta alone.

## Entity and frequency alignment

The intended common entity is a two-digit NAICS sector that exists in both:

- Census BTOS sector estimates; and
- BLS Detailed Industry Productivity.

BTOS is biweekly while the selected BLS productivity outcome is annual.
Therefore BTOS observations must first be aggregated into a frozen treatment
baseline. They are never forward-filled as annual productivity observations.

The current minimum panel contract requires:

- at least four aligned sectors;
- at least two pre outcome years;
- at least one post outcome year;
- a pre and post outcome for every included entity;
- cross-entity variation in frozen treatment intensity;
- no duplicate entity-year rows;
- a full-rank fixed-effects design.

## BTOS measurement break

The original AI question asked whether the business used AI in producing goods
or services. Beginning November 17, 2025, Census changed the wording to use in
any business function and created a new time series after observing a level
shift.

The v1 baseline contract accepts only the original wording regime.
The new series may be modeled later as a distinct measurement regime, but it
cannot silently alter an entity's frozen treatment intensity.

## Point-in-time discipline

Every aligned row must retain both:

- a BTOS treatment vintage ID;
- a BLS productivity vintage ID.

For live research, a current BLS snapshot can be used to investigate the
contract. For historical walk-forward evaluation, an archived release artifact
is required. A current revised BLS history must not be backdated into an older
decision time.

## State activation gate

A valid beta does not automatically become a state-A activation.

`apcr_did` remains Missing until all of these are frozen and passed:

- panel validation;
- point-in-time source completeness;
- beta-to-0..1 activation normalization;
- prospective validation.

Until then, A coverage increment from APCR is exactly zero.


## Frozen BTOS treatment baseline

The authoritative treatment candidate uses BTOS periods 31–36, covering
September 11 through December 3, 2023.

Only national two-digit NAICS total estimates are eligible:

- `STATE` must be empty;
- `MSA` must be empty;
- `EMPSIZE` must be empty;
- `NAICS2` must be a concrete two-digit sector;
- the response must be the current-AI-use “Yes” estimate under the original
  “producing goods or services” wording.

Every included sector must have exactly one eligible row in every baseline
period 31–36. Missing periods are not imputed.

The frozen treatment intensity is the simple arithmetic mean of the six
percentage estimates, converted to a 0..1 share. Standard errors are retained
as source metadata but are not used as inverse-variance weights for the
baseline point estimate, because adjacent BTOS waves are not assumed to be
independent samples.

The probe may emit this as a frozen **candidate**, but APCR remains non-live
until BLS outcome alignment, point-in-time vintage completeness,
beta-normalization, and prospective validation all pass.


### Incomplete sector handling

A NAICS2 sector is eligible for the frozen treatment set only when all six
baseline periods 31–36 are present. A sector with one or more missing waves is
excluded from the candidate treatment universe and reported with the exact
missing period IDs.

No period is imputed, forward-filled, or replaced with a neighboring sector.
The panel-level minimum entity gate is applied only after this explicit
complete-case treatment selection.


## BLS live-research outcome transport

The legacy BLS industry-productivity text-file host is retained as research
metadata but is not relied on by GitHub Actions because that host can reject
cloud runners.

The live APCR source probe instead validates candidate annual labor-productivity
series through the official BLS Public Data API v2.

The candidate series ID is built from an explicit, versioned NAICS2-to-BLS
industry-code crosswalk and measure code `L00`. Aggregate NAICS groups are
spelled out explicitly (for example BTOS 31 maps to BLS 31–33, and BTOS 44 maps
to BLS 44–45); they are never inferred by string truncation.

A candidate industry enters the outcome universe only if the Public API
returns annual `A01` observations. Empty or rejected series remain missing.

These API results are current-vintage live research. They do not satisfy the
historical point-in-time backtest requirement by themselves.


## Promotion gate after sector-trend diagnostics

Research estimation and production promotion are now explicitly separated.

The current candidate may be estimated with one post year so that its behavior
can be inspected. It still cannot contribute to state A.

Production promotion is fail-closed and requires all of the following:

- valid balanced panel and full-rank design;
- at least two post outcome years;
- complete point-in-time productivity release vintages;
- uncontaminated frozen treatment regime;
- sector-specific pretrend confounding resolved by a separately predeclared design;
- beta-to-activation normalization frozen before prospective scoring;
- prospective validation passed.

D22C5 found that baseline AI intensity is materially aligned with pre-existing
sector productivity trends and that trend adjustment sharply changes the raw
interaction coefficient. Those diagnostics are not converted into a new
after-the-fact pass threshold.

No threshold is retrofitted to the observed correlation, placebo ratio, or
trend-adjusted/raw beta ratio. Until the confounding question is resolved under
a predeclared design, `apcr_did` remains Missing and its A coverage increment
is exactly zero.


## 2025 second-post availability gate

Before expanding the APCR estimator beyond the frozen 2021-2024 research
candidate, the source probe requests 2025 from the same official BLS Public API
series for every frozen treatment entity.

The probe records:

- entities with a valid annual `A01` 2025 observation;
- entities missing 2025;
- whether the entire frozen universe is complete.

The estimator is not expanded in this step. A partial 2025 universe is not
imputed, cross-walked to a neighboring sector, or treated as sufficient.
Only complete frozen-universe coverage can open a later two-post-year
re-estimation step.
