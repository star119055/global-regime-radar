# Regime Engine Baseline 0

Baseline 0 is intentionally transparent. It exists to validate data lineage,
missing-data behavior and state persistence before introducing a UKF or a more
complex Bayesian state-space model.

## Inputs

Each state receives configured indicator evidence:

- activation: normalized 0..1 state-support intensity
- weight: structural, config-driven weight
- measurement variance: uncertainty produced upstream
- attribution group: prevents the same underlying raw feature from being
  counted twice toward one state

The baseline does **not** infer activation from headlines or LLM judgment.

## Missing data

Missing is not zero.

For a state with configured total weight W and observed weight w:

```text
coverage = w / W
observed_composite = weighted mean of observed activation
state = coverage * observed_composite + (1 - coverage) * prior
```

If nothing is observed, the result is the explicit prior with low confidence.

This is deliberately different from renormalizing the remaining observations
to 100%, which would make a state look more certain when data disappears.

## Uncertainty

The state variance is a mixture of:

1. observed measurement variance,
2. prior variance for missing coverage,
3. disagreement between the observed composite and prior.

Thus lower coverage naturally raises uncertainty without mechanically forcing
the state to neutral.

## Duplicate attribution

Two observed indicators carrying the same attribution group into the same
state are rejected. This is a second safety layer on top of the data dependency
graph and is intended to prevent hidden double counting.

## What Baseline 0 does not do

It does not yet estimate:

- persistence dynamics,
- cross-state feedback matrix F,
- nonlinear transition functions,
- jump operators,
- posterior credible intervals from a full Bayesian filter.

Those belong to later stages after the deterministic baseline passes
walk-forward and missing-data tests.
