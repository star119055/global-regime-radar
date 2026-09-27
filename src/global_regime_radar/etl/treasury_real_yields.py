import csv
from datetime import datetime
from io import StringIO
from urllib.parse import urlencode

from global_regime_radar.data.contracts import Observation
from global_regime_radar.etl.common import (
    ParsedBatch,
    build_vintage,
    optional_float,
    snapshot_only_observation,
    stable_observation_id,
)

SOURCE_ID = "treasury_real_yield_curve"
BASE_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv"
)

TENOR_MAP = {
    "5 YR": "treasury_real_yield_5y",
    "7 YR": "treasury_real_yield_7y",
    "10 YR": "treasury_real_yield_10y",
    "20 YR": "treasury_real_yield_20y",
    "30 YR": "treasury_real_yield_30y",
}


def build_real_yield_url(year: int) -> str:
    params = {
        "type": "daily_treasury_real_yield_curve",
        "field_tdr_date_value": str(year),
        "_format": "csv",
    }
    return f"{BASE_URL}/{year}/all?{urlencode(params)}"


def parse_real_yield_csv(
    raw_payload: bytes,
    retrieved_at: datetime,
    revision_number: int = 0,
) -> ParsedBatch:
    vintage = build_vintage(SOURCE_ID, raw_payload, retrieved_at, revision_number)
    text = raw_payload.decode("utf-8-sig")
    observations: list[Observation] = []

    for row in csv.DictReader(StringIO(text)):
        date_value = row.get("Date")
        if not date_value:
            continue
        observed = datetime.strptime(f"{date_value}+0000", "%m/%d/%Y%z")
        normalized = observed.strftime("%Y-%m-%d")

        for column, feature_id in TENOR_MAP.items():
            if column not in row:
                continue
            observations.append(
                snapshot_only_observation(
                    observation_id=stable_observation_id(
                        SOURCE_ID,
                        feature_id,
                        normalized,
                        vintage.vintage_id,
                    ),
                    feature_id=feature_id,
                    source_id=SOURCE_ID,
                    entity_id=column,
                    value=optional_float(row.get(column)),
                    unit="percent",
                    observation_start=observed,
                    observation_end=observed,
                    ingested_at=retrieved_at,
                    vintage_id=vintage.vintage_id,
                    quality_flag="pit:snapshot-only",
                )
            )

    return ParsedBatch(vintage=vintage, observations=tuple(observations))
