import pytest

from global_regime_radar.regime.baseline import StateEstimate
from global_regime_radar.regime.dynamics import (
    Coupling,
    DynamicState,
    Jump,
    persistence_coefficient,
    transition_regime,
    transition_state,
)


def estimate(state: str, value: float, coverage: float, variance: float = 0.02):
    return StateEstimate(
        state=state,
        value=value,
        coverage=coverage,
        observed_composite=value if coverage > 0 else None,
        variance=variance,
        confidence="Medium",
        observed_weight=coverage,
        configured_weight=1.0,
    )


def test_half_life_definition():
    assert persistence_coefficient(10, 10) == pytest.approx(0.5)


def test_zero_coverage_does_not_pull_state_to_prior():
    previous = DynamicState("A", 0.8, 0.02)
    result = transition_state(
        previous,
        estimate("A", 0.5, 0.0),
        delta_days=30,
        half_life_days=120,
        source_states={},
        couplings=[],
        jumps=[],
        missing_variance_per_day=0.001,
    )
    assert result.value == pytest.approx(0.8)
    assert result.variance > previous.variance


def test_fast_state_responds_more_than_slow_state():
    fast = transition_state(
        DynamicState("B", 0.5, 0.01),
        estimate("B", 0.9, 1.0),
        delta_days=7,
        half_life_days=7,
        source_states={},
        couplings=[],
        jumps=[],
    )
    slow = transition_state(
        DynamicState("A", 0.5, 0.01),
        estimate("A", 0.9, 1.0),
        delta_days=7,
        half_life_days=120,
        source_states={},
        couplings=[],
        jumps=[],
    )
    assert fast.value > slow.value


def test_jump_is_not_smoothed_by_persistence():
    result = transition_state(
        DynamicState("D", 0.4, 0.01),
        estimate("D", 0.4, 1.0),
        delta_days=1,
        half_life_days=270,
        source_states={},
        couplings=[],
        jumps=[Jump("D", 0.2, "policy-event")],
    )
    assert result.value == pytest.approx(0.6)


def test_sparse_coupling_changes_target_only():
    previous = DynamicState("A", 0.5, 0.01)
    result = transition_state(
        previous,
        estimate("A", 0.5, 1.0),
        delta_days=30,
        half_life_days=120,
        source_states={"C3": 0.9},
        couplings=[Coupling("C3", "A", -0.2)],
        jumps=[],
    )
    assert result.value < 0.5


def test_transition_regime_is_deterministic_and_bounded():
    states = ("A", "B", "C1", "C2", "C3", "D")
    previous = {state: DynamicState(state, 0.5, 0.02) for state in states}
    evidence = {state: estimate(state, 0.7, 1.0) for state in states}
    half_lives = {
        "A": 120,
        "B": 7,
        "C1": 60,
        "C2": 90,
        "C3": 180,
        "D": 270,
    }
    couplings = [
        Coupling("C3", "A", -0.1),
        Coupling("C3", "B", 0.08),
        Coupling("A", "B", -0.08),
        Coupling("B", "A", -0.1),
        Coupling("D", "B", -0.06),
    ]
    first = transition_regime(
        previous,
        evidence,
        delta_days=1,
        half_life_days=half_lives,
        couplings=couplings,
    )
    second = transition_regime(
        previous,
        evidence,
        delta_days=1,
        half_life_days=half_lives,
        couplings=couplings,
    )
    assert first == second
    assert all(0.0 <= item.value <= 1.0 for item in first.values())
