import json
from datetime import UTC, datetime

from global_regime_radar.etl.bls import build_request_payload, parse_bls_payload

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
