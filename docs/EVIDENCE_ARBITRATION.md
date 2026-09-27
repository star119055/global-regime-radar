# Red / Black Evidence Arbitration

The arbitration layer is a review system for model evidence, not a voting
mechanism between language models.

## Roles

### Red Team

Challenges the evidence that supports the current state:

> Why could the evidence behind the current state be wrong?

Typical outputs include stale sources, revisions, proxy breakdowns, duplicated
signals, publication artifacts and alternative explanations.

### Black Team

Searches for nonlinear risk the current model may be missing:

> What important risk is not yet represented strongly enough?

This can include cross-market propagation, hidden leverage, nonlinear
collateral effects or missing geographic routes.

### Arbitrator

The arbitrator does not choose a winning team.

It decides:

- whether a claim can be treated as Observed;
- whether it must remain Inferred or Uncertain;
- which evidence is missing or unavailable at the snapshot as-of time;
- what would falsify the claim;
- which conflicts remain unresolved.

## Trigger

Arbitration is not run on every unchanged day.

The default trigger is any of:

- absolute A/B/C1/C2/C3/D state change >= 0.05;
- Stress level transition;
- B-Fat / C-Fat / D-Fat status transition.

## Point-in-time discipline

An Observed claim must name traceable source IDs. Each source must have been
available at or before the arbitration as-of time.

Future, missing, conflicted or stale evidence cannot silently support an
Observed label.

LLM-generated text never enters the raw observation tables.

## No majority vote

If Red and Black produce admissible claims in the same explicit conflict group,
the conflict remains unresolved unless evidence itself resolves it.

Two models saying one thing and one model saying another is not evidence.

## Falsifiers

Inferred claims require explicit falsification conditions. An inference without
a falsifier is downgraded to Uncertain.

The arbitration output therefore becomes a structured extension of the daily
snapshot's evidence ledger rather than a free-form debate transcript.
