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

SOURCE_ID = "usda_fas_psd"
BASE_URL = (
    "https://apps.fas.usda.gov/PSDOnlineDataServices/api/CommodityData/"
    "GetCommodityDataByYear"
)


def build_commodity_url(commodity_code: str, market_year: int) -> str:
    return f"{BASE_URL}?{urlencode({'commodityCode': commodity_code, 'marketYear': market_year})}"


def request_headers(api_key: str) -> dict[str, str]:
    if not api_key:
        raise ValueError("USDA PSD API key is required")
    return {"Accept": "application/json", "API_KEY": api_key}


def _month_date(calendar_year: int, month: int | None) -> datetime:
    safe_month = month if month is not None and 1 <= month <= 12 else 1
    return datetime(calendar_year, safe_month, 1, tzinfo=UTC)


def parse_commodity_payload(
    raw_payload: bytes,
    retrieved_at: datetime,
    revision_number: int = 0,
) -> ParsedBatch:
    rows = json.loads(raw_payload)
    if not isinstance(rows, list):
        raise TypeError("USDA PSD response must be a JSON list")

    vintage = build_vintage(SOURCE_ID, raw_payload, retrieved_at, revision_number)
    observations: list[Observation] = []

    for row in rows:
        attribute_id = int(row["AttributeId"])
        commodity_code = str(row["CommodityCode"])
        country_code = str(row["CountryCode"])
        market_year = int(row["MarketYear"])
        calendar_year = int(row.get("CalendarYear") or market_year)
        raw_month = row.get("Month")
        month = int(raw_month) if raw_month not in (None, "") else None
        observed = _month_date(calendar_year, month)

        feature_id = f"usda_psd_attribute_{attribute_id}"
        entity_id = f"{country_code}:{commodity_code}"
        quality = (
            "pit:snapshot-only;"
            f"attribute:{row.get('AttributeDescription', '')};"
            f"market_year:{market_year}"
        )
        observations.append(
            snapshot_only_observation(
                observation_id=stable_observation_id(
                    SOURCE_ID,
                    feature_id,
                    entity_id,
                    market_year,
                    month,
                    vintage.vintage_id,
                ),
                feature_id=feature_id,
                source_id=SOURCE_ID,
                entity_id=entity_id,
                value=optional_float(row.get("Value")),
                unit=str(row.get("UnitDescription") or ""),
                observation_start=observed,
                observation_end=observed,
                ingested_at=retrieved_at,
                vintage_id=vintage.vintage_id,
                quality_flag=quality,
            )
        )

    return ParsedBatch(vintage=vintage, observations=tuple(observations))
