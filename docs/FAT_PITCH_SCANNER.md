# Fat Pitch Opportunity Scanner

The scanner runs **after** Regime and Stress. It is a structural opportunity
detector, not a trading recommendation system.

Its output states are:

- `PENDING_DATA`
- `OFF`
- `WATCH`
- `ON`

It deliberately does not emit BUY or SELL.

## B-Fat — forced liquidation

B-Fat looks for financial-market dislocation where price deterioration exceeds
fundamental deterioration.

Hard evidence includes:

- B regime activation;
- at least L2 market-function stress;
- forced-liquidation evidence;
- resilient cash flow;
- a material price-damage minus fundamental-damage gap.

A large drawdown by itself cannot turn B-Fat ON.

## C-Fat — hard physical bottleneck

C-Fat looks for physical scarcity where cash flow and earnings improve faster
than valuation reprices.

It requires:

- active C1 or C3 pressure;
- a measurable physical bottleneck;
- cash-flow confirmation;
- improving earnings;
- valuation softness.

## D-Fat — persistent financial repression

D-Fat looks for persistent repression that supports real-asset cash flow or
replacement value relative to nominal claims.

It requires:

- active D state;
- a minimum persistence period;
- direct exposure to the repression channel;
- real-asset support.

## Permanent Impairment Filter

Every candidate is screened for:

- structural business deterioration;
- technological obsolescence;
- unfinanceable debt;
- permanent loss of pricing power;
- permanent customer loss;
- collapsing replacement cost.

The first implementation uses the maximum impairment dimension as a hard-block
signal. If any dimension exceeds the configured threshold, the candidate is
OFF even when all opportunity gates otherwise pass.

## Missing and traceability

Every required metric must have:

1. a non-missing value;
2. at least one evidence identifier.

If a hard metric is missing or untraceable, the result is `PENDING_DATA`, not
OFF and not ON.

Regime coverage is also checked before scanning.

## Scoring

Scores are class-specific and remain secondary to hard gates.

Conceptually:

```text
Opportunity =
  Structural Support
  * Hard Cash Flow
  * Soft Price
  * (1 - Permanent Impairment)
```

A high numeric score cannot override a failed permanent-impairment filter.

## Engine discipline

The regime engine is explicit in every assessment. The initial configuration
uses `baseline1`. UKF must not become the opportunity engine automatically;
promotion remains governed by prospective Shadow Mode evidence.
