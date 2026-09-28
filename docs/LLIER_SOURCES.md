# LLIER Source Discovery v1

This document records the current public-source boundary for authoritative
large-load cohort conversion.

## Current ERCOT evidence

ERCOT monthly large-load materials expose aggregate MW by projected in-service
year and queue stage. The reports also define stages through Observed Energized.

That is useful research context, but it does not expose a stable public project
identifier that can be followed through monthly status transitions.

The public Large Load Interconnection Process Q&A similarly documents queue
stage semantics, not a project-level history table.

The July 2026 Batch Zero market notice is valuable process-regime metadata. It
establishes the end of the legacy LLIS review process, but contains no cohort
observations.

## Source qualification rule

A source can become authoritative for LLIER only if it provides all of:

1. stable project/request ID;
2. project-level MW;
3. repeatable status history for the same ID;
4. explicit cancellation/withdrawal events.

Process-regime metadata and machine readability are additionally required for
operational use, but cannot substitute for project identity.

## Current result

```text
ERCOT monthly queue       = AGGREGATE_CONTEXT_ONLY
ERCOT process Q&A         = AGGREGATE_CONTEXT_ONLY
Batch Zero market notice = PROCESS_METADATA_ONLY

authoritative_source_available = false
A_coverage_increment = 0
```

The repository will not reconstruct project identity by fuzzy matching MW,
project type, or projected in-service year across aggregate reports.
