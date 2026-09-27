# Stress Engine V0

The Stress Engine is intentionally independent from A/B/C1/C2/C3/D.

It answers a different question:

> How badly is market function impaired right now?

## Three continuous market functions

Each input is normalized to `[0, 1]`, where higher means more stress:

- **Funding** — ability to obtain financing without abnormal dislocation.
- **Price Discovery** — ability of the market to form executable prices with usable depth.
- **Intermediation** — ability of dealers, banks and funds to warehouse or transfer risk.

The engine does not infer macro regimes from these values.

## Raw severity

With default thresholds:

- L1: all three functions are below the pressure threshold.
- L2: at least one function is at or above `0.50`.
- L3: at least two functions are at or above `0.70`.
- L4: the L3 condition is present **and** a sovereign/liquidity controller is intervening while forced private deleveraging persists.

L4 is therefore not simply “high numbers.” It encodes the specific V6.1 condition that intervention has begun but private clearing pressure remains active.

## Hysteresis

The engine separates `raw_level` from `confirmed_level`.

Default confirmation:

```text
upgrade:   2 daily observations
downgrade: 5 daily observations
```

A one-day shock can therefore raise raw severity without immediately changing the confirmed dashboard state. Conversely, a single calm day does not declare a crisis over.

A change in the candidate level resets its confirmation counter. This avoids counting non-consecutive evidence toward a transition.

## Transition history

Every confirmed level change records:

- timestamp;
- prior level;
- new level;
- number of confirming observations.

This allows backtests to measure dwell time, transition frequency and false alarms separately from raw indicator volatility.

## Deliberate V0 simplifications

V0 consumes pre-normalized substate values rather than aggregating individual repo, basis, depth, auction and credit features itself. Feature-to-substate aggregation belongs to the Signal/Stress feature layer built on top of D2 data.

The hysteresis counter treats each `update()` call as one daily decision observation. The caller is responsible for sending at most one official daily stress update and for handling missing days explicitly.
