# Historical Episode Validation

Named historical events are **evaluation targets**, not proof that the model
predicted them.

The project therefore separates three things:

1. the historical episode definition;
2. the channels that the model is expected to observe;
3. the actual point-in-time model output.

An episode can have one of three statuses:

- `PASS`: required data exist and the model met the frozen evaluation contract;
- `FAIL`: required data exist but the model response did not meet the contract;
- `PENDING_DATA`: the historical point-in-time feature set is incomplete.

`PENDING_DATA` must never be silently converted to either PASS or FAIL.

## Initial catalog

The first registry contains:

- 2018 Q4 tightening / liquidity stress;
- September 2019 repo spike;
- March 2020 Treasury-market dysfunction;
- 2022 UK LDI;
- March 2023 regional-bank stress;
- August 2024 cross-market carry unwind.

The thresholds in `config/historical_episodes.yaml` are frozen validation
hypotheses. They are **not probabilities** and are not statements that the
current open-source data layer can already reproduce every episode.

In particular, UK LDI, bank balance-sheet stress and cross-market carry
episodes deliberately name feature families that are not yet implemented.
Those episodes should remain `PENDING_DATA` until the missing source modules
exist.

## Evaluation window

Each episode has:

- an event start and end;
- a pre-event lead window;
- minimum required point-in-time feature coverage;
- an optional minimum Stress level;
- optional minimum peak activation for selected regime states.

The first qualifying point is used to calculate lead time:

```text
lead_days = event_start - first_qualifying_signal
```

Positive lead time means the frozen contract was reached before the event
start. Negative lead time means the response arrived after the start.

## Anti-overfitting rule

Episode thresholds must not be repeatedly changed to make a known event pass.
A threshold change requires a new registry version and must be evaluated across
all episodes and false-alarm periods.
