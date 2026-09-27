import json
from datetime import UTC, datetime

from global_regime_radar.research.apcr_probe import (
    bls_labor_productivity_series_id,
    run_probe,
)


def _json(value) -> bytes:
    return json.dumps(value).encode()


class FakeFetcher:
    def __call__(self, url: str) -> bytes:
        if url.endswith("/periods"):
            return _json(
                [
                    {"PERIOD_ID": 31, "START_DATE": "2023-10-23", "END_DATE": "2023-11-05"},
                    {"PERIOD_ID": 32, "START_DATE": "2023-11-06", "END_DATE": "2023-11-19"},
                    {"PERIOD_ID": 33, "START_DATE": "2023-11-20", "END_DATE": "2023-12-03"},
                    {"PERIOD_ID": 34, "START_DATE": "2023-12-04", "END_DATE": "2023-12-17"},
                    {"PERIOD_ID": 35, "START_DATE": "2023-12-18", "END_DATE": "2023-12-31"},
                    {"PERIOD_ID": 36, "START_DATE": "2024-01-01", "END_DATE": "2024-01-14"},
                    {"PERIOD_ID": 84, "END_DATE": "2025-09-28"},
                    {"PERIOD_ID": 88, "END_DATE": "2025-12-07"},
                ]
            )
        if url.endswith("/questions"):
            return _json(
                [
                    {
                        "QUESTION_ID": "6",
                        "QUESTION": (
                            "In the last two weeks, did this business use "
                            "Artificial Intelligence (AI) in producing goods or services?"
                        ),
                    },
                    {"QUESTION_ID": "OTHER", "QUESTION": "Other question"},
                ]
            )
        if url.endswith("/questions/answers"):
            return _json(
                [
                    {
                        "QUESTION_ID": "6",
                        "QUESTION": "Artificial Intelligence in the last two weeks",
                        "OPTION_TEXT": "AI current",
                        "ANSWER_ID": "15",
                        "ANSWER": "Yes",
                    }
                ]
            )
        if url.endswith("/strata"):
            return _json(
                [
                    {
                        "STRATA_TYPE": "sector",
                        "STRATA_VALUE": "Information",
                        "NAICS": "51",
                        "LABEL": "Information sector",
                    },
                    {
                        "STRATA_TYPE": "state",
                        "STRATA_VALUE": "MA",
                        "LABEL": "Massachusetts",
                    },
                ]
            )
        if any(
            url.endswith(f"/periods/{period_id}/data")
            for period_id in (31, 32, 33, 34, 35, 36)
        ):
            period_id = int(url.split("/periods/")[1].split("/")[0])
            return _json(
                [
                    {
                        "PERIOD_ID": str(period_id),
                        "DATE_RANGE": "fixture",
                        "QUESTION": (
                            "In the last two weeks, did this business use "
                            "Artificial Intelligence (AI) in producing goods or services?"
                        ),
                        "OPTION_TEXT": "AI current",
                        "ANSWER": "Yes",
                        "NAICS2": "51",
                        "NAICS3": "",
                        "STATE": "",
                        "MSA": "",
                        "EMPSIZE": "",
                        "ESTIMATE_PERCENTAGE": 20.0 + period_id / 100.0,
                        "STANDARD_ERROR": 1.1,
                    },
                    {
                        "PERIOD_ID": str(period_id),
                        "DATE_RANGE": "fixture",
                        "QUESTION": (
                            "In the last two weeks, did this business use "
                            "Artificial Intelligence (AI) in producing goods or services?"
                        ),
                        "OPTION_TEXT": "AI current",
                        "ANSWER": "Yes",
                        "NAICS2": "52",
                        "NAICS3": "",
                        "STATE": "",
                        "MSA": "",
                        "EMPSIZE": "",
                        "ESTIMATE_PERCENTAGE": 12.0 + period_id / 100.0,
                        "STANDARD_ERROR": 0.9,
                    },
                    {
                        "PERIOD_ID": str(period_id),
                        "DATE_RANGE": "fixture",
                        "QUESTION": (
                            "In the last two weeks, did this business use "
                            "Artificial Intelligence (AI) in producing goods or services?"
                        ),
                        "OPTION_TEXT": "AI current",
                        "ANSWER": "Yes",
                        "NAICS2": "54",
                        "NAICS3": "",
                        "STATE": "",
                        "MSA": "",
                        "EMPSIZE": "",
                        "ESTIMATE_PERCENTAGE": 18.0 + period_id / 100.0,
                        "STANDARD_ERROR": 0.8,
                    },
                    {
                        "PERIOD_ID": str(period_id),
                        "DATE_RANGE": "fixture",
                        "QUESTION": (
                            "In the last two weeks, did this business use "
                            "Artificial Intelligence (AI) in producing goods or services?"
                        ),
                        "OPTION_TEXT": "AI current",
                        "ANSWER": "Yes",
                        "NAICS2": "44",
                        "NAICS3": "",
                        "STATE": "",
                        "MSA": "",
                        "EMPSIZE": "",
                        "ESTIMATE_PERCENTAGE": 6.0 + period_id / 100.0,
                        "STANDARD_ERROR": 0.7,
                    },
                    {
                        "PERIOD_ID": str(period_id),
                        "QUESTION": "Other question",
                        "OPTION_TEXT": "Other",
                        "ANSWER": "Yes",
                        "NAICS2": "51",
                        "ESTIMATE_PERCENTAGE": 10.0,
                    },
                ]
            )
        if "/periods/84/data/sector/51" in url:
            return _json(
                [
                    {
                        "PERIOD_ID": 84,
                        "SECTOR": "51",
                        "QUESTION_ID": "AI_USE",
                        "ANSWER_ID": "1",
                        "ESTIMATE": 18.5,
                        "STANDARD_ERROR": 1.2,
                    }
                ]
            )
        if "/periods/88/data/sector/51" in url:
            return _json(
                [
                    {
                        "PERIOD_ID": 88,
                        "SECTOR": "51",
                        "QUESTION_ID": "AI_USE_NEW",
                        "ANSWER_ID": "1",
                        "ESTIMATE": 39.7,
                        "STANDARD_ERROR": 1.5,
                    }
                ]
            )
        if url.endswith("/ip.industry"):
            return (
                b"industry_code\tnaics_code\tindustry_text\tdisplay_level\tselectable\tsort_sequence\n"
                b"N51____\t51\tInformation\t0\tT\t1\n"
                b"N511___\t511\tPublishing industries\t1\tT\t2\n"
            )
        if url.endswith("/ip.measure"):
            return (
                b"measure_code\tmeasure_text\tdisplay_level\tselectable\tsort_sequence\n"
                b"L00\tLabor productivity\t0\tT\t1\n"
                b"W00\tOutput per worker\t0\tT\t2\n"
            )
        if url.endswith("/ip.series"):
            return (
                b"series_id\tseasonal\tsector_code\tindustry_code\tmeasure_code\t"
                b"duration_code\tbase_year\ttype_code\tarea_code\tseries_title\t"
                b"footnote_codes\tbegin_year\tbegin_period\tend_year\tend_period\n"
                b"IPUBN51____L000000000\tU\tB\tN51____\tL00\t0\t2017\tI\t"
                b"000000\tLabor productivity, Information\t\t1987\tA01\t2025\tA01\n"
            )
        if url.endswith("/ip.data.0.Current"):
            return (
                b"series_id\tyear\tperiod\tvalue\tfootnote_codes\n"
                b"IPUBN51____L000000000\t2025\tA01\t118.2\t\n"
            )
        raise AssertionError(f"unexpected url: {url}")


class FakePoster:
    def __call__(self, url: str, payload: dict[str, object]) -> bytes:
        assert url.endswith("/publicAPI/v2/timeseries/data/")
        series_ids = list(payload["seriesid"])
        rows = []
        for series_id in series_ids:
            rows.append(
                {
                    "seriesID": series_id,
                    "data": [
                        {
                            "year": str(year),
                            "period": "A01",
                            "periodName": "Annual",
                            "value": str(100 + year - 2020),
                            "footnotes": [],
                        }
                        for year in range(2021, 2026)
                    ],
                }
            )
        return _json(
            {
                "status": "REQUEST_SUCCEEDED",
                "responseTime": 1,
                "message": [],
                "Results": {"series": rows},
            }
        )


def test_apcr_probe_discovers_semantic_btos_and_bls_candidates():
    payload = run_probe(
        retrieved_at=datetime(2026, 9, 27, tzinfo=UTC),
        fetcher=FakeFetcher(),
        json_poster=FakePoster(),
    )
    assert payload["authoritative_state_input"] is False
    assert payload["A_coverage_increment"] == 0.0
    assert payload["failures"] == {}

    btos = payload["btos"]
    assert len(btos["questions"]["ai_question_candidates"]) == 1
    assert len(btos["answers"]["ai_yes_candidates"]) == 1
    assert len(btos["periods"]["baseline_periods_31_36"]) == 6
    assert btos["strata"]["sector_naics_candidates"][0]["NAICS"] == "51"
    assert btos["baseline_data"]["31"]["ai_current_row_count"] == 4
    assert btos["baseline_data"]["31"]["naics2_candidate_count"] == 4
    assert btos["baseline_candidate_diagnostics"]["naics2_values"] == [
        "44",
        "51",
        "52",
        "54",
    ]
    assert btos["baseline_candidate_diagnostics"]["national_naics2_total_rows"] == 24
    frozen = btos["baseline_candidate_diagnostics"]["frozen_treatment_candidate"]
    assert len(frozen) == 4
    assert btos["baseline_candidate_diagnostics"]["freeze_error"] is None
    assert btos["baseline_candidate_diagnostics"]["authoritative_treatment_frozen"] is False
    assert "ESTIMATE" in btos["sector_data"]["sector_old"]["row_keys"]

    bls = payload["bls"]
    assert bls["labor_productivity_measure_candidates"][0]["measure_code"] == "L00"
    candidate = bls["labor_productivity_sector_series"][0]
    assert candidate["naics_code"] == "51"
    assert candidate["series_id"] == "IPUBN51____L000000000"

    api_probe = payload["bls_api_outcome_probe"]
    assert api_probe["status"] == "COMPLETE"
    assert set(api_probe["valid_series"]) == {"44", "51", "52", "54"}
    assert api_probe["missing_series"] == []
    assert len(api_probe["annual_observations"]["51"]) == 5


def test_apcr_probe_hashes_every_downloaded_source():
    payload = run_probe(
        retrieved_at=datetime(2026, 9, 27, tzinfo=UTC),
        fetcher=FakeFetcher(),
        json_poster=FakePoster(),
    )
    assert len(payload["sources"]) == 16
    assert all(len(row["sha256"]) == 64 for row in payload["sources"].values())
    assert all(row["bytes"] > 0 for row in payload["sources"].values())



def test_apcr_probe_isolates_source_failure_and_keeps_artifact_shape():
    class PartialFetcher(FakeFetcher):
        def __call__(self, url: str) -> bytes:
            if url.endswith("/ip.series"):
                raise OSError("BLS blocked")
            return super().__call__(url)

    payload = run_probe(
        retrieved_at=datetime(2026, 9, 27, tzinfo=UTC),
        fetcher=PartialFetcher(),
        json_poster=FakePoster(),
    )
    assert payload["schema_version"] == 2
    assert payload["bls"]["status"] == "PARTIAL"
    assert payload["bls"]["missing_sources"] == ["series"]
    assert payload["failures"]["series"]["error_type"] == "OSError"
    assert payload["authoritative_state_input"] is False
    assert payload["A_coverage_increment"] == 0.0



def test_apcr_probe_excludes_incomplete_treatment_entity_without_imputation():
    class IncompleteEntityFetcher(FakeFetcher):
        def __call__(self, url: str) -> bytes:
            raw = super().__call__(url)
            if url.endswith("/periods/36/data"):
                rows = json.loads(raw)
                rows.append(
                    {
                        "PERIOD_ID": "36",
                        "DATE_RANGE": "fixture",
                        "QUESTION": (
                            "In the last two weeks, did this business use "
                            "Artificial Intelligence (AI) in producing goods or services?"
                        ),
                        "OPTION_TEXT": "AI current",
                        "ANSWER": "Yes",
                        "NAICS2": "11",
                        "NAICS3": "",
                        "STATE": "",
                        "MSA": "",
                        "EMPSIZE": "",
                        "ESTIMATE_PERCENTAGE": 1.5,
                        "STANDARD_ERROR": 0.4,
                    }
                )
                return _json(rows)
            return raw

    payload = run_probe(
        retrieved_at=datetime(2026, 9, 27, tzinfo=UTC),
        fetcher=IncompleteEntityFetcher(),
        json_poster=FakePoster(),
    )
    diag = payload["btos"]["baseline_candidate_diagnostics"]
    assert "11" not in diag["complete_entities"]
    assert diag["incomplete_entities_missing_periods"]["11"] == [31, 32, 33, 34, 35]
    assert len(diag["frozen_treatment_candidate"]) == 4
    assert diag["freeze_error"] is None



def test_bls_productivity_series_id_uses_explicit_sector_crosswalk():
    assert bls_labor_productivity_series_id("51") == "IPUBN51____L000000000"
    assert bls_labor_productivity_series_id("31") == "IPUBN31_33_L000000000"
    assert bls_labor_productivity_series_id("44") == "IPUBN44_45_L000000000"
