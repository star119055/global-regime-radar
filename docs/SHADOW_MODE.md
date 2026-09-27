# Out-of-Sample Shadow Mode

Shadow Mode freezes the transition from model development to prospective
observation.

The three engines run side by side on the **same point-in-time evidence**:

1. Baseline 0 — transparent static aggregation;
2. Baseline 1 — transparent dynamic persistence and sparse feedback;
3. UKF — candidate nonlinear Bayesian filter.

UKF is not the default merely because it is more sophisticated.

## Shared identity

Every run is keyed by decision time, dataset hash, configuration hash and
feature-set version. All three engines share those inputs. The operational
`generated_at` timestamp does not change run identity.

## Readiness

A run is either `COMPLETED` or `PENDING_DATA`. Missing evidence is never
filled with zero or neutral merely to produce a daily state. The default
minimum state coverage is 40%.

## Daily schedule

The repository schedules the shadow contract for 00:30 UTC, corresponding to
08:30 Asia/Singapore year-round.

The scheduled job currently emits `PENDING_DATA` until the normalized live
evidence adapter is connected. This is deliberate: an incomplete live feed must
not masquerade as a production model run.

## Comparison

For every state the system records Baseline0 vs Baseline1, Baseline0 vs UKF,
Baseline1 vs UKF and the maximum three-engine spread. Persistent UKF divergence
is diagnostic information, not evidence that UKF is superior.

## Outcomes

Realized outcomes are attached later in a separate table at frozen horizons
such as 5, 20 and 60 days. Attaching an outcome never mutates the original run.

## Promotion

At least 60 prospective shadow days are required before a default-engine
promotion decision. Promotion must compare state stability, warning lead time,
false alarms and missing-data robustness. Parameter changes create a new
configuration version rather than rewriting history.
