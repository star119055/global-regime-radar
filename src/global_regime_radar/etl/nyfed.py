import json
from datetime import datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from global_regime_radar.data.contracts import Observation
from global_regime_radar.etl.common import (
    ParsedBatch,
    build_vintage,
    optional_float,
    parse_date_utc,
    snapshot_only_observation,
    stable_observation_id,
)

NY = ZoneInfo("America/New_York")

SOFR_SOURCE_ID = "nyfed_sofr"
SOFR_ENDPOINT = "https://markets.newyorkfed.org/api/rates/secured/sofr/search.json"

REPO_SOURCE_ID = "nyfed_repo_operations"
REPO_ENDPOINT = "https://markets.newyorkfed.org/api/rp/repo/all/results/search.json"

PRIMARY_DEALER_SOURCE_ID = "nyfed_primary_dealer"
PRIMARY_DEALER_CATALOG_ENDPOINT = (
    "https://markets.newyorkfed.org/api/pd/list/timeseries.json"
)


def build_sofr_url(start_date: str, end_date: str) -> str:
    return f"{SOFR_ENDPOINT}?{urlencode({'startDate': start_date, 'endDate': end_date})}"


def build_repo_url(start_date: str, end_date: str) -> str:
    return f"{REPO_ENDPOINT}?{urlencode({'startDate': start_date, 'endDate': end_date})}"


def parse_sofr_payload(
    raw_payload: bytes,
    retrieved_at: datetime,
    revision_number: int = 0,
) -> ParsedBatch:
    payload = json.loads(raw_payload)
    vintage = build_vintage(SOFR_SOURCE_ID, raw_payload, retrieved_at, revision_number)
    observations: list[Observation] = []

    fields = {
        "percentRate": ("sofr_rate", "percent"),
        "volumeInBillions": ("sofr_volume", "USD_billions"),
        "percentPercentile1": ("sofr_percentile_1", "percent"),
        "percentPercentile99": ("sofr_percentile_99", "percent"),
    }

    for row in payload.get("refRates", []):
        if row.get("type") not in (None, "SOFR"):
            continue
        effective_date = parse_date_utc(row["effectiveDate"])
        revision_indicator = row.get("revisionIndicator") or ""
        flag = "pit:snapshot-only"
        if revision_indicator:
            flag += f";revision_indicator:{revision_indicator}"

        for source_field, (feature_id, unit) in fields.items():
            observations.append(
                snapshot_only_observation(
                    observation_id=stable_observation_id(
                        SOFR_SOURCE_ID,
                        feature_id,
                        row["effectiveDate"],
                        vintage.vintage_id,
                    ),
                    feature_id=feature_id,
                    source_id=SOFR_SOURCE_ID,
                    entity_id="SOFR",
                    value=optional_float(row.get(source_field)),
                    unit=unit,
                    observation_start=effective_date,
                    observation_end=effective_date,
                    ingested_at=retrieved_at,
                    vintage_id=vintage.vintage_id,
                    quality_flag=flag,
                )
            )

    return ParsedBatch(vintage=vintage, observations=tuple(observations))


def _parse_nyfed_last_updated(value: str) -> datetime:
    local = datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=NY)
    return local.astimezone(ZoneInfo("UTC"))


def parse_repo_payload(
    raw_payload: bytes,
    retrieved_at: datetime,
    revision_number: int = 0,
) -> ParsedBatch:
    payload = json.loads(raw_payload)
    vintage = build_vintage(REPO_SOURCE_ID, raw_payload, retrieved_at, revision_number)
    observations: list[Observation] = []

    for row in payload.get("repo", {}).get("operations", []):
        operation_id = row["operationId"]
        operation_date = parse_date_utc(row["operationDate"])
        source_updated_at = _parse_nyfed_last_updated(row["lastUpdated"])
        available_at = min(source_updated_at, retrieved_at)

        metrics = {
            "repo_total_submitted": row.get("totalAmtSubmitted"),
            "repo_total_accepted": row.get("totalAmtAccepted"),
        }

        for feature_id, raw_value in metrics.items():
            observations.append(
                Observation(
                    observation_id=stable_observation_id(
                        REPO_SOURCE_ID,
                        feature_id,
                        operation_id,
                        vintage.vintage_id,
                    ),
                    feature_id=feature_id,
                    source_id=REPO_SOURCE_ID,
                    entity_id=operation_id,
                    value=optional_float(raw_value),
                    unit="USD_millions",
                    observation_start=operation_date,
                    observation_end=operation_date,
                    published_at=source_updated_at,
                    available_at=available_at,
                    ingested_at=retrieved_at,
                    vintage_id=vintage.vintage_id,
                    quality_flag="pit:source-lastUpdated",
                )
            )

    return ParsedBatch(vintage=vintage, observations=tuple(observations))


def parse_primary_dealer_catalog(raw_payload: bytes) -> dict[str, str]:
    payload = json.loads(raw_payload)
    result: dict[str, str] = {}
    for row in payload.get("pd", {}).get("timeseries", []):
        key = f"{row['seriesbreak']}:{row['keyid']}"
        result[key] = row["description"]
    return result
