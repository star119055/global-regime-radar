# LLIER Cohort-Conversion Contract v1

LLIER is an A-state candidate for **large-load interconnection execution**.

It is not the ratio of energized load to today's total queue.

## Authoritative definition

For a cohort frozen at baseline time `t0` and evaluated at horizon `h`:

```text
LLIER(c,h)
  = MW from the same baseline cohort observed energized by h
    / eligible MW in that frozen baseline cohort
```

A project entering after `t0` can never enter that cohort's denominator.
The numerator uses baseline MW so later project-size revisions cannot
mechanically manufacture conversion.

## Identity requirement

Authoritative LLIER requires:

- a stable project identifier across observations;
- an explicit baseline-eligible status;
- later status history for the same project;
- an explicit horizon;
- versioned process regime;
- a frozen cancellation/withdrawal policy.

Without stable project identity, aggregate queue charts remain research context.

## ERCOT public boundary

ERCOT public monthly materials expose aggregate MW across stages such as
No Studies Submitted, Under ERCOT Review, Section 9.5 Requirements Met,
Approved to Energize but Not Operational, and Observed Energized.

Those stages are useful for understanding execution pressure. Aggregate stage
shares cannot prove that the same baseline projects moved from one stage to
another, because new requests, cancellations, MW changes and projected in-service
dates can change the aggregate composition.

Therefore:

```text
ERCOT aggregate queue context
authoritative_state_input = false
A_coverage_increment = 0
```

## Process-regime break

The legacy ERCOT LLIS process ended on July 10, 2026 during transition to the
PGRR145/NPRR1325 Batch Zero process.

A cohort may not silently span that boundary. A later implementation needs an
explicit mapping proving that project identity and state semantics remain
comparable across regimes.

## Exits

Cancellation and withdrawal treatment is deliberately unresolved in v1.

Possible future policies include:

- count as execution failure;
- right-censor;
- define separate competing-risk outcomes.

The project will not choose among those after seeing which choice improves
LLIER. Until the policy is frozen, an authoritative estimator must fail closed
when a baseline project exits before the horizon.
