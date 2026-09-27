import json
from datetime import UTC, datetime

from global_regime_radar.data.contracts import Observation
from global_regime_radar.etl.common import (
    ParsedBatch,
    build_vintage,
    optional_float,
    snapshot_only_observation,
    stable_observation_id,
)

SOURCE_ID = "bls_productivity"
ENDPOINT = "https://api.bls.gov/publicAPI/v2/timeseries/data/"


def build_request_payload(
    series_ids: list[str],
    start_year: int,
    end_year: int,
    registration_key: str | None = None,
) -> bytes:
    if not series_ids:
        raise ValueError("at least one BLS series_id is required")
    if end_year < start_year:
        raise ValueError("end_year must be >= start_year")

    payload: dict[str, object] = {
        "seriesid": series_ids,
        "startyear": str(start_year),
        "endyear": str(end_year),
    }
    if registration_key:
        payload["registrationkey"] = registration_key
    return json.dumps(payload, separators=(",", ":")).encode()


def _period_start(year: int, period: str) -> datetime:
    if period.startswith("Q") and period[1:].isdigit():
        quarter = int(period[1:])
        if 1 <= quarter <= 4:
            return datetime(year, 1 + (quarter - 1) * 3, 1, tzinfo=UTC)
    if period.startswith("M") and period[1:].isdigit():
        month = int(period[1:])
        if 1 <= month <= 12:
            return datetime(year, month, 1, tzinfo=UTC)
    if period == "A01":
        return datetime(year, 1, 1, tzinfo=UTC)
    raise ValueError(f"unsupported BLS period: {period}")


def parse_bls_payload(
    raw_payload: bytes,
    retrieved_at: datetime,
    *,
    feature_by_series: dict[str, str],
    unit_by_series: dict[str, str | None] | None = None,
    revision_number: int = 0,
) -> ParsedBatch:
    payload = json.loads(raw_payload)
    if payload.get("status") != "REQUEST_SUCCEEDED":
        raise ValueError(f"BLS request failed: {payload.get('message', [])}")

    vintage = build_vintage(SOURCE_ID, raw_payload, retrieved_at, revision_number)
    observations: list[Observation] = []
    units = unit_by_series or {}

    for series in payload.get("Results", {}).get("series", []):
        series_id = series["seriesID"]
        feature_id = feature_by_series.get(series_id)
        if feature_id is None:
            continue

        for row in series.get("data", []):
            period = row["period"]
            if period == "M13":
                continue
            observed = _period_start(int(row["year"]), period)
            footnotes = ";".join(
                footnote.get("text", "")
                for footnote in row.get("footnotes", [])
                if footnote
            )
            quality = "pit:current-vintage-snapshot-only"
            if footnotes:
                quality += f";footnotes:{footnotes}"

            observations.append(
                snapshot_only_observation(
                    observation_id=stable_observation_id(
                        SOURCE_ID,
                        series_id,
                        row["year"],
                        period,
                        vintage.vintage_id,
                    ),
                    feature_id=feature_id,
                    source_id=SOURCE_ID,
                    entity_id=series_id,
                    value=optional_float(row.get("value")),
                    unit=units.get(series_id),
                    observation_start=observed,
                    observation_end=observed,
                    ingested_at=retrieved_at,
                    vintage_id=vintage.vintage_id,
                    quality_flag=quality,
                )
            )

    return ParsedBatch(vintage=vintage, observations=tuple(observations))
