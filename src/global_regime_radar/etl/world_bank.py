import json
from datetime import UTC, datetime
from urllib.parse import urlencode

from global_regime_radar.data.contracts import Observation
from global_regime_radar.etl.common import (
    ParsedBatch,
    build_vintage,
    optional_float,
    snapshot_only_observation,
    stable_observation_id,
)

SOURCE_ID = "world_bank_indicators"
BASE_URL = "https://api.worldbank.org/v2/country"

RESERVE_MONTHS_IMPORTS = "FI.RES.TOTL.MO"
EXTERNAL_DEBT_STOCK = "DT.DOD.DECT.CD"
TOTAL_DEBT_SERVICE_EXPORTS = "DT.TDS.DECT.EX.ZS"


def build_indicator_url(
    countries: list[str],
    indicator: str,
    start_year: int,
    end_year: int,
    per_page: int = 20000,
) -> str:
    country_path = ";".join(country.lower() for country in countries)
    params = {
        "format": "json",
        "date": f"{start_year}:{end_year}",
        "per_page": str(per_page),
    }
    return (
        f"{BASE_URL}/{country_path}/indicator/{indicator}?"
        f"{urlencode(params)}"
    )


def parse_indicator_payload(
    raw_payload: bytes,
    retrieved_at: datetime,
    feature_id: str,
    revision_number: int = 0,
) -> ParsedBatch:
    payload = json.loads(raw_payload)
    if not isinstance(payload, list) or len(payload) < 2:
        raise ValueError("World Bank response must contain metadata and data")

    rows = payload[1] or []
    vintage = build_vintage(SOURCE_ID, raw_payload, retrieved_at, revision_number)
    observations: list[Observation] = []

    for row in rows:
        year = int(row["date"])
        observed = datetime(year, 1, 1, tzinfo=UTC)
        country_code = row.get("countryiso3code") or row.get("country", {}).get("id")
        indicator_code = row.get("indicator", {}).get("id", feature_id)

        observations.append(
            snapshot_only_observation(
                observation_id=stable_observation_id(
                    SOURCE_ID,
                    indicator_code,
                    country_code,
                    year,
                    vintage.vintage_id,
                ),
                feature_id=feature_id,
                source_id=SOURCE_ID,
                entity_id=country_code,
                value=optional_float(row.get("value")),
                unit=None,
                observation_start=observed,
                observation_end=observed,
                ingested_at=retrieved_at,
                vintage_id=vintage.vintage_id,
                quality_flag=(
                    "pit:current-vintage-snapshot-only;"
                    f"indicator:{indicator_code}"
                ),
            )
        )

    return ParsedBatch(vintage=vintage, observations=tuple(observations))
