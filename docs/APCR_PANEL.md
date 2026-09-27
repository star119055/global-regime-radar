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
