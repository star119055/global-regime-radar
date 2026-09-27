from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from global_regime_radar.regime.baseline import IndicatorEvidence
from global_regime_radar.regime.dynamics import Coupling
from global_regime_radar.shadow.engine import (
    ShadowPendingData,
    ShadowStatus,
    canonical_config_hash,
    run_shadow,
)
from global_regime_radar.shadow.reporting import render_shadow_markdown

STATES = ("A", "B", "C1", "C2", "C3", "D")
HALF_LIVES = {
    "A": 120.0,
    "B": 7.0,
    "C1": 60.0,
    "C2": 90.0,
    "C3": 180.0,
    "D": 270.0,
}
DYNAMIC_Q = {state: 0.0001 for state in STATES}
UKF_Q = {state: 0.001 for state in STATES}


def dt(day: int) -> datetime:
    return datetime(2026, 9, day, 0, 30, tzinfo=UTC)


def evidence(value: float = 0.6):
    return {
        state: [
            IndicatorEvidence(
                key=f"{state}-signal",
                activation=value,
                weight=1.0,
                measurement_variance=0.02,
                attribution_group=f"{state}-group",
            )
        ]
        for state in STATES
    }


def run(day: int = 27):
    return run_shadow(
        decision_time=dt(day),
        generated_at=dt(day) + timedelta(minutes=2),
        dataset_hash="dataset-123",
        config_hash=canonical_config_hash({"version": "shadow-v1"}),
        feature_set_version="core-v1",
        evidence=evidence(),
        prior_dynamic=None,
        prior_ukf=None,
        prior_time=None,
        half_life_days=HALF_LIVES,
        dynamic_process_variance_per_day=DYNAMIC_Q,
        ukf_process_variance_per_day=UKF_Q,
        couplings=[Coupling("C3", "A", -0.1)],
        minimum_state_coverage=0.4,
    )


def test_completed_shadow_run_contains_three_engines_on_same_input():
    shadow, _, _ = run()
    assert shadow.status is ShadowStatus.COMPLETED
    assert {result.engine for result in shadow.results} == {
        "baseline0",
        "baseline1",
        "ukf",
    }
    assert shadow.dataset_hash == "dataset-123"
    assert len(shadow.disagreements) == 6


def test_run_id_does_not_depend_on_generation_time():
    first, _, _ = run()
    second, _, _ = run()
    assert first.run_id == second.run_id


def test_missing_state_coverage_returns_pending_data_not_neutral():
    partial = evidence()
    partial["D"] = [IndicatorEvidence(key="D-missing", activation=None, weight=1.0)]
    with pytest.raises(ShadowPendingData) as exc_info:
        run_shadow(
            decision_time=dt(27),
            generated_at=dt(27),
            dataset_hash="dataset",
            config_hash="config",
            feature_set_version="core-v1",
            evidence=partial,
            prior_dynamic=None,
            prior_ukf=None,
            prior_time=None,
            half_life_days=HALF_LIVES,
            dynamic_process_variance_per_day=DYNAMIC_Q,
            ukf_process_variance_per_day=UKF_Q,
            couplings=[],
            minimum_state_coverage=0.4,
        )
    pending = exc_info.value.run
    assert pending.status is ShadowStatus.PENDING_DATA
    assert any(item.startswith("D:coverage=") for item in pending.missing_requirements)
    assert pending.results == ()


def test_second_day_reuses_prior_dynamic_and_ukf_state():
    first, dynamic, ukf = run(27)
    second, _, _ = run_shadow(
        decision_time=dt(28),
        generated_at=dt(28),
        dataset_hash="dataset-124",
        config_hash=first.config_hash,
        feature_set_version="core-v1",
        evidence=evidence(0.8),
        prior_dynamic=dynamic,
        prior_ukf=ukf,
        prior_time=dt(27),
        half_life_days=HALF_LIVES,
        dynamic_process_variance_per_day=DYNAMIC_Q,
        ukf_process_variance_per_day=UKF_Q,
        couplings=[],
        minimum_state_coverage=0.4,
    )
    assert second.status is ShadowStatus.COMPLETED
    assert second.run_id != first.run_id


def test_markdown_surfaces_engine_disagreement():
    shadow, _, _ = run()
    rendered = render_shadow_markdown(shadow)
    assert "Baseline0" in rendered
    assert "Baseline1" in rendered
    assert "UKF" in rendered
    assert "Max spread" in rendered


def test_pending_markdown_keeps_diagnostic_engine_outputs():
    shadow, _, _ = run()
    pending = replace(
        shadow,
        status=ShadowStatus.PENDING_DATA,
        missing_requirements=("A:coverage=0.000<0.400",),
    )
    rendered = render_shadow_markdown(pending)
    assert "Diagnostic only" in rendered
    assert "A:coverage=0.000<0.400" in rendered
    assert "Baseline0" in rendered
    assert "UKF" in rendered


def test_config_hash_is_key_order_independent():
    assert canonical_config_hash({"a": 1, "b": 2}) == canonical_config_hash(
        {"b": 2, "a": 1}
    )
