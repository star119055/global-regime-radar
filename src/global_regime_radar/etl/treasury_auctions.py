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

SOURCE_ID = "treasury_fiscal_auctions"
ENDPOINT = (
    "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/"
    "v1/accounting/od/auctions_query"
)

FIELD_MAP: dict[str, tuple[str, str]] = {
    "bid_to_cover_ratio": ("auction_bid_to_cover", "ratio"),
    "primary_dealer_accepted": ("auction_primary_dealer_accepted", "USD"),
    "direct_bidder_accepted": ("auction_direct_bidder_accepted", "USD"),
    "indirect_bidder_accepted": ("auction_indirect_bidder_accepted", "USD"),
    "total_accepted": ("auction_total_accepted", "USD"),
}


def build_auction_url(
    start_date: str,
    end_date: str,
    page_size: int = 200,
) -> str:
    fields = [
        "record_date",
        "cusip",
        "security_type",
        "security_term",
        "original_security_term",
        "auction_date",
        *FIELD_MAP,
    ]
    params = {
        "fields": ",".join(fields),
        "filter": f"record_date:gte:{start_date},record_date:lte:{end_date}",
        "sort": "record_date,auction_date,cusip",
        "page[size]": str(page_size),
        "format": "json",
    }
    return f"{ENDPOINT}?{urlencode(params)}"


def parse_auction_payload(
    raw_payload: bytes,
    retrieved_at: datetime,
    revision_number: int = 0,
) -> ParsedBatch:
    payload = json.loads(raw_payload)
    rows = payload.get("data", [])
    vintage = build_vintage(SOURCE_ID, raw_payload, retrieved_at, revision_number)
    observations: list[Observation] = []

    for row in rows:
        cusip = row["cusip"]
        auction_date = parse_date_utc(row["auction_date"])
        for source_field, (feature_id, unit) in FIELD_MAP.items():
            observation_id = stable_observation_id(
                SOURCE_ID,
                feature_id,
                cusip,
                row["auction_date"],
                vintage.vintage_id,
            )
            observations.append(
                snapshot_only_observation(
                    observation_id=observation_id,
                    feature_id=feature_id,
                    source_id=SOURCE_ID,
                    entity_id=cusip,
                    value=optional_float(row.get(source_field)),
                    unit=unit,
                    observation_start=auction_date,
                    observation_end=auction_date,
                    ingested_at=retrieved_at,
                    vintage_id=vintage.vintage_id,
                    quality_flag=(
                        "pit:snapshot-only;"
                        f"record_date:{row.get('record_date', 'unknown')}"
                    ),
                )
            )

    return ParsedBatch(vintage=vintage, observations=tuple(observations))
