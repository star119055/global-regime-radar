# Macro and Physical-Delivery Source Contract

D4 preserves the V6.1 separation among C1, C2 and C3.

- **C1** consumes core-economy inflation/energy transmission evidence.
- **C2** consumes external-finance, reserve and debt-service evidence.
- **C3** consumes industrial/project delivery constraints.
- Climate and chokepoint inputs remain exogenous until routed into one of those states.

## Evidence stages

Shock evidence is tracked separately from state intensity:

```text
EXPECTED -> CONFIRMED -> MACRO_TRANSMITTED
```

A stage cannot move backward. The transition must cite an evidence ID. This prevents a
weather forecast from being treated as already-realized crop damage or sovereign stress.

## NOAA ONI

The NOAA/PSL ONI text file provides a long monthly history. D4 treats a downloaded file
as a **current vintage**. It is useful immediately for current/shadow-mode analysis, but
strict historical replay requires archived vintages because historical climate indices
and climatological baselines can be updated.

## USDA PSD

USDA FAS exposes commodity data by commodity code and market year. Authentication uses
the `API_KEY` request header. D4 ingests the raw attributes rather than prematurely
hard-coding a Crop Balance Stress formula. Stocks/use and input-cost composites belong in
the signal layer.

## EIA

EIA API v2 requires an API key. The adapter is route-generic so hydropower, natural-gas
generation and other physical energy series can share one auditable ingestion path.

Current-history downloads are snapshot-only unless release-vintage provenance is
available.

## Sovereign data

The no-key World Bank Indicators API is used for broad sovereign context such as reserve
months, external debt stocks and debt service. QEDS remains the preferred quarterly debt
source for the C2 module where country coverage permits it.

QEDS strict historical use requires its publication calendar and release vintage because
the database is revised.

## Treasury QRA

Quarterly Refunding releases are events, not smooth time series. D4 registers the official
Treasury archive as an event-artifact source. Later work can extract bill/coupon issuance
structure from each preserved release without rewriting the historical document.

## Interconnection queues

LBNL Queued Up editions are treated as annual snapshots. A later workbook may describe
what eventually happened to an old project, but that outcome cannot be injected into an
earlier decision date.
