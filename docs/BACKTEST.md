# Walk-Forward Backtest Contract

D5 exists to make historical claims reproducible and falsifiable.

## A valid run is an immutable tuple

Every completed backtest must bind:

```text
model_version
feature_set_version
fold_id
dataset_hash
code_commit
parameters_hash
```

If any element changes, it is a different run.

The deterministic run ID is derived from those fields plus the fold boundaries.

## Point-in-time rule

The core eligibility test remains:

```text
available_at <= decision_time
```

D5 adds optional **extra lag simulation** on top of the recorded historical availability.
This can answer questions such as: “Would the model still work if this monthly source
arrived seven days later?”

The extra lag never makes information available earlier.

## Revisions

Revision control is inherited from the D1 vintage layer. At each decision time the
snapshot selects only the latest revision that was already eligible at that time.

A revision published later cannot replace the value used by an earlier decision.

## Frozen historical universes

The repository intentionally does not force every modern feature into every period:

- Core-1: 2006-2009
- Core-2: 2010-2019
- Core-3: 2020-2023
- New Module: 2024-2026

Feature availability must be checked against the fold universe and earliest valid date.

## Sensitivity

Default sensitivity scenarios change **one numeric parameter at a time** by:

```text
-20%, -10%, +10%, +20%
```

This makes it possible to identify models whose conclusions depend on a narrow parameter
choice.

## Missing-data stress

The default missing-data test masks 20% of observations. Selection is deterministic from:

```text
seed + observation_id
```

so the exact stress test can be reproduced. Masking sets `value = null`; it does not
convert missing data to zero or delete provenance.

## Evaluation metrics

D5 provides baseline metrics for warning systems:

- episode recall
- false-alarm episodes
- false-negative events
- median lead time
- time in warning
- transition count
- mean warning dwell time
- monotonicity between state intensity and future stress

These metrics are diagnostic. They do not redefine A/B/C1/C2/C3/D as probabilities.

## Parameter freeze

Parameters are serialized to canonical JSON and hashed. Reordering keys does not create a
new configuration, while any actual value change does.

Parameter updates after viewing a test fold require a new model/config version and a new
run. Historical results must not be silently overwritten.
