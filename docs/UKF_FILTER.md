# Bayesian / UKF Regime Filter

The UKF is a **candidate estimator**, not a replacement for Baseline 0 or
Baseline 1.

The transparent baselines remain mandatory controls in walk-forward testing.

## Why logit space?

The six regime states are bounded activation intensities in `[0, 1]`.
A Gaussian filter directly in activation space can leak outside those bounds.

The UKF therefore keeps a latent Gaussian vector in logit space:

```text
z_t in R^6
R_t = sigmoid(z_t)
```

The observation function is nonlinear, which makes sigma-point filtering a
natural fit.

## Prediction

Absent couplings and jumps, the expected state persists rather than drifting
mechanically to neutral.

Different state speeds are expressed primarily through process variance:

- B has higher process variance and can adapt quickly;
- A, C3 and D have lower process variance and move more slowly.

Sparse structural couplings from Baseline 1 are applied in activation space and
then mapped back to latent space.

Jump events are applied immediately and are not smoothed away.

## Measurement update

Measurements can be partial. If a state has no usable measurement it is simply
omitted from that update.

Missing is never converted to zero.

Measurement variance carries uncertainty from upstream freshness, source
confidence and data coverage. Lower-quality evidence therefore receives a
smaller Kalman gain.

## Output

The filter returns for each state:

- activation mean;
- activation variance;
- 90% interval;
- qualitative confidence.

These are state-estimation intervals, not crisis probabilities.

## Promotion rule

UKF is not the default engine merely because it is more sophisticated.

It can only replace a transparent baseline if walk-forward testing shows
material improvement in:

- lead time;
- false positives / false negatives;
- state persistence;
- missing-data robustness;
- historical episode behavior;

without a material increase in false alarms or loss of interpretability.

No named crisis is used to fit parameters in this PR.
