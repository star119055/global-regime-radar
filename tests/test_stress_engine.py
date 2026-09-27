from datetime import UTC, datetime, timedelta

import pytest

from global_regime_radar.stress.engine import (
    StressConfig,
    StressEngine,
    StressInputs,
    StressLevel,
    classify_stress,
)

START = datetime(2020, 3, 1, 8, 30, tzinfo=UTC)


def at(day: int) -> datetime:
    return START + timedelta(days=day)


def normal() -> StressInputs:
    return StressInputs(funding=0.2, price_discovery=0.2, intermediation=0.2)


def l2_pressure() -> StressInputs:
    return StressInputs(funding=0.55, price_discovery=0.3, intermediation=0.3)


def l3_impairment() -> StressInputs:
    return StressInputs(funding=0.8, price_discovery=0.75, intermediation=0.4)


def l4_intervention() -> StressInputs:
    return StressInputs(
        funding=0.85,
        price_discovery=0.8,
        intermediation=0.75,
        controller_intervention=True,
        forced_deleveraging=True,
    )


def test_raw_level_boundaries():
    assert classify_stress(normal()) == StressLevel.L1
    assert classify_stress(l2_pressure()) == StressLevel.L2
    assert classify_stress(l3_impairment()) == StressLevel.L3
    assert classify_stress(l4_intervention()) == StressLevel.L4


def test_l4_requires_both_intervention_and_forced_deleveraging():
    controller_only = StressInputs(
        funding=0.9,
        price_discovery=0.8,
        intermediation=0.8,
        controller_intervention=True,
        forced_deleveraging=False,
    )
    deleveraging_only = StressInputs(
        funding=0.9,
        price_discovery=0.8,
        intermediation=0.8,
        controller_intervention=False,
        forced_deleveraging=True,
    )

    assert classify_stress(controller_only) == StressLevel.L3
    assert classify_stress(deleveraging_only) == StressLevel.L3


def test_single_day_spike_does_not_upgrade_confirmed_state():
    engine = StressEngine()
    assessment = engine.update(at(0), l3_impairment())

    assert assessment.raw_level == StressLevel.L3
    assert assessment.confirmed_level == StressLevel.L1
    assert assessment.candidate_level == StressLevel.L3
    assert assessment.confirmation_count == 1


def test_upgrade_confirms_after_two_consecutive_daily_observations():
    engine = StressEngine()
    engine.update(at(0), l2_pressure())
    result = engine.update(at(1), l2_pressure())

    assert result.confirmed_level == StressLevel.L2
    assert result.candidate_level is None
    assert len(engine.transitions) == 1
    assert engine.transitions[0].from_level == StressLevel.L1
    assert engine.transitions[0].to_level == StressLevel.L2


def test_candidate_change_resets_upgrade_counter():
    engine = StressEngine()
    engine.update(at(0), l2_pressure())
    result = engine.update(at(1), l3_impairment())

    assert result.confirmed_level == StressLevel.L1
    assert result.candidate_level == StressLevel.L3
    assert result.confirmation_count == 1


def test_two_day_severe_episode_can_jump_directly_to_l3():
    engine = StressEngine()
    engine.update(at(0), l3_impairment())
    result = engine.update(at(1), l3_impairment())

    assert result.confirmed_level == StressLevel.L3


def test_single_day_recovery_does_not_downgrade():
    engine = StressEngine()
    engine.update(at(0), l3_impairment())
    engine.update(at(1), l3_impairment())

    result = engine.update(at(2), l2_pressure())

    assert result.raw_level == StressLevel.L2
    assert result.confirmed_level == StressLevel.L3
    assert result.confirmation_count == 1


def test_downgrade_requires_five_consecutive_observations():
    engine = StressEngine()
    engine.update(at(0), l3_impairment())
    engine.update(at(1), l3_impairment())

    for day in range(2, 6):
        result = engine.update(at(day), l2_pressure())
        assert result.confirmed_level == StressLevel.L3

    result = engine.update(at(6), l2_pressure())
    assert result.confirmed_level == StressLevel.L2
    assert engine.transitions[-1].confirmation_count == 5


def test_l4_transition_and_exit_are_hysteretic():
    engine = StressEngine()
    engine.update(at(0), l4_intervention())
    entered = engine.update(at(1), l4_intervention())

    assert entered.confirmed_level == StressLevel.L4

    for day in range(2, 6):
        result = engine.update(at(day), l3_impairment())
        assert result.confirmed_level == StressLevel.L4

    exited = engine.update(at(6), l3_impairment())
    assert exited.confirmed_level == StressLevel.L3


def test_custom_confirmation_windows_are_independent():
    config = StressConfig(
        upgrade_confirmation_days=1,
        downgrade_confirmation_days=3,
    )
    engine = StressEngine(config=config)

    assert engine.update(at(0), l2_pressure()).confirmed_level == StressLevel.L2
    assert engine.update(at(1), normal()).confirmed_level == StressLevel.L2
    assert engine.update(at(2), normal()).confirmed_level == StressLevel.L2
    assert engine.update(at(3), normal()).confirmed_level == StressLevel.L1


def test_out_of_range_substate_is_rejected():
    with pytest.raises(ValueError, match=r"funding must be in \[0, 1\]"):
        StressInputs(funding=1.1, price_discovery=0.2, intermediation=0.2)


def test_updates_must_be_strictly_chronological():
    engine = StressEngine()
    engine.update(at(0), normal())

    with pytest.raises(ValueError, match="increase strictly"):
        engine.update(at(0), normal())


def test_threshold_configuration_is_validated():
    with pytest.raises(
        ValueError,
        match="pressure_threshold must be <= impairment_threshold",
    ):
        StressConfig(pressure_threshold=0.8, impairment_threshold=0.7)
