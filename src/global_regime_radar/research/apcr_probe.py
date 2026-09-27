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

from global_regime_radar.live.http import FetchBytes, fetch_bytes
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

OLD_WORDING_PROBE_PERIOD = 84
NEW_WORDING_PROBE_PERIOD = 88
PROBE_SECTOR = "51"
BASELINE_PERIOD_IDS = (31, 32, 33, 34, 35, 36)


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
            for row in freeze_apcr_baseline_treatment(treatment_rows)
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

    return {
        "schema_version": 2,
        "retrieved_at": retrieved_at.isoformat(),
        "authoritative_state_input": False,
        "A_coverage_increment": 0.0,
        "btos": btos,
        "bls": bls,
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
