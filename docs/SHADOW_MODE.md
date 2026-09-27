# Out-of-Sample Shadow Mode

Shadow Mode is the prospective validation layer for V6.1.

The three engines run side by side on the **same point-in-time evidence**:

1. Baseline 0 — transparent static aggregation;
2. Baseline 1 — transparent dynamic persistence and sparse feedback;
3. UKF — candidate nonlinear Bayesian filter.

UKF is not the default merely because it is more sophisticated.

## Shared identity

Every run is keyed by decision time, dataset hash, configuration hash and
feature-set version. The operational `generated_at` timestamp does not change
run identity.

## Readiness versus diagnostics

Strict readiness still requires at least 40% configured evidence coverage for
every state.

When one or more states fail that rule, the run remains `PENDING_DATA` and is
**not promotion-eligible**.

Shadow v2 nevertheless runs all three estimators diagnostically:

- missing observations remain missing;
- Baseline 0 falls back toward its explicit prior according to coverage;
- Baseline 1 preserves prior state and grows uncertainty;
- UKF omits missing measurements and propagates its prior posterior.

The resulting state values are therefore diagnostic estimates under incomplete
coverage, not claims that missing evidence is neutral.

## Continuous prior state

Baseline 1 and UKF are stateful. Each prospective run writes a deterministic
`state.json` containing:

- decision time;
- all six Baseline 1 state values and variances;
- UKF latent mean;
- UKF covariance matrix.

The next run may load only an earlier prospective state. Future-dated prior
state is rejected.

## Permanent prospective ledger

GitHub Actions artifacts are useful operational copies, but they expire.

The scheduled workflow therefore maintains a separate public branch named
`shadow-ledger`.

Each run is appended under:

```text
runs/YYYY-MM-DD/<run_id>/
  live-evidence.json
  shadow.json
  shadow.md
  state.json
```

The branch also contains:

```text
state/latest.json
```

for the next run's prior state.

Historical run directories are append-only. If the same run ID already exists,
the workflow fails rather than rewriting the record. Only
`state/latest.json` advances.

This makes later 60-day or 120-day comparisons genuinely prospective: the
repository can prove what data and model state existed at each decision time.

## Daily schedule

The scheduled workflow runs at 00:30 UTC, corresponding to 08:30
Asia/Singapore year-round.

It:

1. loads the prior state from `shadow-ledger` when available;
2. collects official point-in-time live evidence;
3. runs Baseline0 / Baseline1 / UKF;
4. labels the result `COMPLETED` or `PENDING_DATA`;
5. uploads a normal Actions artifact;
6. appends the permanent run to `shadow-ledger`.

## Comparison

For every state the system records:

- Baseline0 vs Baseline1;
- Baseline0 vs UKF;
- Baseline1 vs UKF;
- maximum three-engine spread.

Persistent UKF divergence is diagnostic information, not evidence that UKF is
superior.

## Outcomes

At 5, 20 and 60 days, the ledger can attach a separate prospective outcome
record without changing the original run.

The target is the later **observation-driven composite** for each state, and a
state is eligible only when the later evidence coverage is at least 40%.

For each engine the system records absolute distance from those later observed
composites and an aggregate MAE across eligible states.

This metric is named **forward consistency**. It is not prediction accuracy:
the regime state is an estimate of the current system, not an explicit
horizon-return forecast.

Outcome files are append-only:

```text
outcomes/<origin_run_id>/5d.json
outcomes/<origin_run_id>/20d.json
outcomes/<origin_run_id>/60d.json
```

If no later eligible target exists, no score is created. Missing target
evidence is never converted to zero.

A rebuildable `scorecard.json` aggregates run counts, engine disagreement,
matured outcome counts and mean forward-consistency MAE.

## Promotion

At least 60 **promotion-eligible** prospective days are required before a
default-engine promotion decision.

Promotion must compare state stability, warning lead time, false alarms and
missing-data robustness. Parameter changes create a new configuration version
rather than rewriting history.
