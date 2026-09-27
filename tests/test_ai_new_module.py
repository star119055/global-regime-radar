from datetime import UTC, datetime

import pytest

from global_regime_radar.backtest.compare import compare_module_metrics
from global_regime_radar.modules.ai_cycle import (
    APCRObservation,
    estimate_apcr_did,
    geoi_score,
    gpu_collateral_bridge,
    pccb_score,
)
from global_regime_radar.modules.availability import (
    ModuleFeatureGate,
    require_feature_availability,
)


def dt(year: int, month: int = 1, day: int = 1) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


def test_apcr_recovers_continuous_treatment_interaction():
    observations: list[APCRObservation] = []
    entity_effect = {"low": 0.0, "high": 1.0}
    periods = [
        ("2023Q2", False, 0.0),
        ("2023Q3", False, 0.5),
        ("2023Q4", True, 1.0),
        ("2024Q1", True, 1.5),
    ]
    intensities = {"low": 0.2, "high": 0.8}
    true_beta = 2.5

    for entity, intensity in intensities.items():
        for period, post, time_effect in periods:
            productivity = (
                10.0
                + entity_effect[entity]
                + time_effect
                + true_beta * intensity * float(post)
            )
            observations.append(
                APCRObservation(
                    entity_id=entity,
                    period=period,
                    productivity=productivity,
                    ai_intensity=intensity,
                    post=post,
                )
            )

    result = estimate_apcr_did(observations)

    assert result.interaction_coefficient == pytest.approx(true_beta)
    assert result.n_entities == 2
    assert result.n_periods == 4
    assert result.r_squared == pytest.approx(1.0)


def test_apcr_rejects_rank_deficient_design():
    observations = [
        APCRObservation("a", "p1", 1.0, 0.5, False),
        APCRObservation("b", "p1", 2.0, 0.5, False),
        APCRObservation("a", "p2", 1.5, 0.5, True),
        APCRObservation("b", "p2", 2.5, 0.5, True),
    ]
    with pytest.raises(ValueError, match="rank deficient"):
        estimate_apcr_did(observations)


def test_geoi_frozen_weights_and_signs():
    score = geoi_score(
        performance_per_dollar_change_z=2.0,
        old_gpu_rental_yield_change_z=-1.0,
        secondary_gpu_price_change_z=-2.0,
    )
    assert score == pytest.approx(1.65)


def test_geoi_does_not_reweight_missing_components():
    assert (
        geoi_score(
            performance_per_dollar_change_z=1.0,
            old_gpu_rental_yield_change_z=None,
            secondary_gpu_price_change_z=-1.0,
        )
        is None
    )


def test_pccb_frozen_weights():
    assert pccb_score(
        non_accrual_z=1.0,
        pik_z=2.0,
        nav_markdown_z=3.0,
        gates_z=4.0,
    ) == pytest.approx(2.2)


def test_pccb_missing_component_is_missing():
    assert (
        pccb_score(
            non_accrual_z=1.0,
            pik_z=2.0,
            nav_markdown_z=None,
            gates_z=4.0,
        )
        is None
    )


def test_gpu_collateral_loss_translates_to_higher_ltv():
    bridge = gpu_collateral_bridge(
        initial_ltv=0.50,
        collateral_price_change=-0.50,
    )
    assert bridge.stressed_ltv == pytest.approx(1.0)
    assert bridge.ltv_change == pytest.approx(0.50)


def test_gpu_collateral_bridge_rejects_total_value_destruction():
    with pytest.raises(ValueError, match="greater than -1"):
        gpu_collateral_bridge(initial_ltv=0.5, collateral_price_change=-1.0)


def test_new_module_feature_gate_blocks_core_history():
    gate = ModuleFeatureGate(
        feature_id="geoi",
        earliest_valid_at=dt(2024),
        allowed_universes=frozenset({"new_module"}),
    )
    gates = {"geoi": gate}

    with pytest.raises(ValueError, match="feature not valid"):
        require_feature_availability({"geoi"}, gates, "core_3", dt(2024))

    with pytest.raises(ValueError, match="feature not valid"):
        require_feature_availability({"geoi"}, gates, "new_module", dt(2023))

    require_feature_availability({"geoi"}, gates, "new_module", dt(2024))


def test_module_comparison_requires_matched_metric_keys():
    with pytest.raises(ValueError, match="same metric keys"):
        compare_module_metrics(
            core_run_id="core",
            augmented_run_id="ai",
            core_metrics={"recall": 0.5},
            augmented_metrics={"lead": 10.0},
        )


def test_module_comparison_reports_deltas_without_ranking():
    comparison = compare_module_metrics(
        core_run_id="core",
        augmented_run_id="ai",
        core_metrics={"false_alarms": 3.0, "recall": 0.50},
        augmented_metrics={"false_alarms": 2.0, "recall": 0.60},
    )

    by_metric = {item.metric: item for item in comparison.deltas}
    assert by_metric["recall"].delta == pytest.approx(0.10)
    assert by_metric["false_alarms"].delta == pytest.approx(-1.0)



def test_legacy_apcr_facade_rejects_time_varying_treatment_intensity():
    observations = [
        APCRObservation("a", "2022", 1.0, 0.2, False),
        APCRObservation("b", "2022", 2.0, 0.6, False),
        APCRObservation("a", "2024", 2.0, 0.4, True),
        APCRObservation("b", "2024", 4.0, 0.6, True),
    ]
    with pytest.raises(ValueError, match="frozen baseline AI intensity"):
        estimate_apcr_did(observations)
