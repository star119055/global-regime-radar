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

SOURCE_ID = "eia_api_v2"
BASE_URL = "https://api.eia.gov/v2"


def build_data_url(
    route: str,
    api_key: str,
    data_fields: list[str],
    frequency: str,
    start: str,
    end: str,
    facets: dict[str, list[str]] | None = None,
    length: int = 5000,
) -> str:
    if not api_key:
        raise ValueError("EIA API key is required")

    pairs: list[tuple[str, str]] = [
        ("api_key", api_key),
        ("frequency", frequency),
        ("start", start),
        ("end", end),
        ("length", str(length)),
    ]
    for index, field in enumerate(data_fields):
        pairs.append((f"data[{index}]", field))
    for facet, values in (facets or {}).items():
        for value in values:
            pairs.append((f"facets[{facet}][]", value))

    route = route.strip("/")
    return f"{BASE_URL}/{route}/data/?{urlencode(pairs)}"


def _parse_period(value: str) -> datetime:
    if len(value) == 7:
        return datetime.strptime(f"{value}-01+0000", "%Y-%m-%d%z")
    if len(value) == 4:
        return datetime(int(value), 1, 1, tzinfo=UTC)
    raise ValueError(f"unsupported EIA period: {value}")


def parse_series_payload(
    raw_payload: bytes,
    retrieved_at: datetime,
    *,
    value_field: str,
    feature_id: str,
    unit: str | None,
    entity_fields: tuple[str, ...] = (),
    revision_number: int = 0,
) -> ParsedBatch:
    payload = json.loads(raw_payload)
    rows = payload.get("response", {}).get("data", [])
    vintage = build_vintage(SOURCE_ID, raw_payload, retrieved_at, revision_number)
    observations: list[Observation] = []

    for row in rows:
        period = str(row["period"])
        observed = _parse_period(period)
        entity_id = ":".join(str(row.get(field, "")) for field in entity_fields) or None
        observations.append(
            snapshot_only_observation(
                observation_id=stable_observation_id(
                    SOURCE_ID,
                    feature_id,
                    entity_id,
                    period,
                    vintage.vintage_id,
                ),
                feature_id=feature_id,
                source_id=SOURCE_ID,
                entity_id=entity_id,
                value=optional_float(row.get(value_field)),
                unit=unit,
                observation_start=observed,
                observation_end=observed,
                ingested_at=retrieved_at,
                vintage_id=vintage.vintage_id,
                quality_flag="pit:current-vintage-snapshot-only",
            )
        )

    return ParsedBatch(vintage=vintage, observations=tuple(observations))
