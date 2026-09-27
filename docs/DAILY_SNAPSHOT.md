# Daily Snapshot Contract

The daily snapshot is the canonical decision artifact for the system.

It is deliberately smaller than the raw research database and deliberately
more structured than a macro-news summary.

## Layer 1 — decision state

Every snapshot contains exactly:

- A / B / C1 / C2 / C3 / D state rows;
- daily delta;
- confidence and data coverage;
- Stress L1-L4;
- B-Fat / C-Fat / D-Fat OFF, WATCH or ON.

## Layer 2 — explanation

The explanatory layer is bounded:

- at most three model-changing drivers;
- one dominant feedback loop;
- an evidence ledger with explicit Observed / Inferred / Uncertain labels;
- one next confirmation event;
- explicit falsification conditions.

A daily report must not expand into an unbounded news digest.

## Stable identity

The snapshot hash is calculated from the decision payload and deliberately
excludes `generated_at`.

Thus regenerating the same snapshot at a different wall-clock time produces the
same hash. If any state, evidence item, conclusion, confirmation event or
falsification condition changes, the hash changes.

This allows the system to answer:

> What exactly did the model believe, and on what evidence, at that as-of time?

## Presentation

The first renderer is Markdown. The same canonical payload can later feed:

- a web dashboard;
- a JSON API;
- a scheduled 08:30 report;
- historical replay;
- Red/Black evidence arbitration.

The renderer itself performs no LLM inference.
