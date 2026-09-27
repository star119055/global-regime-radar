# Regime Dynamics Baseline 1

Baseline 1 adds explicit time dynamics to the transparent Baseline 0 estimator.

It is still not a UKF or a learned state-space model.

## Persistence

Each state uses its own half-life:

```text
phi = exp(-ln(2) * delta_days / half_life_days)
```

Evidence innovation is coverage-scaled:

```text
innovation_strength = (1 - phi) * coverage
new_state = previous + innovation_strength * (evidence - previous)
```

Therefore missing data does not cause a state to drift mechanically toward 0.5.
Instead, the state persists while variance grows.

## Sparse feedbacks

Only a small structural coupling set is enabled initially:

- C3 -> A: negative
- C3 -> B: positive
- A -> B: negative
- B -> A: negative
- D -> B: negative

Coupling is applied as a bounded deviation from neutral:

```text
(1 - phi_target) * coefficient * (source_state - 0.5)
```

This keeps faster states more responsive than slower structural states.

The coefficients are explicit baseline assumptions. They are not calibrated to
maximize historical crisis detection.

## Jump Operator

Discrete events can apply direct state jumps after the persistence update.
Jumps are deliberately not smoothed by the half-life mechanism.

Examples include:

- emergency liquidity programs
- abrupt SLR / reserve-rule changes
- major QRA issuance-structure changes
- verified chokepoint closure
- outbreak of war

The event layer owns whether an event is sufficiently verified and the signed
magnitude of its jump.

## Uncertainty

Variance propagates from:

- prior state variance,
- current evidence variance,
- process variance,
- additional missing-coverage variance.

The next implementation layer may replace this explicit approximation with a
Bayesian filter, but only after Baseline 1 passes walk-forward stability tests.
