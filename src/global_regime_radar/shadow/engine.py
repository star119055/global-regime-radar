from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from global_regime_radar.filtering.ukf import (
    FilteredState,
    UKFState,
    initialize_filter,
    measurement_from_estimate,
    step,
    summarize,
)
from global_regime_radar.regime.baseline import (
    IndicatorEvidence,
    StateEstimate,
    estimate_regime,
)
from global_regime_radar.regime.dynamics import (
    Coupling,
    DynamicState,
    Jump,
    transition_regime,
)

STATES = ("A", "B", "C1", "C2", "C3", "D")
ENGINES = ("baseline0", "baseline1", "ukf")


class ShadowStatus(str, Enum):
    COMPLETED = "COMPLETED"
    PENDING_DATA = "PENDING_DATA"


@dataclass(frozen=True)
class EngineState:
    state: str
    value: float
    variance: float
    confidence: str

    def __post_init__(self) -> None:
        if self.state not in STATES:
            raise ValueError(f"unsupported state {self.state!r}")
        if not 0.0 <= self.value <= 1.0:
            raise ValueError("state value must be within [0, 1]")
        if self.variance < 0:
            raise ValueError("variance must be non-negative")


@dataclass(frozen=True)
class EngineResult:
    engine: str
    states: tuple[EngineState, ...]

    def __post_init__(self) -> None:
        if self.engine not in ENGINES:
            raise ValueError(f"unsupported engine {self.engine!r}")
        keys = tuple(item.state for item in self.states)
        if len(keys) != len(STATES) or set(keys) != set(STATES):
            raise ValueError("engine result must contain all six states exactly once")


@dataclass(frozen=True)
class ShadowDisagreement:
    state: str
    minimum: float
    maximum: float
    spread: float
    baseline0_vs_baseline1: float
    baseline0_vs_ukf: float
    baseline1_vs_ukf: float


@dataclass(frozen=True)
class ShadowRun:
    run_id: str
    decision_time: datetime
    generated_at: datetime
    status: ShadowStatus
    dataset_hash: str
    config_hash: str
    feature_set_version: str
    results: tuple[EngineResult, ...]
    missing_requirements: tuple[str, ...]
    disagreements: tuple[ShadowDisagreement, ...]

    def __post_init__(self) -> None:
        for field_name in ("decision_time", "generated_at"):
            value = getattr(self, field_name)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{field_name} must be timezone-aware")
        if not self.dataset_hash:
            raise ValueError("dataset_hash cannot be empty")
        if not self.config_hash:
            raise ValueError("config_hash cannot be empty")
        if self.status is ShadowStatus.COMPLETED:
            engines = tuple(result.engine for result in self.results)
            if set(engines) != set(ENGINES) or len(engines) != len(ENGINES):
                raise ValueError("completed shadow run requires exactly three engines")
            if self.missing_requirements:
                raise ValueError("completed run cannot have missing requirements")


@dataclass(frozen=True)
class ShadowOutcome:
    run_id: str
    horizon_days: int
    attached_at: datetime
    metrics: dict[str, float]

    def __post_init__(self) -> None:
        if self.horizon_days <= 0:
            raise ValueError("horizon_days must be positive")
        if self.attached_at.tzinfo is None or self.attached_at.utcoffset() is None:
            raise ValueError("attached_at must be timezone-aware")


def canonical_config_hash(config: dict[str, Any]) -> str:
    raw = json.dumps(
        config,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _run_id(
    *,
    decision_time: datetime,
    dataset_hash: str,
    config_hash: str,
    feature_set_version: str,
) -> str:
    material = (
        f"{decision_time.isoformat()}|{dataset_hash}|"
        f"{config_hash}|{feature_set_version}"
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _confidence_from_variance(variance: float) -> str:
    if variance <= 0.01:
        return "High"
    if variance <= 0.04:
        return "Medium"
    return "Low"


def _baseline0_result(estimates: dict[str, StateEstimate]) -> EngineResult:
    return EngineResult(
        engine="baseline0",
        states=tuple(
            EngineState(
                state=state,
                value=estimates[state].value,
                variance=estimates[state].variance,
                confidence=estimates[state].confidence,
            )
            for state in STATES
        ),
    )


def _baseline1_result(states: dict[str, DynamicState]) -> EngineResult:
    return EngineResult(
        engine="baseline1",
        states=tuple(
            EngineState(
                state=state,
                value=states[state].value,
                variance=states[state].variance,
                confidence=_confidence_from_variance(states[state].variance),
            )
            for state in STATES
        ),
    )


def _ukf_result(states: dict[str, FilteredState]) -> EngineResult:
    return EngineResult(
        engine="ukf",
        states=tuple(
            EngineState(
                state=state,
                value=states[state].value,
                variance=states[state].variance,
                confidence=states[state].confidence,
            )
            for state in STATES
        ),
    )


def compute_disagreements(
    results: tuple[EngineResult, ...],
) -> tuple[ShadowDisagreement, ...]:
    by_engine = {
        result.engine: {item.state: item.value for item in result.states}
        for result in results
    }
    missing = [engine for engine in ENGINES if engine not in by_engine]
    if missing:
        raise ValueError(f"missing engine outputs: {', '.join(missing)}")

    rows: list[ShadowDisagreement] = []
    for state in STATES:
        b0 = by_engine["baseline0"][state]
        b1 = by_engine["baseline1"][state]
        ukf = by_engine["ukf"][state]
        values = (b0, b1, ukf)
        rows.append(
            ShadowDisagreement(
                state=state,
                minimum=min(values),
                maximum=max(values),
                spread=max(values) - min(values),
                baseline0_vs_baseline1=abs(b0 - b1),
                baseline0_vs_ukf=abs(b0 - ukf),
                baseline1_vs_ukf=abs(b1 - ukf),
            )
        )
    return tuple(rows)


def readiness_gaps(
    estimates: dict[str, StateEstimate],
    *,
    minimum_state_coverage: float,
) -> tuple[str, ...]:
    if not 0.0 <= minimum_state_coverage <= 1.0:
        raise ValueError("minimum_state_coverage must be within [0, 1]")
    gaps: list[str] = []
    for state in STATES:
        estimate = estimates.get(state)
        if estimate is None:
            gaps.append(f"{state}:missing")
        elif estimate.coverage < minimum_state_coverage:
            gaps.append(
                f"{state}:coverage={estimate.coverage:.3f}"
                f"<{minimum_state_coverage:.3f}"
            )
    return tuple(gaps)


def pending_shadow_run(
    *,
    decision_time: datetime,
    generated_at: datetime,
    dataset_hash: str,
    config_hash: str,
    feature_set_version: str,
    missing_requirements: tuple[str, ...],
) -> ShadowRun:
    return ShadowRun(
        run_id=_run_id(
            decision_time=decision_time,
            dataset_hash=dataset_hash,
            config_hash=config_hash,
            feature_set_version=feature_set_version,
        ),
        decision_time=decision_time,
        generated_at=generated_at,
        status=ShadowStatus.PENDING_DATA,
        dataset_hash=dataset_hash,
        config_hash=config_hash,
        feature_set_version=feature_set_version,
        results=(),
        missing_requirements=missing_requirements,
        disagreements=(),
    )


def run_shadow(
    *,
    decision_time: datetime,
    generated_at: datetime,
    dataset_hash: str,
    config_hash: str,
    feature_set_version: str,
    evidence: dict[str, list[IndicatorEvidence]],
    prior_dynamic: dict[str, DynamicState] | None,
    prior_ukf: UKFState | None,
    prior_time: datetime | None,
    half_life_days: dict[str, float],
    dynamic_process_variance_per_day: dict[str, float],
    ukf_process_variance_per_day: dict[str, float],
    couplings: list[Coupling],
    jumps: list[Jump] | None = None,
    minimum_state_coverage: float = 0.40,
    missing_variance_per_day: float = 0.0,
) -> tuple[ShadowRun, dict[str, DynamicState], UKFState]:
    estimates = estimate_regime(evidence)
    gaps = readiness_gaps(
        estimates,
        minimum_state_coverage=minimum_state_coverage,
    )
    if gaps:
        pending = pending_shadow_run(
            decision_time=decision_time,
            generated_at=generated_at,
            dataset_hash=dataset_hash,
            config_hash=config_hash,
            feature_set_version=feature_set_version,
            missing_requirements=gaps,
        )
        raise ShadowPendingData(pending)

    if prior_time is None:
        prior_time = decision_time

    if prior_dynamic is None:
        prior_dynamic = {
            state: DynamicState(
                state=state,
                value=estimates[state].value,
                variance=estimates[state].variance,
            )
            for state in STATES
        }

    delta_days = (decision_time - prior_time).total_seconds() / 86400.0
    if delta_days < 0:
        raise ValueError("decision_time cannot precede prior_time")

    dynamic = transition_regime(
        prior_dynamic,
        estimates,
        delta_days=delta_days,
        half_life_days=half_life_days,
        couplings=couplings,
        jumps=jumps or [],
        process_variance_per_day=dynamic_process_variance_per_day,
        missing_variance_per_day=missing_variance_per_day,
    )

    if prior_ukf is None:
        prior_ukf = initialize_filter(
            {state: estimates[state].value for state in STATES},
            {state: estimates[state].variance for state in STATES},
            as_of=prior_time,
        )

    measurements = [
        measurement
        for state in STATES
        if (measurement := measurement_from_estimate(estimates[state])) is not None
    ]
    posterior = step(
        prior_ukf,
        measurements,
        as_of=decision_time,
        half_life_days=half_life_days,
        process_variance_per_day=ukf_process_variance_per_day,
        couplings=couplings,
        jumps=jumps or [],
    )
    ukf_states = summarize(posterior)

    results = (
        _baseline0_result(estimates),
        _baseline1_result(dynamic),
        _ukf_result(ukf_states),
    )
    run = ShadowRun(
        run_id=_run_id(
            decision_time=decision_time,
            dataset_hash=dataset_hash,
            config_hash=config_hash,
            feature_set_version=feature_set_version,
        ),
        decision_time=decision_time,
        generated_at=generated_at,
        status=ShadowStatus.COMPLETED,
        dataset_hash=dataset_hash,
        config_hash=config_hash,
        feature_set_version=feature_set_version,
        results=results,
        missing_requirements=(),
        disagreements=compute_disagreements(results),
    )
    return run, dynamic, posterior


class ShadowPendingData(RuntimeError):
    def __init__(self, run: ShadowRun) -> None:
        super().__init__("shadow run is pending required data")
        self.run = run
