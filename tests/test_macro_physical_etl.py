import json
from datetime import UTC, datetime

import pytest

from global_regime_radar.etl.eia import build_data_url, parse_series_payload
from global_regime_radar.etl.lbnl_queues import (
    parse_curated_snapshots,
    parse_queued_up_html,
)
from global_regime_radar.etl.noaa import parse_oni_text
from global_regime_radar.etl.usda_psd import (
    build_commodity_url,
    parse_commodity_payload,
    request_headers,
)
from global_regime_radar.etl.world_bank import (
    RESERVE_MONTHS_IMPORTS,
    build_indicator_url,
    parse_indicator_payload,
)
from global_regime_radar.routing.stages import EvidenceStage, StageTracker

RETRIEVED = datetime(2026, 9, 27, 8, 0, tzinfo=UTC)


def test_lbnl_queued_up_parser_preserves_annual_snapshot_semantics():
    raw = b"""
    <html><body>
    <p>features interconnection data through the end of 2025.</p>
    <li>As of the end of 2025, there were projects representing
    1,312 GW of generation and approximately 749 GW of storage.</li>
    <li>549 GW of capacity already has a draft or executed
    interconnection agreement (IA) but has not yet reached commercial operations.</li>
    </body></html>
    """
    batch = parse_queued_up_html(raw, RETRIEVED)
    rows = {obs.feature_id: obs for obs in batch.observations}

    assert batch.vintage.source_id == "lbnl_queued_up"
    assert rows["lbnl_active_generation_gw"].value == 1312.0
    assert rows["lbnl_active_storage_gw"].value == 749.0
    assert rows["lbnl_draft_executed_ia_gw"].value == 549.0
    assert rows["lbnl_active_generation_gw"].observation_start == datetime(
        2025, 12, 31, tzinfo=UTC
    )
    assert rows["lbnl_active_generation_gw"].available_at == RETRIEVED
    assert "ia_not_cod" in (rows["lbnl_draft_executed_ia_gw"].quality_flag or "")


def test_lbnl_queued_up_parser_fails_closed_when_key_fields_disappear():
    with pytest.raises(ValueError, match="capacity"):
        parse_queued_up_html(
            b"<html>through the end of 2025 but no capacity fields</html>",
            RETRIEVED,
        )


def test_lbnl_curated_snapshot_respects_available_at_and_future_gate():
    raw = b"""
version: 1
snapshots:
  - snapshot_id: queued-up-2026
    observation_end: "2025-12-31"
    available_at: "2026-05-31T23:59:59+00:00"
    active_generation_gw: 1312
    active_storage_gw: 749
    draft_executed_ia_gw: 549
  - snapshot_id: queued-up-2027
    observation_end: "2026-12-31"
    available_at: "2027-05-31T23:59:59+00:00"
    active_generation_gw: 1500
    active_storage_gw: 800
    draft_executed_ia_gw: 700
"""
    batch = parse_curated_snapshots(raw, RETRIEVED)
    rows = {obs.feature_id: obs for obs in batch.observations}

    assert rows["lbnl_active_generation_gw"].value == 1312.0
    assert rows["lbnl_active_generation_gw"].available_at == datetime(
        2026, 5, 31, 23, 59, 59, tzinfo=UTC
    )
    assert rows["lbnl_active_generation_gw"].observation_start == datetime(
        2025, 12, 31, tzinfo=UTC
    )
    assert "snapshot_id:queued-up-2026" in (
        rows["lbnl_active_generation_gw"].quality_flag or ""
    )


def test_lbnl_curated_snapshot_refuses_prepublication_use():
    raw = b"""
version: 1
snapshots:
  - snapshot_id: queued-up-2026
    observation_end: "2025-12-31"
    available_at: "2026-05-31T23:59:59+00:00"
    active_generation_gw: 1312
    active_storage_gw: 749
    draft_executed_ia_gw: 549
"""
    before_release = datetime(2026, 5, 1, tzinfo=UTC)
    with pytest.raises(ValueError, match="no LBNL snapshot"):
        parse_curated_snapshots(raw, before_release)


def test_noaa_oni_parser_uses_current_vintage_snapshot():
    raw = b"""1950 2026
 2025  -0.70 -0.50 -0.20 0.10 0.20 0.30 0.40 0.50 0.60 0.70 0.80 0.90
 2026   0.80  0.70  0.60 0.50 0.40 0.30 -99.90 -99.90 -99.90 -99.90 -99.90 -99.90
"""
    batch = parse_oni_text(raw, RETRIEVED)

    assert len(batch.observations) == 18
    assert batch.observations[-1].value == 0.30
    assert batch.observations[-1].available_at == RETRIEVED
    assert batch.observations[-1].quality_flag == "pit:current-vintage-snapshot-only"


def test_usda_psd_parser_preserves_attribute_identity():
    payload = [
        {
            "CommodityCode": "0440000",
            "CommodityDescription": "Corn",
            "CountryCode": "US",
            "CountryName": "United States",
            "MarketYear": "2026",
            "CalendarYear": "2026",
            "Month": "9",
            "AttributeId": 88,
            "AttributeDescription": "Ending Stocks",
            "UnitId": 4,
            "UnitDescription": "1000 MT",
            "Value": 12345.0,
        }
    ]
    batch = parse_commodity_payload(json.dumps(payload).encode(), RETRIEVED)
    obs = batch.observations[0]

    assert obs.feature_id == "usda_psd_attribute_88"
    assert obs.entity_id == "US:0440000"
    assert "Ending Stocks" in (obs.quality_flag or "")
    assert obs.available_at == RETRIEVED


def test_usda_url_and_api_key_contract():
    url = build_commodity_url("0440000", 2026)
    assert "commodityCode=0440000" in url
    assert "marketYear=2026" in url
    assert request_headers("secret")["API_KEY"] == "secret"

    with pytest.raises(ValueError, match="API key"):
        request_headers("")


def test_world_bank_indicator_parser_is_snapshot_only():
    payload = [
        {"page": 1, "pages": 1},
        [
            {
                "indicator": {
                    "id": RESERVE_MONTHS_IMPORTS,
                    "value": "Total reserves in months of imports",
                },
                "country": {"id": "PK", "value": "Pakistan"},
                "countryiso3code": "PAK",
                "date": "2025",
                "value": 2.4,
            }
        ],
    ]
    batch = parse_indicator_payload(
        json.dumps(payload).encode(),
        RETRIEVED,
        feature_id="reserve_import_cover_months",
    )
    obs = batch.observations[0]

    assert obs.entity_id == "PAK"
    assert obs.value == 2.4
    assert obs.available_at == RETRIEVED


def test_world_bank_url_is_no_key_v2_query():
    url = build_indicator_url(["pak", "egy"], RESERVE_MONTHS_IMPORTS, 2020, 2026)
    assert "/pak;egy/indicator/" in url
    assert "format=json" in url
    assert "date=2020%3A2026" in url


def test_eia_route_builder_and_parser():
    url = build_data_url(
        "electricity/electric-power-operational-data",
        "key",
        ["generation"],
        "monthly",
        "2026-01",
        "2026-03",
        facets={"fueltypeid": ["WAT", "NG"]},
    )
    assert "api_key=key" in url
    assert "data%5B0%5D=generation" in url
    assert "facets%5Bfueltypeid%5D%5B%5D=WAT" in url

    payload = {
        "response": {
            "data": [
                {
                    "period": "2026-01",
                    "location": "US",
                    "fueltypeid": "WAT",
                    "generation": "25000.5",
                }
            ]
        }
    }
    batch = parse_series_payload(
        json.dumps(payload).encode(),
        RETRIEVED,
        value_field="generation",
        feature_id="eia_generation_mwh",
        unit="MWh",
        entity_fields=("location", "fueltypeid"),
    )
    obs = batch.observations[0]

    assert obs.entity_id == "US:WAT"
    assert obs.value == 25000.5
    assert obs.available_at == RETRIEVED


def test_eia_api_key_is_required():
    with pytest.raises(ValueError, match="API key"):
        build_data_url(
            "electricity/electric-power-operational-data",
            "",
            ["generation"],
            "monthly",
            "2026-01",
            "2026-03",
        )


def test_evidence_stage_progression_is_monotonic():
    tracker = StageTracker()
    confirmed = tracker.advance(
        RETRIEVED,
        EvidenceStage.CONFIRMED,
        "usda-release-2026-09",
    )
    transmitted = tracker.advance(
        datetime(2026, 10, 1, 8, 0, tzinfo=UTC),
        EvidenceStage.MACRO_TRANSMITTED,
        "cpi-release-2026-10",
    )

    assert confirmed is not None
    assert transmitted is not None
    assert tracker.stage == EvidenceStage.MACRO_TRANSMITTED

    with pytest.raises(ValueError, match="cannot move backward"):
        tracker.advance(
            datetime(2026, 10, 2, 8, 0, tzinfo=UTC),
            EvidenceStage.CONFIRMED,
            "late-weather-note",
        )
