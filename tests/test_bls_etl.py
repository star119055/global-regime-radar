import json
from datetime import UTC, datetime

from global_regime_radar.etl.bls import (
    TRANSFORMER_PPI_SERIES,
    build_request_payload,
    build_series_url,
    parse_bls_payload,
    parse_bls_single_series_payload,
)

RETRIEVED = datetime(2026, 9, 27, 8, 0, tzinfo=UTC)


def test_bls_request_payload_is_deterministic():
    payload = build_request_payload(["PRS85006092"], 2023, 2026)
    assert json.loads(payload) == {
        "seriesid": ["PRS85006092"],
        "startyear": "2023",
        "endyear": "2026",
    }


def test_bls_parser_keeps_current_history_snapshot_only():
    payload = {
        "status": "REQUEST_SUCCEEDED",
        "responseTime": 10,
        "message": [],
        "Results": {
            "series": [
                {
                    "seriesID": "PRS85006092",
                    "data": [
                        {
                            "year": "2024",
                            "period": "Q01",
                            "periodName": "1st Quarter",
                            "value": "112.3",
                            "footnotes": [{"code": "R", "text": "Revised."}],
                        }
                    ],
                }
            ]
        },
    }

    batch = parse_bls_payload(
        json.dumps(payload).encode(),
        RETRIEVED,
        feature_by_series={"PRS85006092": "labor_productivity_index"},
        unit_by_series={"PRS85006092": "index"},
    )
    observation = batch.observations[0]

    assert observation.value == 112.3
    assert observation.available_at == RETRIEVED
    assert "pit:current-vintage-snapshot-only" in (
        observation.quality_flag or ""
    )
    assert "Revised." in (observation.quality_flag or "")



def test_bls_single_series_url_is_no_key_get_endpoint():
    assert build_series_url(TRANSFORMER_PPI_SERIES).endswith(
        f"/{TRANSFORMER_PPI_SERIES}"
    )


def test_bls_single_series_parser_supports_live_ppi_source_identity():
    payload = {
        "status": "REQUEST_SUCCEEDED",
        "responseTime": 5,
        "message": [],
        "Results": {
            "series": [
                {
                    "seriesID": TRANSFORMER_PPI_SERIES,
                    "data": [
                        {
                            "year": "2026",
                            "period": "M08",
                            "periodName": "August",
                            "value": "418.257",
                            "footnotes": [],
                        }
                    ],
                }
            ]
        },
    }
    batch = parse_bls_single_series_payload(
        json.dumps(payload).encode(),
        RETRIEVED,
        series_id=TRANSFORMER_PPI_SERIES,
        feature_id="transformer_industry_ppi",
        source_id="bls_transformer_ppi",
    )
    observation = batch.observations[0]
    assert batch.vintage.source_id == "bls_transformer_ppi"
    assert observation.source_id == "bls_transformer_ppi"
    assert observation.feature_id == "transformer_industry_ppi"
    assert observation.value == 418.257
