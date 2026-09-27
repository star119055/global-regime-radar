# Live Public Evidence v1

The first live adapter connects only official sources that can be collected
without a private API key:

- New York Fed SOFR;
- New York Fed repo operations;
- U.S. Treasury FiscalData auctions;
- U.S. Treasury real-yield curve;
- NOAA ONI.

Every payload is hashed and assigned a retrieval-time vintage before any
normalization occurs.

## What is normalized

The first live state evidence is intentionally narrow.

### B

The adapter can derive:

- repo usage stress;
- SOFR distribution dispersion;
- Treasury auction bid-to-cover stress.

Primary-dealer balance-sheet coverage remains missing.

### D

The adapter derives only a partial real-yield repression signal from the 10Y
real yield relative to its recent live distribution.

Treasury issuance duration, regulatory intervention and the broader asset-gap
composite remain missing.

## What is deliberately not mapped

NOAA ONI remains exogenous. It is not automatically treated as C1 inflation.

Generic BLS productivity is not treated as AI productivity realization.

World Bank annual indicators are not treated as high-frequency C2 stress.

No synthetic A/C1/C2/C3 evidence is generated merely to satisfy Shadow Mode.

## Normalization

Supported live features use a robust recent-distribution transform:

1. median center;
2. MAD scale, with standard-deviation fallback;
3. signed z-score based on the economically defined direction;
4. logistic transform into a 0..1 activation intensity.

At least eight observations are required. Flat series remain missing rather
than being forced to neutral.

These live transforms are operational signal transforms, not crisis
probabilities.

## Daily workflow

At 08:30 Asia/Singapore, GitHub Actions now:

1. downloads the no-key official sources;
2. writes a hashed `live-evidence.json`;
3. passes the document to Shadow Mode;
4. emits the real coverage gaps in the Shadow artifact.

Until all six state families meet the configured coverage requirement, the
Shadow result remains `PENDING_DATA`.
