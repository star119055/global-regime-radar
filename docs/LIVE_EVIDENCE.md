# Live Public Evidence v5

The live adapter currently connects official/public sources that can be
collected without a private API key:

- New York Fed SOFR;
- New York Fed repo operations;
- U.S. Treasury FiscalData auctions;
- U.S. Treasury real-yield curve;
- NOAA ONI;
- BLS transformer-manufacturing PPI;
- BLS switchgear-manufacturing PPI;
- Lawrence Berkeley National Laboratory Queued Up annual snapshot.

Every payload is hashed and assigned a retrieval-time vintage before any
normalization occurs.

## B coverage

Live v2 derives four independent B observations:

- repo usage stress;
- SOFR distribution dispersion;
- Treasury auction bid-to-cover stress;
- primary-dealer auction take-down share stress.

Auction take-down share is **not** relabeled as the broader primary-dealer
balance-sheet series. That broader feature remains missing.

## D coverage

Live v2 derives:

- a partial real-yield repression signal from the 10Y real yield;
- an accepted-amount-weighted Treasury issuance-duration signal.

The duration series parses the original security term for each auction and
aggregates weighted duration by month. Shorter duration relative to the recent
distribution raises the partial D pressure proxy.

This is a TIDS proxy. It is not a substitute for the full QRA narrative,
regulatory intervention, or the gold/USD/real-yield asset-gap composite.

## C3 capex-cost coverage

The BLS Public Data API supplies monthly industry PPI observations for:

- `PCU335311335311` — power, distribution, and specialty transformer manufacturing;
- `PCU335313335313` — switchgear and switchboard apparatus manufacturing.

The live adapter aligns common monthly observations and averages the two index
levels into a robust recent-distribution **capex-cost pressure proxy**.

Higher producer-price pressure increases C3 activation.

This does **not** fill the transformer lead-time requirement. Price and lead
time remain separate features because a producer-price index cannot establish
delivery delay.

The BLS payload is treated as current-vintage snapshot data. Historical
revisions are not backdated into earlier Shadow runs.

## C3 interconnection execution coverage

Live v4 adds Lawrence Berkeley National Laboratory's annual `Queued Up`
snapshot as a low-frequency advanced-stage execution proxy.

The input components are:

- active generation capacity in the transmission interconnection queue;
- active storage capacity;
- capacity with a draft or executed interconnection agreement that has not yet
  reached commercial operation.

The bounded activation is:

```text
IA share = draft_or_executed_IA_GW /
           (active_generation_GW + active_storage_GW)
```

For the 2025 snapshot this is `549 / (1312 + 749)`, approximately 0.266.

This ratio is **not a completion rate** and an IA is **not COD**. The source is
generation-side transmission interconnection data; it does not include load
interconnection requests.

Because the observation is annual, it is not passed through the normal
high-frequency robust-z transform. Instead:

```text
Freshness = exp(-ln(2) * age_days / 365)
MeasurementVariance = 0.04 / Freshness
```

with variance capped at 1.0. The activation itself does not decay toward zero.
The annual observation simply becomes less informative as it ages.

The official annual release is frozen in
`config/lbnl_queued_up_snapshots.yaml` with its source URL, observation date
and conservative `available_at` gate.

The daily Shadow workflow does **not** scrape Berkeley Lab. This is deliberate:
the public site returns HTTP 403 to the GitHub Actions runner, and the source is
annual rather than daily. A new Queued Up edition appends a new registry entry;
it never rewrites an earlier snapshot.

The 2025 year-end snapshot is gated at
`2026-05-31T23:59:59Z`, the conservative end of the source's published
05/2026 month. A historical decision before that timestamp cannot see the
snapshot.

## A-state contract reconciliation

Live v5 removes two identifier drifts from the early Shadow adapter. The
authoritative A keys now exactly match the frozen regime contract:

```text
apcr_did
llier
geoi
```

The earlier live-only names `apcr` and `ai_capital_cycle` are retired.

This change does not manufacture new A evidence. APCR-DiD remains missing,
LLIER remains missing because generation interconnection queues are not
large-load execution data, and GEOI remains missing until independent GPU
performance/rental/secondary-market vintages exist.

The workflow also writes `ai-research-context.json`, a non-authoritative
Census BTOS sidecar. It is stored beside the prospective run but is excluded
from `LiveEvidenceDocument.evidence`, so A coverage remains zero.

## Still deliberately missing

A, C1 and C2 remain incomplete. C3 still lacks a direct transformer/switchgear
lead-time source.

The adapter does not manufacture synthetic evidence merely to clear the Shadow
Mode coverage threshold.

NOAA ONI remains exogenous. It is not automatically treated as C1 inflation.

Generic productivity is not treated as AI productivity realization.

## Coverage and gap inventory

The live evidence document emits:

- deterministic per-state observed/configured coverage;
- every missing feature;
- gap priority: CRITICAL, HIGH or MEDIUM;
- source failures separately from feature gaps.

Current priority policy:

- A and C3: CRITICAL;
- C1 and C2: HIGH;
- B and D: MEDIUM.

The priority is an engineering remediation order, not an investment score.

## Normalization

High- and medium-frequency supported features normally use:

1. median center;
2. MAD scale, with standard-deviation fallback;
3. signed z-score based on the economically defined direction;
4. logistic transform into a 0..1 activation intensity.

At least eight observations are normally required. The monthly issuance
duration series uses four monthly observations as its minimum because it is a
lower-frequency feature.

Annual LBNL evidence is handled separately through freshness-adjusted
measurement variance.

Flat, stale or insufficient data are never forced to zero.

## Shadow workflow

At 08:30 Asia/Singapore, GitHub Actions:

1. downloads the official/public no-key sources and loads the frozen annual
   LBNL registry entry available at that decision time;
2. writes a hashed `live-evidence.json`;
3. passes the document to continuous three-engine Shadow Mode;
4. records real coverage gaps and state coverage;
5. writes the non-authoritative `ai-research-context.json` sidecar;
6. uploads an immutable Actions artifact;
7. appends the prospective run and sidecar to `shadow-ledger`.

Until all six state families meet the configured coverage requirement, the
Shadow result remains `PENDING_DATA` and is not promotion-eligible.
