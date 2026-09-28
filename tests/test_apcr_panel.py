from datetime import UTC, datetime

import pytest

from global_regime_radar.modules.apcr import (
    APCRFrozenTreatment,
    APCRPanelContract,
    APCRPanelObservation,
    APCRTreatmentObservation,
    apcr_ready_for_state_activation,
    estimate_apcr_baseline_did,
    freeze_apcr_baseline_treatment,
    validate_apcr_panel,
)


def contract() -> APCRPanelContract:
    return APCRPanelContract(
        contract_version="apcr-panel-v1",
        treatment_source="census_btos_ai",
        outcome_source="bls_detailed_industry_productivity",
        entity_level="naics2",
        treatment_measure="current_ai_use_share",
        treatment_measurement_regime="producing_goods_or_services",
        treatment_baseline_start=datetime(2023, 9, 11, tzinfo=UTC),
        treatment_baseline_end=datetime(2023, 12, 3, 23, 59, 59, tzinfo=UTC),
        post_start_year=2024,
        minimum_entities=4,
        minimum_pre_periods=2,
        minimum_post_periods=1,
    )


def panel(beta: float = 3.0) -> list[APCRPanelObservation]:
    intensities = {"51": 0.30, "52": 0.22, "54": 0.18, "44": 0.08}
    entity_effect = {"51": 1.2, "52": 0.8, "54": 0.4, "44": 0.0}
    period_effect = {2021: 0.0, 2022: 0.4, 2024: 1.0, 2025: 1.3}
    rows = []
    for entity, intensity in intensities.items():
        for year in (2021, 2022, 2024, 2025):
            post = year >= 2024
            productivity = (
                100.0
                + entity_effect[entity]
                + period_effect[year]
                + beta * intensity * float(post)
            )
            rows.append(
                APCRPanelObservation(
                    entity_id=entity,
                    year=year,
                    productivity=productivity,
                    baseline_ai_intensity=intensity,
                    post=post,
                    treatment_measurement_regime="producing_goods_or_services",
                    treatment_vintage_id="btos-baseline-v1",
                    productivity_vintage_id=f"bls-{year}-v1",
                )
            )
    return rows


def test_apcr_baseline_treatment_did_recovers_interaction():
    result = estimate_apcr_baseline_did(panel(beta=3.0), contract())
    assert result.interaction_coefficient == pytest.approx(3.0)
    assert result.n_entities == 4
    assert result.n_periods == 4
    assert result.treatment_intensity_min == pytest.approx(0.08)
    assert result.treatment_intensity_max == pytest.approx(0.30)


def test_apcr_rejects_time_varying_treatment_intensity():
    rows = panel()
    row = rows[-1]
    rows[-1] = APCRPanelObservation(
        entity_id=row.entity_id,
        year=row.year,
        productivity=row.productivity,
        baseline_ai_intensity=row.baseline_ai_intensity + 0.05,
        post=row.post,
        treatment_measurement_regime=row.treatment_measurement_regime,
        treatment_vintage_id=row.treatment_vintage_id,
        productivity_vintage_id=row.productivity_vintage_id,
    )
    with pytest.raises(ValueError, match="must be frozen"):
        validate_apcr_panel(rows, contract())


def test_apcr_rejects_post_2025_wording_regime_in_baseline_contract():
    rows = panel()
    row = rows[0]
    rows[0] = APCRPanelObservation(
        entity_id=row.entity_id,
        year=row.year,
        productivity=row.productivity,
        baseline_ai_intensity=row.baseline_ai_intensity,
        post=row.post,
        treatment_measurement_regime="any_business_function",
        treatment_vintage_id=row.treatment_vintage_id,
        productivity_vintage_id=row.productivity_vintage_id,
    )
    with pytest.raises(ValueError, match="measurement regime"):
        validate_apcr_panel(rows, contract())


def test_apcr_rejects_missing_pre_or_post_entity():
    rows = [
        row
        for row in panel()
        if not (row.entity_id == "51" and row.post)
    ]
    with pytest.raises(ValueError, match="pre and post"):
        validate_apcr_panel(rows, contract())


def test_apcr_rejects_insufficient_entity_overlap():
    rows = [row for row in panel() if row.entity_id in {"51", "52", "54"}]
    with pytest.raises(ValueError, match="at least 4 aligned entities"):
        validate_apcr_panel(rows, contract())


def test_apcr_activation_requires_all_promotion_gates():
    assert not apcr_ready_for_state_activation(
        panel_valid=True,
        beta_normalization_frozen=False,
        point_in_time_vintages_complete=True,
        prospective_validation_passed=True,
    )
    assert not apcr_ready_for_state_activation(
        panel_valid=True,
        beta_normalization_frozen=True,
        point_in_time_vintages_complete=True,
        prospective_validation_passed=True,
    )
    assert apcr_ready_for_state_activation(
        panel_valid=True,
        beta_normalization_frozen=True,
        point_in_time_vintages_complete=True,
        prospective_validation_passed=True,
        full_rank_design=True,
        post_period_count=2,
        treatment_regime_clean=True,
        pretrend_confounding_resolved=True,
    )



def treatment_rows() -> list[APCRTreatmentObservation]:
    values = {
        "44": [0.020, 0.021, 0.022, 0.023, 0.024, 0.025],
        "51": [0.090, 0.100, 0.110, 0.120, 0.130, 0.140],
        "52": [0.050, 0.052, 0.054, 0.056, 0.058, 0.060],
        "54": [0.080, 0.082, 0.084, 0.086, 0.088, 0.090],
    }
    rows = []
    for entity, shares in values.items():
        for period_id, share in zip((31, 32, 33, 34, 35, 36), shares, strict=True):
            rows.append(
                APCRTreatmentObservation(
                    entity_id=entity,
                    period_id=period_id,
                    ai_use_share=share,
                    standard_error_share=0.01,
                    strata_scope="national_naics2_total",
                    source_vintage_id=f"btos-{period_id}",
                )
            )
    return rows


def test_freeze_apcr_treatment_uses_simple_mean_and_all_six_periods():
    frozen = freeze_apcr_baseline_treatment(treatment_rows())
    by_entity = {row.entity_id: row for row in frozen}
    assert isinstance(by_entity["51"], APCRFrozenTreatment)
    assert by_entity["51"].baseline_ai_intensity == pytest.approx(0.115)
    assert by_entity["51"].period_ids == (31, 32, 33, 34, 35, 36)
    assert by_entity["51"].aggregation == "simple_mean"


def test_freeze_apcr_treatment_rejects_size_or_geo_substrata():
    with pytest.raises(ValueError, match="national_naics2_total"):
        APCRTreatmentObservation(
            entity_id="51",
            period_id=31,
            ai_use_share=0.10,
            strata_scope="employee_size_B",
            source_vintage_id="btos-31",
        )


def test_freeze_apcr_treatment_rejects_incomplete_entity_periods():
    rows = [
        row
        for row in treatment_rows()
        if not (row.entity_id == "51" and row.period_id == 36)
    ]
    with pytest.raises(ValueError, match="missing baseline periods"):
        freeze_apcr_baseline_treatment(rows)
