from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

import numpy as np

from global_regime_radar.modules.apcr import (
    APCRPanelContract,
    APCRPanelObservation,
    estimate_apcr_baseline_did,
)

TREATMENT_REGIME = "producing_goods_or_services"


def _combined_vintage_id(values: list[str]) -> str:
    material = json.dumps(sorted(values), separators=(",", ":")).encode()
    return hashlib.sha256(material).hexdigest()


def _contract(
    *,
    post_start_year: int,
    minimum_entities: int = 4,
) -> APCRPanelContract:
    return APCRPanelContract(
        contract_version="apcr-panel-v1",
        treatment_source="census_btos_ai",
        outcome_source="bls_major_industry_productivity",
        entity_level="naics2_major_industry",
        treatment_measure="current_ai_use_share",
        treatment_measurement_regime=TREATMENT_REGIME,
        treatment_baseline_start=datetime(2023, 9, 11, tzinfo=UTC),
        treatment_baseline_end=datetime(2023, 12, 3, 23, 59, 59, tzinfo=UTC),
        post_start_year=post_start_year,
        minimum_entities=minimum_entities,
        minimum_pre_periods=2,
        minimum_post_periods=1,
    )


def build_current_snapshot_panel(
    *,
    frozen_treatment: list[dict[str, Any]],
    annual_observations: dict[str, list[dict[str, Any]]],
    productivity_vintage_id: str,
    years: tuple[int, ...] = (2021, 2022, 2023, 2024),
    post_start_year: int = 2024,
) -> list[APCRPanelObservation]:
    treatment_by_entity = {
        str(row["entity_id"]): row for row in frozen_treatment
    }
    observations: list[APCRPanelObservation] = []

    for entity_id in sorted(set(treatment_by_entity) & set(annual_observations)):
        treatment = treatment_by_entity[entity_id]
        treatment_vintage_id = _combined_vintage_id(
            [str(value) for value in treatment["source_vintage_ids"]]
        )
        outcome_by_year = {
            int(row["year"]): row
            for row in annual_observations[entity_id]
            if int(row["year"]) in years
        }
        if set(outcome_by_year) != set(years):
            continue

        for year in years:
            observations.append(
                APCRPanelObservation(
                    entity_id=entity_id,
                    year=year,
                    productivity=float(outcome_by_year[year]["value"]),
                    baseline_ai_intensity=float(
                        treatment["baseline_ai_intensity"]
                    ),
                    post=year >= post_start_year,
                    treatment_measurement_regime=TREATMENT_REGIME,
                    treatment_vintage_id=treatment_vintage_id,
                    productivity_vintage_id=productivity_vintage_id,
                )
            )
    return observations


def _entity_pretrend_diagnostics(
    panel: list[APCRPanelObservation],
) -> dict[str, Any]:
    entities = sorted({row.entity_id for row in panel})
    by_entity = {
        entity: sorted(
            [row for row in panel if row.entity_id == entity],
            key=lambda row: row.year,
        )
        for entity in entities
    }

    slopes: dict[str, float] = {}
    residual_2024: dict[str, float] = {}
    intensities: list[float] = []
    slope_values: list[float] = []

    for entity in entities:
        rows = by_entity[entity]
        pre = [row for row in rows if row.year in (2021, 2022, 2023)]
        post = [row for row in rows if row.year == 2024]
        if len(pre) != 3 or len(post) != 1:
            raise ValueError(
                f"APCR trend diagnostic requires 2021-2024 for entity {entity}"
            )

        x = np.asarray([row.year - 2021 for row in pre], dtype=float)
        y = np.asarray([row.productivity for row in pre], dtype=float)
        design = np.column_stack([np.ones(len(x)), x])
        coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
        intercept, slope = coefficients
        predicted_2024 = float(intercept + slope * 3.0)
        residual = float(post[0].productivity - predicted_2024)

        slopes[entity] = float(slope)
        residual_2024[entity] = residual
        intensities.append(float(post[0].baseline_ai_intensity))
        slope_values.append(float(slope))

    intensity_array = np.asarray(intensities, dtype=float)
    slope_array = np.asarray(slope_values, dtype=float)
    if np.std(intensity_array) <= 1e-12 or np.std(slope_array) <= 1e-12:
        correlation = None
    else:
        correlation = float(np.corrcoef(intensity_array, slope_array)[0, 1])

    residual_array = np.asarray(
        [residual_2024[entity] for entity in entities],
        dtype=float,
    )
    residual_design = np.column_stack(
        [np.ones(len(entities)), intensity_array]
    )
    residual_coefficients, *_ = np.linalg.lstsq(
        residual_design,
        residual_array,
        rcond=None,
    )
    residual_beta = float(residual_coefficients[1])

    return {
        "pretrend_slope_by_entity": slopes,
        "baseline_ai_intensity_vs_pretrend_slope_correlation": correlation,
        "residual_2024_by_entity": residual_2024,
        "residual_on_ai_intensity_beta": residual_beta,
    }


def _entity_trend_adjusted_twfe_beta(
    panel: list[APCRPanelObservation],
) -> dict[str, float | int]:
    entities = sorted({row.entity_id for row in panel})
    years = sorted({row.year for row in panel})
    entity_index = {entity: index for index, entity in enumerate(entities)}
    year_index = {year: index for index, year in enumerate(years)}

    design_rows: list[list[float]] = []
    outcomes: list[float] = []
    for row in panel:
        time_index = float(row.year - years[0])
        design = [
            1.0,
            row.baseline_ai_intensity * float(row.year >= 2024),
        ]
        design.extend(
            float(entity_index[row.entity_id] == index)
            for index in range(1, len(entities))
        )
        design.extend(
            float(year_index[row.year] == index)
            for index in range(1, len(years))
        )
        design.extend(
            float(entity_index[row.entity_id] == index) * time_index
            for index in range(1, len(entities))
        )
        design_rows.append(design)
        outcomes.append(row.productivity)

    matrix = np.asarray(design_rows, dtype=float)
    outcome = np.asarray(outcomes, dtype=float)
    rank = int(np.linalg.matrix_rank(matrix))
    if rank < matrix.shape[1]:
        raise ValueError(
            "APCR entity-trend-adjusted design matrix is rank deficient"
        )
    coefficients, *_ = np.linalg.lstsq(matrix, outcome, rcond=None)
    return {
        "interaction_coefficient": float(coefficients[1]),
        "rank": rank,
        "n_columns": int(matrix.shape[1]),
    }


def estimate_candidate(
    *,
    frozen_treatment: list[dict[str, Any]],
    annual_observations: dict[str, list[dict[str, Any]]],
    productivity_vintage_id: str,
) -> dict[str, Any]:
    panel = build_current_snapshot_panel(
        frozen_treatment=frozen_treatment,
        annual_observations=annual_observations,
        productivity_vintage_id=productivity_vintage_id,
    )
    entities = sorted({row.entity_id for row in panel})
    years = sorted({row.year for row in panel})
    expected_rows = len(entities) * len(years)

    if len(entities) < 4 or years != [2021, 2022, 2023, 2024]:
        return {
            "status": "INSUFFICIENT_PANEL",
            "authoritative_state_input": False,
            "A_coverage_increment": 0.0,
            "entities": entities,
            "years": years,
            "n_observations": len(panel),
            "promotion_blockers": [
                "insufficient_complete_current_snapshot_panel",
                "beta_normalization_not_frozen",
                "prospective_validation_not_passed",
            ],
        }
    if len(panel) != expected_rows:
        raise ValueError("APCR current-snapshot panel is not balanced")

    main = estimate_apcr_baseline_did(panel, _contract(post_start_year=2024))

    loso: dict[str, float] = {}
    for omitted in entities:
        subset = [row for row in panel if row.entity_id != omitted]
        loso[omitted] = estimate_apcr_baseline_did(
            subset,
            _contract(
                post_start_year=2024,
                minimum_entities=max(2, min(4, len(entities) - 1)),
            ),
        ).interaction_coefficient

    placebo_panel = [
        APCRPanelObservation(
            entity_id=row.entity_id,
            year=row.year,
            productivity=row.productivity,
            baseline_ai_intensity=row.baseline_ai_intensity,
            post=row.year >= 2023,
            treatment_measurement_regime=row.treatment_measurement_regime,
            treatment_vintage_id=row.treatment_vintage_id,
            productivity_vintage_id=row.productivity_vintage_id,
        )
        for row in panel
        if row.year <= 2023
    ]
    placebo = estimate_apcr_baseline_did(
        placebo_panel,
        _contract(post_start_year=2023),
    )

    denominator = abs(main.interaction_coefficient)
    placebo_ratio = (
        abs(placebo.interaction_coefficient) / denominator
        if denominator > 1e-12
        else None
    )

    trend = _entity_pretrend_diagnostics(panel)
    trend_twfe = _entity_trend_adjusted_twfe_beta(panel)
    trend_beta = float(trend_twfe["interaction_coefficient"])
    residual_beta = float(trend["residual_on_ai_intensity_beta"])
    trend_method_difference = abs(trend_beta - residual_beta)
    if trend_method_difference > 1e-8:
        raise ValueError(
            "APCR trend-adjusted estimators disagree beyond tolerance"
        )

    raw_beta = main.interaction_coefficient
    trend_ratio = (
        abs(trend_beta) / abs(raw_beta)
        if abs(raw_beta) > 1e-12
        else None
    )

    loso_values = list(loso.values())
    return {
        "status": "ESTIMATED_RESEARCH_ONLY",
        "authoritative_state_input": False,
        "A_coverage_increment": 0.0,
        "representation": "bls_major_industry_labor_productivity_index_2017_100",
        "vintage_semantics": "current_revised_snapshot_only",
        "entities": entities,
        "years": years,
        "n_observations": len(panel),
        "main": asdict(main),
        "main_beta_per_10pp_ai_share": main.interaction_coefficient * 0.10,
        "leave_one_sector_out_beta": loso,
        "leave_one_sector_out_range": {
            "minimum": min(loso_values),
            "maximum": max(loso_values),
        },
        "pre_period_placebo": {
            "pseudo_post_start_year": 2023,
            "years": [2021, 2022, 2023],
            "result": asdict(placebo),
            "absolute_beta_ratio_to_main": placebo_ratio,
        },
        "sector_pretrend_diagnostics": {
            **trend,
            "trend_adjusted_twfe": trend_twfe,
            "trend_adjusted_beta_per_10pp_ai_share": trend_beta * 0.10,
            "trend_adjusted_to_raw_absolute_beta_ratio": trend_ratio,
            "equivalent_method_absolute_difference": trend_method_difference,
        },
        "promotion_blockers": [
            "current_bls_history_is_revised_snapshot_not_historical_pit",
            "archived_release_automation_unavailable_in_github_runner",
            "pretrend_not_validated",
            "sector_specific_trend_confounding_not_resolved",
            "single_post_year_only",
            "beta_normalization_not_frozen",
            "prospective_validation_not_passed",
        ],
        "causal_claim_allowed": False,
    }
