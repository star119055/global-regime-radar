import json
from datetime import datetime
from urllib.parse import urlencode

from global_regime_radar.data.contracts import Observation
from global_regime_radar.etl.common import (
    ParsedBatch,
    build_vintage,
    optional_float,
    parse_date_utc,
    snapshot_only_observation,
    stable_observation_id,
)

SOURCE_ID = "ofr_hfm"
BASE_URL = "https://data.financialresearch.gov/hf/v1"
TREASURY_NET_POSITION = "TFF-LF_TREAS_NET_POSITION"


def build_series_url(
    mnemonic: str,
    start_date: str,
    end_date: str,
) -> str:
    params = {
        "mnemonic": mnemonic,
        "start_date": start_date,
        "end_date": end_date,
    }
    return f"{BASE_URL}/series/full?{urlencode(params)}"


def parse_single_series_payload(
    raw_payload: bytes,
    retrieved_at: datetime,
    mnemonic: str,
    feature_id: str,
    unit: str | None,
    revision_number: int = 0,
) -> ParsedBatch:
    payload = json.loads(raw_payload)
    series = payload.get(mnemonic) or payload.get(mnemonic.upper())
    if series is None:
        raise ValueError(f"mnemonic not found in OFR payload: {mnemonic}")

    vintage = build_vintage(SOURCE_ID, raw_payload, retrieved_at, revision_number)
    observations: list[Observation] = []
    timeseries = series.get("timeseries", {})

    for subseries_name, points in timeseries.items():
        for point in points:
            if isinstance(point, dict):
                date_value = point.get("date") or point.get("observation_date")
                raw_value = point.get("value")
            else:
                date_value, raw_value = point[0], point[1]

            if date_value is None:
                continue

            observed = parse_date_utc(date_value)
            observations.append(
                snapshot_only_observation(
                    observation_id=stable_observation_id(
                        SOURCE_ID,
                        mnemonic,
                        subseries_name,
                        date_value,
                        vintage.vintage_id,
                    ),
                    feature_id=feature_id,
                    source_id=SOURCE_ID,
                    entity_id=f"{mnemonic}:{subseries_name}",
                    value=optional_float(raw_value),
                    unit=unit,
                    observation_start=observed,
                    observation_end=observed,
                    ingested_at=retrieved_at,
                    vintage_id=vintage.vintage_id,
                    quality_flag="pit:current-vintage-snapshot-only",
                )
            )

    return ParsedBatch(vintage=vintage, observations=tuple(observations))
