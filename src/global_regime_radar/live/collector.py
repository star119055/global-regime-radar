from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial

from global_regime_radar.data.contracts import DataVintage, Observation
from global_regime_radar.data.hashing import dataset_snapshot_hash
from global_regime_radar.etl.bls import (
    SWITCHGEAR_PPI_SERIES,
    TRANSFORMER_PPI_SERIES,
    build_series_url,
    parse_bls_single_series_payload,
)
from global_regime_radar.etl.noaa import ONI_URL, parse_oni_text
from global_regime_radar.etl.nyfed import (
    REPO_LIVE_ENDPOINT,
    build_sofr_url,
    parse_repo_payload,
    parse_sofr_payload,
)
from global_regime_radar.etl.treasury_auctions import (
    build_auction_url,
    parse_auction_payload,
)
from global_regime_radar.etl.treasury_real_yields import (
    build_real_yield_url,
    parse_real_yield_csv,
)
from global_regime_radar.live.http import FetchBytes, fetch_bytes


@dataclass(frozen=True)
class SourceFailure:
    source: str
    error_type: str
    message: str


@dataclass(frozen=True)
class LiveBundle:
    retrieved_at: datetime
    observations: tuple[Observation, ...]
    vintages: tuple[DataVintage, ...]
    source_failures: tuple[SourceFailure, ...]
    dataset_hash: str


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("retrieved_at must be timezone-aware")


def collect_public_core(
    retrieved_at: datetime,
    *,
    fetcher: FetchBytes = fetch_bytes,
    lookback_days: int = 180,
) -> LiveBundle:
    _require_aware(retrieved_at)
    if lookback_days < 30:
        raise ValueError("lookback_days must be >= 30")

    end = retrieved_at.date()
    start = end - timedelta(days=lookback_days)
    start_text = start.isoformat()
    end_text = end.isoformat()

    source_specs = (
        (
            "nyfed_sofr",
            build_sofr_url(start_text, end_text),
            parse_sofr_payload,
        ),
        (
            "nyfed_repo",
            REPO_LIVE_ENDPOINT,
            parse_repo_payload,
        ),
        (
            "treasury_auctions",
            build_auction_url(start_text, end_text),
            parse_auction_payload,
        ),
        (
            "treasury_real_yields",
            build_real_yield_url(retrieved_at.year),
            parse_real_yield_csv,
        ),
        (
            "noaa_oni",
            ONI_URL,
            parse_oni_text,
        ),
        (
            "bls_transformer_ppi",
            build_series_url(TRANSFORMER_PPI_SERIES),
            partial(
                parse_bls_single_series_payload,
                series_id=TRANSFORMER_PPI_SERIES,
                feature_id="transformer_industry_ppi",
                source_id="bls_transformer_ppi",
            ),
        ),
        (
            "bls_switchgear_ppi",
            build_series_url(SWITCHGEAR_PPI_SERIES),
            partial(
                parse_bls_single_series_payload,
                series_id=SWITCHGEAR_PPI_SERIES,
                feature_id="switchgear_industry_ppi",
                source_id="bls_switchgear_ppi",
            ),
        ),
    )

    observations: list[Observation] = []
    vintages: list[DataVintage] = []
    failures: list[SourceFailure] = []

    for source_name, url, parser in source_specs:
        try:
            raw = fetcher(url)
            batch = parser(raw, retrieved_at)
        except (OSError, ValueError, TypeError) as exc:
            failures.append(
                SourceFailure(
                    source=source_name,
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )
            continue
        vintages.append(batch.vintage)
        observations.extend(batch.observations)

    snapshot_hash = dataset_snapshot_hash(observations, vintages)
    return LiveBundle(
        retrieved_at=retrieved_at,
        observations=tuple(observations),
        vintages=tuple(vintages),
        source_failures=tuple(failures),
        dataset_hash=snapshot_hash,
    )
