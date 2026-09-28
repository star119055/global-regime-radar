from copy import deepcopy

from global_regime_radar.research.apcr_promotion import (
    APCRPromotionGate,
    evaluate_apcr_promotion,
)


def _candidate():
    return {
        "main": {"interaction_coefficient": 111.0},
        "pre_period_placebo": {"absolute_beta_ratio_to_main": 0.78},
        "sector_pretrend_diagnostics": {
            "baseline_ai_intensity_vs_pretrend_slope_correlation": 0.73,
            "trend_adjusted_twfe": {"interaction_coefficient": 6.4},
            "trend_adjusted_to_raw_absolute_beta_ratio": 0.058,
        },
    }


def _passing_gate():
    return APCRPromotionGate(
        panel_valid=True,
        full_rank_design=True,
        post_period_count=2,
        minimum_post_periods_for_promotion=2,
        point_in_time_vintages_complete=True,
        treatment_regime_clean=True,
        pretrend_confounding_resolved=True,
        beta_normalization_frozen=True,
        prospective_validation_passed=True,
    )


def test_apcr_promotion_is_fail_closed_for_each_gate():
    fields = [
        "panel_valid",
        "full_rank_design",
        "point_in_time_vintages_complete",
        "treatment_regime_clean",
        "pretrend_confounding_resolved",
        "beta_normalization_frozen",
        "prospective_validation_passed",
    ]
    for field in fields:
        values = _passing_gate().__dict__.copy()
        values[field] = False
        result = evaluate_apcr_promotion(
            _candidate(),
            gate=APCRPromotionGate(**values),
        )
        assert result["promotion_eligible"] is False
        assert result["A_coverage_increment"] == 0.0


def test_single_post_year_blocks_production_promotion():
    values = _passing_gate().__dict__.copy()
    values["post_period_count"] = 1
    result = evaluate_apcr_promotion(
        _candidate(),
        gate=APCRPromotionGate(**values),
    )
    assert "insufficient_post_periods_for_promotion" in result["blockers"]
    assert result["authoritative_state_input"] is False


def test_only_all_gates_pass_allows_state_mapping():
    result = evaluate_apcr_promotion(
        _candidate(),
        gate=_passing_gate(),
    )
    assert result["promotion_eligible"] is True
    assert result["A_coverage_increment"] == 1.0
    assert result["status"] == "ELIGIBLE_FOR_STATE_MAPPING"


def test_observed_diagnostics_do_not_create_ex_post_thresholds():
    candidate = deepcopy(_candidate())
    result = evaluate_apcr_promotion(
        candidate,
        gate=APCRPromotionGate(
            **{
                **_passing_gate().__dict__,
                "pretrend_confounding_resolved": False,
            }
        ),
    )
    assert result["observed_diagnostics"]["raw_beta"] == 111.0
    assert result["observed_diagnostics"]["trend_adjusted_beta"] == 6.4
    assert "No ex-post" in result["threshold_policy"]
    assert result["promotion_eligible"] is False
