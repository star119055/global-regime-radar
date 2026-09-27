import json
from datetime import UTC, datetime

from global_regime_radar.etl.nyfed import (
    parse_primary_dealer_catalog,
    parse_repo_payload,
    parse_sofr_payload,
)
from global_regime_radar.etl.ofr import parse_single_series_payload
from global_regime_radar.etl.treasury_auctions import (\n    parse_auction_payload,\n    parse_security_term_years,\n)
from global_regime_radar.etl.treasury_real_yields import parse_real_yield_csv

RETRIEVED = datetime(2026, 9, 27, 8, 0, tzinfo=UTC)


def test_treasury_auction_parser_is_snapshot_only():
    payload = {
        "data": [
            {
                "record_date": "2026-09-24",
                "cusip": "91282CXX0",
                "security_type": "Note",
                "security_term": "2-Year",
                "original_security_term": "2-Year",
                "auction_date": "2026-09-24",
                "bid_to_cover_ratio": "2.65",
                "primary_dealer_accepted": "12000000000",
                "direct_bidder_accepted": "4000000000",
                "indirect_bidder_accepted": "44000000000",
                "total_accepted": "60000000000",
            }
        ]
    }
    batch = parse_auction_payload(json.dumps(payload).encode(), RETRIEVED)

    assert len(batch.observations) == 6
    bid_to_cover = next(
        obs for obs in batch.observations if obs.feature_id == "auction_bid_to_cover"
    )
    assert bid_to_cover.value == 2.65
    assert bid_to_cover.available_at == RETRIEVED
    assert "pit:snapshot-only" in (bid_to_cover.quality_flag or "")
    term = next(
        obs
        for obs in batch.observations
        if obs.feature_id == "auction_original_term_years"
    )
    assert term.value == 2.0
    assert term.unit == "years"


def test_security_term_parser_handles_common_treasury_terms():
    assert parse_security_term_years("2-Year") == 2.0
    assert parse_security_term_years("26-Week") == pytest.approx(182.0 / 365.25)
    assert parse_security_term_years("1-Year 6-Month") == 1.5
    assert parse_security_term_years("unknown") is None


def test_sofr_parser_preserves_revision_signal_and_does_not_backdate():
    payload = {
        "refRates": [
            {
                "effectiveDate": "2026-09-24",
                "type": "SOFR",
                "percentRate": 3.88,
                "volumeInBillions": 2990,
                "percentPercentile1": 3.80,
                "percentPercentile99": 3.95,
                "revisionIndicator": "r",
            }
        ]
    }
    batch = parse_sofr_payload(json.dumps(payload).encode(), RETRIEVED)

    rate = next(obs for obs in batch.observations if obs.feature_id == "sofr_rate")
    assert rate.value == 3.88
    assert rate.available_at == RETRIEVED
    assert "revision_indicator:r" in (rate.quality_flag or "")


def test_repo_parser_uses_last_updated_as_point_in_time_gate():
    payload = {
        "repo": {
            "operations": [
                {
                    "operationId": "RP 092526 27",
                    "operationDate": "2026-09-25",
                    "lastUpdated": "2026-09-25 13:45:37",
                    "totalAmtSubmitted": 1000000,
                    "totalAmtAccepted": 1000000,
                }
            ]
        }
    }
    batch = parse_repo_payload(json.dumps(payload).encode(), RETRIEVED)

    accepted = next(
        obs for obs in batch.observations if obs.feature_id == "repo_total_accepted"
    )
    assert accepted.value == 1000000
    assert accepted.unit == "USD_millions"
    assert accepted.available_at < RETRIEVED
    assert accepted.published_at == accepted.available_at


def test_primary_dealer_catalog_parser():
    payload = {
        "pd": {
            "timeseries": [
                {
                    "seriesbreak": "SBN2024",
                    "keyid": "PDSORA-UTSETTOT",
                    "description": "Treasury repo agreements",
                }
            ]
        }
    }
    catalog = parse_primary_dealer_catalog(json.dumps(payload).encode())
    assert catalog["SBN2024:PDSORA-UTSETTOT"] == "Treasury repo agreements"


def test_ofr_current_vintage_is_snapshot_only():
    mnemonic = "TFF-LF_TREAS_NET_POSITION"
    payload = {
        mnemonic: {
            "timeseries": {
                "value": [
                    {"date": "2026-09-01", "value": "123.4"},
                    {"date": "2026-09-08", "value": "125.0"},
                ]
            }
        }
    }
    batch = parse_single_series_payload(
        json.dumps(payload).encode(),
        RETRIEVED,
        mnemonic,
        "treasury_futures_net_position",
        "USD",
    )

    assert len(batch.observations) == 2
    assert all(obs.available_at == RETRIEVED for obs in batch.observations)
    assert all(
        obs.quality_flag == "pit:current-vintage-snapshot-only"
        for obs in batch.observations
    )


def test_real_yield_csv_parser():
    raw = (
        b"Date,5 YR,7 YR,10 YR,20 YR,30 YR\n"
        b"09/24/2026,1.10,1.20,1.30,1.40,1.50\n"
    )
    batch = parse_real_yield_csv(raw, RETRIEVED)

    ten_year = next(
        obs for obs in batch.observations if obs.feature_id == "treasury_real_yield_10y"
    )
    assert ten_year.value == 1.30
    assert ten_year.unit == "percent"
    assert ten_year.available_at == RETRIEVED
