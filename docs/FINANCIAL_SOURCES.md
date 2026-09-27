# Financial Core sources

D2 intentionally separates **API availability** from **point-in-time eligibility**.

A public endpoint that returns a long history today is not automatically safe for a
historical backtest. If the provider can revise old observations and does not expose all
prior vintages, the adapter marks the series as snapshot-only. Such data can be collected
for shadow mode immediately and becomes point-in-time safe from the date this project
starts preserving snapshots.

## Treasury auctions

FiscalData exposes Treasury auction records including bid-to-cover and bidder/dealer
accepted amounts. The adapter does not invent auction tail because a true tail requires a
when-issued market yield at the auction deadline.

Endpoint:

```text
https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/auctions_query
```

## New York Fed SOFR

SOFR is published through the NY Fed Markets API. The API exposes a revision indicator,
but a current historical query is not treated as a complete prior-vintage archive.
Historical backfills are therefore snapshot-only by default.

## New York Fed repo / SRF

Repo operation results expose `lastUpdated`. D2 uses that source timestamp as the
eligibility time for the current record. Operation amounts from the API are in millions
of dollars; public NY Fed display pages commonly present the same totals in billions.

## New York Fed Primary Dealer Statistics

The NY Fed states that historical Primary Dealer series may reflect revisions since prior
publication. That makes a fresh bulk download unsuitable for strict historical
point-in-time replay. D2 includes the official series catalog and establishes a policy to
archive weekly payloads going forward.

## OFR Hedge Fund Monitor

The OFR API is keyless and exposes Treasury-futures and related hedge-fund series. OFR
metadata can identify a series as current vintage. Those series remain snapshot-only
unless a prior-vintage archive is independently available.

Useful Treasury futures mnemonic:

```text
TFF-LF_TREAS_NET_POSITION
```

## Treasury real yields

Treasury publishes daily par real yield curve rates at 5Y, 7Y, 10Y, 20Y and 30Y. The
annual CSV is parsed without extra dependencies. Historical annual files are still marked
snapshot-only until release-vintage reconstruction is proven.

## Strict-mode rule

D2 never silently assigns an old observation an old `available_at` merely because the
source currently reports an old observation date.

When prior-vintage proof is unavailable:

```text
available_at = ingested_at
quality_flag = pit:snapshot-only
```

This sacrifices historical coverage rather than creating look-ahead bias.
