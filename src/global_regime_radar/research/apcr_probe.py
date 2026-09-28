from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from global_regime_radar.live.http import (
    FetchBytes,
    PostJsonBytes,
    fetch_bytes,
    post_json_bytes,
)
from global_regime_radar.research.bls_major_productivity import (
    parse_major_industry_labor_productivity,
)
from global_regime_radar.modules.apcr import (
    APCRTreatmentObservation,
    freeze_apcr_baseline_treatment,
)

CENSUS_BASE = "https://www.census.gov/hfp/btos/api"
BTOS_PERIODS_URL = f"{CENSUS_BASE}/periods"
BTOS_QUESTIONS_URL = f"{CENSUS_BASE}/questions"
BTOS_ANSWERS_URL = f"{CENSUS_BASE}/questions/answers"
BTOS_STRATA_URL = f"{CENSUS_BASE}/strata"

BLS_IP_BASE = "https://download.bls.gov/pub/time.series/ip"
BLS_IP_INDUSTRY_URL = f"{BLS_IP_BASE}/ip.industry"
BLS_IP_MEASURE_URL = f"{BLS_IP_BASE}/ip.measure"
BLS_IP_SERIES_URL = f"{BLS_IP_BASE}/ip.series"
BLS_IP_CURRENT_URL = f"{BLS_IP_BASE}/ip.data.0.Current"
BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

BLS_MAJOR_RELEASES = {
    2021: (
        "2022-11-18",
        "https://www.bls.gov/news.release/archives/prod5_11182022.htm",
    ),
    2022: (
        "2023-11-21",
        "https://www.bls.gov/news.release/archives/prod5_11212023.htm",
    ),
    2023: (
        "2024-12-04",
        "https://www.bls.gov/news.release/archives/prod5_12042024.htm",
    ),
    2024: (
        "2025-12-19",
        "https://www.bls.gov/news.release/prod5.t05.htm",
    ),
}

BLS_MAJOR_LP_INDEX_SERIES = {
    "23": "MPU0023062",
    "31": "MPU9900062",
    "42": "MPU0042062",
    "44": "MPU0044062",
    "51": "MPU0051062",
    "52": "MPU0052062",
    "53": "MPU0053062",
    "54": "MPU0054062",
    "56": "MPU0056062",
    "61": "MPU0061062",
    "62": "MPU0062062",
    "71": "MPU0071062",
    "72": "MPU0072062",
    "81": "MPU0081062",
}


OLD_WORDING_PROBE_PERIOD = 84
NEW_WORDING_PROBE_PERIOD = 88
PROBE_SECTOR = "51"
BASELINE_PERIOD_IDS = (31, 32, 33, 34, 35, 36)



def bls_labor_productivity_series_id(naics2: str) -> str:
    series_id = BLS_MAJOR_LP_INDEX_SERIES.get(naics2)
    if series_id is None:
        raise ValueError(f"unsupported APCR BLS NAICS2 crosswalk: {naics2}")
    return series_id


def summarize_bls_api(
    raw: bytes,
    *,
    requested_by_naics: dict[str, str],
) -> dict[str, Any]:
    payload = json.loads(raw)
    status = str(payload.get("status", ""))
    if status != "REQUEST_SUCCEEDED":
        return {
            "status": status or "REQUEST_FAILED",
            "messages": payload.get("message", []),
            "requested_series": requested_by_naics,
            "valid_series": {},
            "missing_series": sorted(requested_by_naics),
            "annual_observations": {},
        }

    by_series = {
        str(row.get("seriesID", "")): row
        for row in payload.get("Results", {}).get("series", [])
        if isinstance(row, dict)
    }
    valid: dict[str, str] = {}
    missing: list[str] = []
    annual: dict[str, list[dict[str, object]]] = {}

    for naics2, series_id in sorted(requested_by_naics.items()):
        series = by_series.get(series_id)
        rows = [] if series is None else [
            row
            for row in series.get("data", [])
            if str(row.get("period", "")) == "A01"
            and row.get("value") not in (None, "")
        ]
        if not rows:
            missing.append(naics2)
            continue
        valid[naics2] = series_id
        annual[naics2] = [
            {
                "year": int(row["year"]),
                "period": str(row["period"]),
                "value": float(row["value"]),
                "footnotes": [
                    footnote.get("text", "")
                    for footnote in row.get("footnotes", [])
                    if isinstance(footnote, dict) and footnote.get("text")
                ],
            }
            for row in rows
        ]

    return {
        "status": "COMPLETE" if not missing else "PARTIAL",
        "messages": payload.get("message", []),
        "requested_series": requested_by_naics,
        "valid_series": valid,
        "missing_series": missing,
        "annual_observations": annual,
    }

@dataclass(frozen=True)
class FetchRecord:
    source_id: str
    url: str
    raw: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.raw).hexdigest()


def _json_rows(raw: bytes) -> tuple[str, list[dict[str, Any]], list[str]]:
    payload = json.loads(raw)
    payload_type = type(payload).__name__
    rows: list[dict[str, Any]] = []

    if isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
    elif isinstance(payload, dict):
        for value in payload.values():
            if isinstance(value, list) and all(
                isinstance(row, dict) for row in value
            ):
                rows = list(value)
                break
        if not rows:
            rows = [payload]

    keys = sorted({str(key) for row in rows for key in row})
    return payload_type, rows, keys


def _string_blob(row: dict[str, Any]) -> str:
    return " ".join(
        str(value)
        for value in row.values()
        if isinstance(value, (str, int, float))
    ).lower()


def _candidate_rows(
    rows: list[dict[str, Any]],
    *,
    required_terms: tuple[str, ...],
) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        blob = _string_blob(row)
        if all(term.lower() in blob for term in required_terms):
            result.append(row)
    return result


def _safe_candidate(row: dict[str, Any]) -> dict[str, Any]:
    allowed_tokens = (
        "period",
        "question",
        "answer",
        "sector",
        "strata",
        "naics",
        "industry",
        "category",
        "group",
        "estimate",
        "standard",
        "error",
        "date",
        "id",
        "text",
        "label",
        "name",
        "value",
    )
    return {
        str(key): value
        for key, value in row.items()
        if any(token in str(key).lower() for token in allowed_tokens)
    }



def _btos_ai_current_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        blob = _string_blob(row)
        if "artificial intelligence" not in blob or "last two weeks" not in blob:
            continue
        option_text = str(row.get("OPTION_TEXT", "")).strip().lower()
        answer = str(row.get("ANSWER", "")).strip().lower()
        if option_text and option_text != "ai current":
            continue
        if answer and answer != "yes":
            continue
        result.append(row)
    return result


def _btos_naics2_treatment_candidates(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates = []
    for row in _btos_ai_current_rows(rows):
        naics2 = str(row.get("NAICS2", "")).strip()
        if not re.fullmatch(r"\d{2}", naics2):
            continue
        estimate = row.get("ESTIMATE_PERCENTAGE")
        if estimate in (None, ""):
            continue
        candidates.append(
            {
                "PERIOD_ID": str(row.get("PERIOD_ID", "")),
                "DATE_RANGE": row.get("DATE_RANGE"),
                "NAICS2": naics2,
                "STATE": row.get("STATE"),
                "MSA": row.get("MSA"),
                "EMPSIZE": row.get("EMPSIZE"),
                "ESTIMATE_PERCENTAGE": estimate,
                "STANDARD_ERROR": row.get("STANDARD_ERROR"),
                "QUESTION": row.get("QUESTION"),
                "OPTION_TEXT": row.get("OPTION_TEXT"),
                "ANSWER": row.get("ANSWER"),
            }
        )
    return candidates

def summarize_btos(records: dict[str, FetchRecord]) -> dict[str, Any]:
    periods_type, period_rows, period_keys = _json_rows(records["periods"].raw)
    questions_type, question_rows, question_keys = _json_rows(
        records["questions"].raw
    )
    answers_type, answer_rows, answer_keys = _json_rows(records["answers"].raw)
    strata_type, strata_rows, strata_keys = _json_rows(records["strata"].raw)

    ai_questions = _candidate_rows(
        question_rows,
        required_terms=("artificial intelligence",),
    )
    ai_current = [
        row for row in ai_questions if "last two weeks" in _string_blob(row)
    ]
    yes_ai_answers = [
        row
        for row in answer_rows
        if "artificial intelligence" in _string_blob(row)
        and re.search(r"\byes\b", _string_blob(row))
    ]

    sector_summaries: dict[str, Any] = {}
    for key in ("sector_old", "sector_new"):
        payload_type, rows, keys = _json_rows(records[key].raw)
        sector_summaries[key] = {
            "payload_type": payload_type,
            "row_count": len(rows),
            "row_keys": keys,
            "sample_rows": [_safe_candidate(row) for row in rows[:3]],
        }

    baseline_periods = [
        row
        for row in period_rows
        if int(row.get("PERIOD_ID", -1)) in BASELINE_PERIOD_IDS
    ]
    strata_candidates = [
        row
        for row in strata_rows
        if any(
            term in _string_blob(row)
            for term in ("sector", "naics", "industry")
        )
    ]

    baseline_data: dict[str, Any] = {}
    combined_candidates: list[dict[str, Any]] = []
    for period_id in BASELINE_PERIOD_IDS:
        key = f"period{period_id}_all"
        payload_type, rows, keys = _json_rows(records[key].raw)
        ai_rows = _btos_ai_current_rows(rows)
        candidates = _btos_naics2_treatment_candidates(rows)
        combined_candidates.extend(candidates)
        baseline_data[str(period_id)] = {
            "payload_type": payload_type,
            "row_count": len(rows),
            "row_keys": keys,
            "ai_current_row_count": len(ai_rows),
            "naics2_candidate_count": len(candidates),
            "sample_ai_current_rows": [
                _safe_candidate(row) for row in ai_rows[:20]
            ],
            "sample_naics2_candidates": candidates[:40],
        }

    strata_dimensions = {
        name: sorted(
            {
                str(row.get(name, "")).strip()
                for row in combined_candidates
                if str(row.get(name, "")).strip()
            }
        )
        for name in ("STATE", "MSA", "EMPSIZE")
    }

    treatment_rows: list[APCRTreatmentObservation] = []
    for period_id in BASELINE_PERIOD_IDS:
        source_key = f"period{period_id}_all"
        _, rows, _ = _json_rows(records[source_key].raw)
        for row in _btos_naics2_treatment_candidates(rows):
            if any(row.get(name) not in (None, "", "None") for name in ("STATE", "MSA", "EMPSIZE")):
                continue
            treatment_rows.append(
                APCRTreatmentObservation(
                    entity_id=str(row["NAICS2"]),
                    period_id=period_id,
                    ai_use_share=float(row["ESTIMATE_PERCENTAGE"]) / 100.0,
                    standard_error_share=(
                        float(row["STANDARD_ERROR"]) / 100.0
                        if row.get("STANDARD_ERROR") not in (None, "")
                        else None
                    ),
                    strata_scope="national_naics2_total",
                    source_vintage_id=records[source_key].sha256,
                )
            )

    required_periods = set(BASELINE_PERIOD_IDS)
    periods_by_entity: dict[str, set[int]] = {}
    for row in treatment_rows:
        periods_by_entity.setdefault(row.entity_id, set()).add(row.period_id)

    complete_entities = sorted(
        entity
        for entity, periods in periods_by_entity.items()
        if periods == required_periods
    )
    incomplete_entities = {
        entity: sorted(required_periods - periods)
        for entity, periods in sorted(periods_by_entity.items())
        if periods != required_periods
    }
    complete_rows = [
        row for row in treatment_rows if row.entity_id in set(complete_entities)
    ]

    frozen_treatment = []
    treatment_error = None
    try:
        frozen_treatment = [
            {
                "entity_id": row.entity_id,
                "baseline_ai_intensity": row.baseline_ai_intensity,
                "period_ids": list(row.period_ids),
                "source_vintage_ids": list(row.source_vintage_ids),
                "aggregation": row.aggregation,
            }
            for row in freeze_apcr_baseline_treatment(complete_rows)
        ]
    except ValueError as exc:
        treatment_error = str(exc)

    return {
        "periods": {
            "payload_type": periods_type,
            "row_count": len(period_rows),
            "row_keys": period_keys,
            "sample_rows": [_safe_candidate(row) for row in period_rows[:3]],
            "baseline_periods_31_36": [
                _safe_candidate(row) for row in baseline_periods
            ],
        },
        "questions": {
            "payload_type": questions_type,
            "row_count": len(question_rows),
            "row_keys": question_keys,
            "ai_question_candidates": [
                _safe_candidate(row) for row in ai_current
            ],
        },
        "answers": {
            "payload_type": answers_type,
            "row_count": len(answer_rows),
            "row_keys": answer_keys,
            "ai_yes_candidates": [
                _safe_candidate(row) for row in yes_ai_answers
            ],
        },
        "strata": {
            "payload_type": strata_type,
            "row_count": len(strata_rows),
            "row_keys": strata_keys,
            "sector_naics_candidates": [
                _safe_candidate(row) for row in strata_candidates[:100]
            ],
        },
        "baseline_data": baseline_data,
        "sector_data": sector_summaries,
        "baseline_candidate_diagnostics": {
            "total_naics2_candidate_rows": len(combined_candidates),
            "national_naics2_total_rows": len(treatment_rows),
            "complete_entities": complete_entities,
            "incomplete_entities_missing_periods": incomplete_entities,
            "naics2_values": sorted(
                {str(row["NAICS2"]) for row in combined_candidates}
            ),
            "observed_extra_dimensions": strata_dimensions,
            "frozen_treatment_candidate": frozen_treatment,
            "freeze_error": treatment_error,
            "authoritative_treatment_frozen": False,
        },
    }


def _tsv_rows(raw: bytes) -> list[dict[str, str]]:
    text = raw.decode("utf-8-sig")
    return [
        {str(key).strip(): (value or "").strip() for key, value in row.items()}
        for row in csv.DictReader(io.StringIO(text), delimiter="\t")
    ]


def _is_sector_naics(value: str) -> bool:
    return bool(
        re.fullmatch(r"\d{2}", value)
        or re.fullmatch(r"\d{2}-\d{2}", value)
    )


def summarize_bls(records: dict[str, FetchRecord]) -> dict[str, Any]:
    industries = _tsv_rows(records["industry"].raw)
    measures = _tsv_rows(records["measure"].raw)
    series = _tsv_rows(records["series"].raw)
    current = _tsv_rows(records["current"].raw)

    labor_measures = [
        row
        for row in measures
        if "labor productivity" in row.get("measure_text", "").lower()
    ]
    labor_codes = {row["measure_code"] for row in labor_measures}
    sector_industries = [
        row
        for row in industries
        if _is_sector_naics(row.get("naics_code", ""))
        and row.get("selectable", "") == "T"
    ]
    industry_by_code = {
        row["industry_code"]: row for row in sector_industries
    }

    candidate_series = []
    candidate_ids: set[str] = set()
    for row in series:
        if row.get("measure_code") not in labor_codes:
            continue
        if row.get("industry_code") not in industry_by_code:
            continue
        if row.get("area_code") != "000000":
            continue
        if row.get("duration_code") != "0":
            continue
        industry = industry_by_code[row["industry_code"]]
        candidate_ids.add(row["series_id"])
        candidate_series.append(
            {
                "series_id": row["series_id"],
                "naics_code": industry["naics_code"],
                "industry_text": industry.get("industry_text", ""),
                "measure_code": row["measure_code"],
                "series_title": row.get("series_title", ""),
                "begin_year": row.get("begin_year", ""),
                "end_year": row.get("end_year", ""),
            }
        )

    latest_by_series: dict[str, dict[str, str]] = {}
    for row in current:
        series_id = row.get("series_id", "")
        if series_id not in candidate_ids:
            continue
        previous = latest_by_series.get(series_id)
        marker = (row.get("year", ""), row.get("period", ""))
        if previous is None or marker > (
            previous.get("year", ""),
            previous.get("period", ""),
        ):
            latest_by_series[series_id] = row

    return {
        "industry_columns": sorted(
            {key for row in industries for key in row}
        ),
        "measure_columns": sorted({key for row in measures for key in row}),
        "series_columns": sorted({key for row in series for key in row}),
        "current_data_columns": sorted(
            {key for row in current[:100] for key in row}
        ),
        "labor_productivity_measure_candidates": labor_measures,
        "selectable_sector_industries": sector_industries,
        "labor_productivity_sector_series": candidate_series,
        "latest_candidate_observations": {
            key: latest_by_series[key] for key in sorted(latest_by_series)
        },
    }


def run_probe(
    *,
    retrieved_at: datetime,
    fetcher: FetchBytes = fetch_bytes,
    json_poster: PostJsonBytes = post_json_bytes,
) -> dict[str, Any]:
    if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
        raise ValueError("retrieved_at must be timezone-aware")

    urls = {
        "periods": ("census_btos_periods", BTOS_PERIODS_URL),
        "questions": ("census_btos_questions", BTOS_QUESTIONS_URL),
        "answers": ("census_btos_question_answers", BTOS_ANSWERS_URL),
        "strata": ("census_btos_strata", BTOS_STRATA_URL),
        "period31_all": (
            "census_btos_period31_all",
            f"{CENSUS_BASE}/periods/31/data",
        ),
        "period32_all": (
            "census_btos_period32_all",
            f"{CENSUS_BASE}/periods/32/data",
        ),
        "period33_all": (
            "census_btos_period33_all",
            f"{CENSUS_BASE}/periods/33/data",
        ),
        "period34_all": (
            "census_btos_period34_all",
            f"{CENSUS_BASE}/periods/34/data",
        ),
        "period35_all": (
            "census_btos_period35_all",
            f"{CENSUS_BASE}/periods/35/data",
        ),
        "period36_all": (
            "census_btos_period36_all",
            f"{CENSUS_BASE}/periods/36/data",
        ),
        "sector_old": (
            "census_btos_sector_old",
            f"{CENSUS_BASE}/periods/{OLD_WORDING_PROBE_PERIOD}/data/sector/{PROBE_SECTOR}",
        ),
        "sector_new": (
            "census_btos_sector_new",
            f"{CENSUS_BASE}/periods/{NEW_WORDING_PROBE_PERIOD}/data/sector/{PROBE_SECTOR}",
        ),
        "major_2021": (
            "bls_major_industry_productivity_2021",
            BLS_MAJOR_RELEASES[2021][1],
        ),
        "major_2022": (
            "bls_major_industry_productivity_2022",
            BLS_MAJOR_RELEASES[2022][1],
        ),
        "major_2023": (
            "bls_major_industry_productivity_2023",
            BLS_MAJOR_RELEASES[2023][1],
        ),
        "major_2024": (
            "bls_major_industry_productivity_2024",
            BLS_MAJOR_RELEASES[2024][1],
        ),
        "industry": ("bls_ip_industry", BLS_IP_INDUSTRY_URL),
        "measure": ("bls_ip_measure", BLS_IP_MEASURE_URL),
        "series": ("bls_ip_series", BLS_IP_SERIES_URL),
        "current": ("bls_ip_current", BLS_IP_CURRENT_URL),
    }
    records: dict[str, FetchRecord] = {}
    failures: dict[str, dict[str, str]] = {}
    for key, (source_id, url) in urls.items():
        print(f"apcr-probe fetching source={key} url={url}", flush=True)
        try:
            raw = fetcher(url)
        except (OSError, ValueError, TypeError) as exc:
            failures[key] = {
                "source_id": source_id,
                "url": url,
                "error_type": type(exc).__name__,
                "message": str(exc),
            }
            print(
                f"apcr-probe source-failure source={key} "
                f"type={type(exc).__name__} message={exc}",
                flush=True,
            )
            continue
        records[key] = FetchRecord(source_id, url, raw)

    btos_required = {
        "periods",
        "questions",
        "answers",
        "strata",
        "sector_old",
        "sector_new",
        *{f"period{period_id}_all" for period_id in BASELINE_PERIOD_IDS},
    }
    bls_required = {"industry", "measure", "series", "current"}
    btos = (
        summarize_btos(records)
        if btos_required <= set(records)
        else {
            "status": "PARTIAL",
            "available_sources": sorted(set(records) & btos_required),
            "missing_sources": sorted(btos_required - set(records)),
        }
    )
    bls = (
        summarize_bls(records)
        if bls_required <= set(records)
        else {
            "status": "PARTIAL",
            "available_sources": sorted(set(records) & bls_required),
            "missing_sources": sorted(bls_required - set(records)),
        }
    )

    frozen_entities = [
        str(row["entity_id"])
        for row in btos.get("baseline_candidate_diagnostics", {}).get(
            "frozen_treatment_candidate", []
        )
        if str(row["entity_id"]) in BLS_MAJOR_LP_INDEX_SERIES
    ]
    requested_by_naics = {
        entity: bls_labor_productivity_series_id(entity)
        for entity in frozen_entities
    }
    bls_api: dict[str, Any]
    if requested_by_naics:
        try:
            raw = json_poster(
                BLS_API_URL,
                {
                    "seriesid": list(requested_by_naics.values()),
                    "startyear": "2021",
                    "endyear": "2024",
                },
            )
        except (OSError, ValueError, TypeError) as exc:
            bls_api = {
                "status": "SOURCE_FAILURE",
                "error_type": type(exc).__name__,
                "message": str(exc),
                "requested_series": requested_by_naics,
                "valid_series": {},
                "missing_series": sorted(requested_by_naics),
                "annual_observations": {},
            }
        else:
            bls_api = summarize_bls_api(
                raw,
                requested_by_naics=requested_by_naics,
            )
            records["bls_api_outcome"] = FetchRecord(
                "bls_major_industry_productivity_current_snapshot",
                BLS_API_URL,
                raw,
            )
    else:
        bls_api = {
            "status": "NO_TREATMENT_ENTITIES",
            "requested_series": {},
            "valid_series": {},
            "missing_series": [],
            "annual_observations": {},
        }

    major_outcomes: dict[str, Any] = {
        "status": "COMPLETE",
        "source_family": "bls_major_industry_productivity_release",
        "observations": [],
        "missing_release_years": [],
    }
    for outcome_year, (release_date, _url) in BLS_MAJOR_RELEASES.items():
        key = f"major_{outcome_year}"
        record = records.get(key)
        if record is None:
            major_outcomes["status"] = "PARTIAL"
            major_outcomes["missing_release_years"].append(outcome_year)
            continue
        try:
            observations = parse_major_industry_labor_productivity(
                record.raw,
                outcome_year=outcome_year,
                source_release_date=release_date,
                source_vintage_id=record.sha256,
            )
        except ValueError as exc:
            major_outcomes["status"] = "PARTIAL"
            major_outcomes.setdefault("parse_errors", {})[str(outcome_year)] = str(exc)
            continue
        major_outcomes["observations"].extend(
            {
                "entity_id": row.entity_id,
                "outcome_year": row.outcome_year,
                "labor_productivity_change": row.labor_productivity_change,
                "source_release_date": row.source_release_date,
                "source_vintage_id": row.source_vintage_id,
                "bls_naics_code": row.bls_naics_code,
            }
            for row in observations
        )

    frozen_entity_set = set(frozen_entities)
    coverage_by_entity = {
        entity: sorted(
            row["outcome_year"]
            for row in major_outcomes["observations"]
            if row["entity_id"] == entity
        )
        for entity in sorted(frozen_entity_set)
    }
    major_outcomes["coverage_by_entity"] = coverage_by_entity
    major_outcomes["complete_panel_entities"] = [
        entity
        for entity, years in coverage_by_entity.items()
        if years == [2021, 2022, 2023, 2024]
    ]
    major_outcomes["missing_panel_entities"] = {
        entity: sorted({2021, 2022, 2023, 2024} - set(years))
        for entity, years in coverage_by_entity.items()
        if years != [2021, 2022, 2023, 2024]
    }

    return {
        "schema_version": 2,
        "retrieved_at": retrieved_at.isoformat(),
        "authoritative_state_input": False,
        "A_coverage_increment": 0.0,
        "btos": btos,
        "bls": bls,
        "bls_api_outcome_probe": {
            **bls_api,
            "database": "BLS Major Industry Productivity",
            "representation": "labor_productivity_index_2017_100",
            "vintage_semantics": "current_revised_snapshot_only",
            "authoritative_backtest_vintage": False,
        },
        "bls_major_outcome_probe": major_outcomes,
        "failures": failures,
        "sources": {
            key: {
                "source_id": record.source_id,
                "url": record.url,
                "sha256": record.sha256,
                "bytes": len(record.raw),
            }
            for key, record in records.items()
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe APCR public source schemas")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    payload = run_probe(retrieved_at=datetime.now(UTC))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    btos_status = "COMPLETE" if "questions" in payload["btos"] else "PARTIAL"
    bls_status = (
        "COMPLETE"
        if "labor_productivity_sector_series" in payload["bls"]
        else "PARTIAL"
    )
    print(
        "apcr-probe "
        f"btos={btos_status} "
        f"bls={bls_status} "
        f"failures={len(payload['failures'])}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
