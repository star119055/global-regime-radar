# Live Public Evidence v3

The live adapter currently connects official sources that can be collected
without a private API key:

- New York Fed SOFR;
- New York Fed repo operations;
- U.S. Treasury FiscalData auctions;
- U.S. Treasury real-yield curve;
- NOAA ONI;\n- BLS transformer-manufacturing PPI;\n- BLS switchgear-manufacturing PPI.

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

## Still deliberately missing

A, C1, C2 and C3 remain incomplete. The adapter does not manufacture synthetic
evidence merely to clear the Shadow Mode coverage threshold.

NOAA ONI remains exogenous. It is not automatically treated as C1 inflation.

Generic productivity is not treated as AI productivity realization.

## Coverage and gap inventory

The live evidence document now emits:

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

Supported features use a robust recent-distribution transform:

1. median center;
2. MAD scale, with standard-deviation fallback;
3. signed z-score based on the economically defined direction;
4. logistic transform into a 0..1 activation intensity.

At least eight observations are normally required. The monthly issuance
duration series uses four monthly observations as its minimum because it is a
lower-frequency feature.

Flat or insufficient series remain missing rather than being forced to neutral.

## Shadow workflow

At 08:30 Asia/Singapore, GitHub Actions:

1. downloads the official no-key sources;
2. writes a hashed `live-evidence.json`;
3. passes the document to Shadow Mode;
4. records real coverage gaps and state coverage;
5. uploads an immutable run artifact.

Until all six state families meet the configured coverage requirement, the
Shadow result remains `PENDING_DATA`.


## C3 coverage added in v3

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
