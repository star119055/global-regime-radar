from __future__ import annotations

from dataclasses import dataclass
from math import exp, log

from global_regime_radar.regime.baseline import StateEstimate


@dataclass(frozen=True)
class Coupling:
    source: str
    target: str
    coefficient: float


@dataclass(frozen=True)
class Jump:
    state: str
    magnitude: float
    event_id: str | None = None


@dataclass(frozen=True)
class DynamicState:
    state: str
    value: float
    variance: float


def persistence_coefficient(delta_days: float, half_life_days: float) -> float:
    if delta_days < 0:
        raise ValueError("delta_days must be non-negative")
    if half_life_days <= 0:
        raise ValueError("half_life_days must be positive")
    return exp(-log(2.0) * delta_days / half_life_days)


def _clip01(value: float) -> float:
    return min(1.0, max(0.0, value))


def transition_state(
    previous: DynamicState,
    evidence: StateEstimate,
    *,
    delta_days: float,
    half_life_days: float,
    source_states: dict[str, float],
    couplings: list[Coupling],
    jumps: list[Jump],
    process_variance_per_day: float = 0.0,
    missing_variance_per_day: float = 0.0,
) -> DynamicState:
    if previous.state != evidence.state:
        raise ValueError("previous and evidence state must match")
    if process_variance_per_day < 0 or missing_variance_per_day < 0:
        raise ValueError("variance growth rates must be non-negative")

    phi = persistence_coefficient(delta_days, half_life_days)
    innovation_strength = (1.0 - phi) * evidence.coverage
    value = previous.value + innovation_strength * (evidence.value - previous.value)

    coupling_delta = 0.0
    for coupling in couplings:
        if coupling.target != previous.state:
            continue
        if coupling.source not in source_states:
            raise ValueError(f"missing source state {coupling.source!r}")
        source_value = source_states[coupling.source]
        if not 0.0 <= source_value <= 1.0:
            raise ValueError("source state values must be within [0, 1]")
        coupling_delta += (1.0 - phi) * coupling.coefficient * (source_value - 0.5)

    jump_delta = sum(jump.magnitude for jump in jumps if jump.state == previous.state)
    value = _clip01(value + coupling_delta + jump_delta)

    evidence_share = innovation_strength
    variance = (
        phi**2 * previous.variance
        + evidence_share**2 * evidence.variance
        + process_variance_per_day * delta_days
        + missing_variance_per_day * delta_days * (1.0 - evidence.coverage)
    )

    return DynamicState(
        state=previous.state,
        value=value,
        variance=max(0.0, variance),
    )


def transition_regime(
    previous: dict[str, DynamicState],
    evidence: dict[str, StateEstimate],
    *,
    delta_days: float,
    half_life_days: dict[str, float],
    couplings: list[Coupling],
    jumps: list[Jump] | None = None,
    process_variance_per_day: dict[str, float] | None = None,
    missing_variance_per_day: float = 0.0,
) -> dict[str, DynamicState]:
    expected = ("A", "B", "C1", "C2", "C3", "D")
    for state in expected:
        if state not in previous or state not in evidence or state not in half_life_days:
            raise ValueError(f"incomplete dynamic configuration for {state}")

    process_variance_per_day = process_variance_per_day or {}
    jumps = jumps or []
    source_states = {state: previous[state].value for state in expected}

    return {
        state: transition_state(
            previous[state],
            evidence[state],
            delta_days=delta_days,
            half_life_days=half_life_days[state],
            source_states=source_states,
            couplings=couplings,
            jumps=jumps,
            process_variance_per_day=process_variance_per_day.get(state, 0.0),
            missing_variance_per_day=missing_variance_per_day,
        )
        for state in expected
    }
