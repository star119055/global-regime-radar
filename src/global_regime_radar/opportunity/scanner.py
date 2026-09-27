from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from global_regime_radar.stress.engine import StressLevel


class OpportunityClass(str, Enum):
    B = "B"
    C = "C"
    D = "D"


class OpportunityStatus(str, Enum):
    PENDING_DATA = "PENDING_DATA"
    OFF = "OFF"
    WATCH = "WATCH"
    ON = "ON"


@dataclass(frozen=True)
class MetricEvidence:
    value: float | None
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.value is not None and not 0.0 <= self.value <= 1.0:
            raise ValueError("metric value must be within [0, 1]")


@dataclass(frozen=True)
class PermanentImpairment:
    business_deterioration: float = 0.0
    technological_obsolescence: float = 0.0
    unfinanceable_debt: float = 0.0
    pricing_power_loss: float = 0.0
    permanent_customer_loss: float = 0.0
    replacement_cost_collapse: float = 0.0

    def __post_init__(self) -> None:
        for field_name in (
            "business_deterioration",
            "technological_obsolescence",
            "unfinanceable_debt",
            "pricing_power_loss",
            "permanent_customer_loss",
            "replacement_cost_collapse",
        ):
            value = getattr(self, field_name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field_name} must be within [0, 1]")

    @property
    def maximum(self) -> float:
        return max(
            self.business_deterioration,
            self.technological_obsolescence,
            self.unfinanceable_debt,
            self.pricing_power_loss,
            self.permanent_customer_loss,
            self.replacement_cost_collapse,
        )

    def reasons(self, threshold: float) -> tuple[str, ...]:
        labels = {
            "business_deterioration": "structural business deterioration",
            "technological_obsolescence": "technological obsolescence",
            "unfinanceable_debt": "unfinanceable debt",
            "pricing_power_loss": "permanent pricing-power loss",
            "permanent_customer_loss": "permanent customer loss",
            "replacement_cost_collapse": "replacement-cost collapse",
        }
        return tuple(
            labels[field_name]
            for field_name in labels
            if getattr(self, field_name) >= threshold
        )


@dataclass(frozen=True)
class RegimeContext:
    as_of: datetime
    engine: str
    states: dict[str, float]
    state_coverage: dict[str, float]
    stress_level: StressLevel
    persistence_days: dict[str, int]

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        if self.engine not in {"baseline0", "baseline1", "ukf"}:
            raise ValueError("engine must be baseline0, baseline1 or ukf")
        for state in ("A", "B", "C1", "C2", "C3", "D"):
            if state not in self.states or state not in self.state_coverage:
                raise ValueError(f"missing regime context for {state}")
            if not 0.0 <= self.states[state] <= 1.0:
                raise ValueError("state values must be within [0, 1]")
            if not 0.0 <= self.state_coverage[state] <= 1.0:
                raise ValueError("state coverage must be within [0, 1]")


@dataclass(frozen=True)
class OpportunityCandidate:
    asset_id: str
    opportunity_class: OpportunityClass
    metrics: dict[str, MetricEvidence]
    impairment: PermanentImpairment

    def __post_init__(self) -> None:
        if not self.asset_id.strip():
            raise ValueError("asset_id cannot be empty")


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    actual: float | str
    threshold: float | str
    detail: str


@dataclass(frozen=True)
class OpportunityAssessment:
    asset_id: str
    opportunity_class: OpportunityClass
    status: OpportunityStatus
    score: float | None
    gate_ratio: float
    gates: tuple[GateResult, ...]
    missing_requirements: tuple[str, ...]
    impairment_score: float
    impairment_reasons: tuple[str, ...]
    regime_engine: str


@dataclass(frozen=True)
class ScannerConfig:
    minimum_state_coverage: float = 0.40
    permanent_impairment_block: float = 0.50
    watch_score: float = 0.18
    on_score: float = 0.30
    minimum_watch_gate_ratio: float = 0.60

    b_state_threshold: float = 0.60
    b_minimum_stress: StressLevel = StressLevel.L2
    b_forced_liquidation: float = 0.60
    b_cash_flow_strength: float = 0.60
    b_dislocation_gap: float = 0.25

    c_state_threshold: float = 0.60
    c_bottleneck_strength: float = 0.60
    c_cash_flow_strength: float = 0.60
    c_earnings_momentum: float = 0.50
    c_valuation_softness: float = 0.50

    d_state_threshold: float = 0.60
    d_minimum_persistence_days: int = 90
    d_repression_exposure: float = 0.60
    d_real_asset_support: float = 0.60

    def __post_init__(self) -> None:
        bounded = (
            self.minimum_state_coverage,
            self.permanent_impairment_block,
            self.watch_score,
            self.on_score,
            self.minimum_watch_gate_ratio,
            self.b_state_threshold,
            self.b_forced_liquidation,
            self.b_cash_flow_strength,
            self.b_dislocation_gap,
            self.c_state_threshold,
            self.c_bottleneck_strength,
            self.c_cash_flow_strength,
            self.c_earnings_momentum,
            self.c_valuation_softness,
            self.d_state_threshold,
            self.d_repression_exposure,
            self.d_real_asset_support,
        )
        if any(not 0.0 <= value <= 1.0 for value in bounded):
            raise ValueError("scanner thresholds must be within [0, 1]")
        if self.watch_score > self.on_score:
            raise ValueError("watch_score must be <= on_score")
        if self.d_minimum_persistence_days < 0:
            raise ValueError("d_minimum_persistence_days must be non-negative")


_REQUIRED_METRICS = {
    OpportunityClass.B: (
        "price_damage",
        "fundamental_damage",
        "forced_liquidation",
        "cash_flow_strength",
    ),
    OpportunityClass.C: (
        "bottleneck_strength",
        "cash_flow_strength",
        "earnings_momentum",
        "valuation_softness",
    ),
    OpportunityClass.D: (
        "repression_exposure",
        "real_asset_support",
        "valuation_softness",
    ),
}


def _metric(candidate: OpportunityCandidate, key: str) -> float:
    evidence = candidate.metrics[key]
    assert evidence.value is not None
    return evidence.value


def _missing_requirements(
    candidate: OpportunityCandidate,
    context: RegimeContext,
    config: ScannerConfig,
) -> tuple[str, ...]:
    missing: list[str] = []
    for key in _REQUIRED_METRICS[candidate.opportunity_class]:
        evidence = candidate.metrics.get(key)
        if evidence is None or evidence.value is None:
            missing.append(f"metric:{key}:missing")
        elif not evidence.evidence_ids:
            missing.append(f"metric:{key}:untraceable")

    required_states = {
        OpportunityClass.B: ("B",),
        OpportunityClass.C: ("C1", "C3"),
        OpportunityClass.D: ("D",),
    }[candidate.opportunity_class]
    for state in required_states:
        if context.state_coverage[state] < config.minimum_state_coverage:
            missing.append(
                f"state:{state}:coverage={context.state_coverage[state]:.3f}"
            )
    return tuple(missing)


def _gate(
    name: str,
    actual: float,
    threshold: float,
    *,
    detail: str,
) -> GateResult:
    return GateResult(
        name=name,
        passed=actual >= threshold,
        actual=actual,
        threshold=threshold,
        detail=detail,
    )


def _assess_b(
    candidate: OpportunityCandidate,
    context: RegimeContext,
    config: ScannerConfig,
) -> tuple[tuple[GateResult, ...], float]:
    price_damage = _metric(candidate, "price_damage")
    fundamental_damage = _metric(candidate, "fundamental_damage")
    forced_liquidation = _metric(candidate, "forced_liquidation")
    cash_flow = _metric(candidate, "cash_flow_strength")
    dislocation = max(price_damage - fundamental_damage, 0.0)

    gates = (
        _gate(
            "B_state",
            context.states["B"],
            config.b_state_threshold,
            detail="financial microstructure deleveraging is active",
        ),
        GateResult(
            name="Stress",
            passed=context.stress_level >= config.b_minimum_stress,
            actual=context.stress_level.name,
            threshold=config.b_minimum_stress.name,
            detail="market-function stress is material",
        ),
        _gate(
            "forced_liquidation",
            forced_liquidation,
            config.b_forced_liquidation,
            detail="price pressure is plausibly forced rather than purely fundamental",
        ),
        _gate(
            "cash_flow_strength",
            cash_flow,
            config.b_cash_flow_strength,
            detail="cash-flow resilience remains intact",
        ),
        _gate(
            "price_minus_fundamental_damage",
            dislocation,
            config.b_dislocation_gap,
            detail="price deterioration exceeds fundamental deterioration",
        ),
    )
    dislocation_score = min(dislocation / max(config.b_dislocation_gap, 1e-9), 1.0)
    score = forced_liquidation * cash_flow * dislocation_score
    return gates, score


def _assess_c(
    candidate: OpportunityCandidate,
    context: RegimeContext,
    config: ScannerConfig,
) -> tuple[tuple[GateResult, ...], float]:
    bottleneck = _metric(candidate, "bottleneck_strength")
    cash_flow = _metric(candidate, "cash_flow_strength")
    earnings = _metric(candidate, "earnings_momentum")
    valuation = _metric(candidate, "valuation_softness")
    c_state = max(context.states["C1"], context.states["C3"])

    gates = (
        _gate(
            "C_state",
            c_state,
            config.c_state_threshold,
            detail="physical or industrial inflation pressure is active",
        ),
        _gate(
            "bottleneck_strength",
            bottleneck,
            config.c_bottleneck_strength,
            detail="the physical bottleneck is hard and observable",
        ),
        _gate(
            "cash_flow_strength",
            cash_flow,
            config.c_cash_flow_strength,
            detail="cash flow confirms the bottleneck",
        ),
        _gate(
            "earnings_momentum",
            earnings,
            config.c_earnings_momentum,
            detail="earnings are improving",
        ),
        _gate(
            "valuation_softness",
            valuation,
            config.c_valuation_softness,
            detail="valuation has not fully repriced the cash-flow improvement",
        ),
    )
    score = bottleneck * cash_flow * ((earnings + valuation) / 2.0)
    return gates, score


def _assess_d(
    candidate: OpportunityCandidate,
    context: RegimeContext,
    config: ScannerConfig,
) -> tuple[tuple[GateResult, ...], float]:
    repression = _metric(candidate, "repression_exposure")
    real_asset = _metric(candidate, "real_asset_support")
    valuation = _metric(candidate, "valuation_softness")
    persistence = context.persistence_days.get("D", 0)

    gates = (
        _gate(
            "D_state",
            context.states["D"],
            config.d_state_threshold,
            detail="financial repression is active",
        ),
        GateResult(
            name="D_persistence",
            passed=persistence >= config.d_minimum_persistence_days,
            actual=str(persistence),
            threshold=str(config.d_minimum_persistence_days),
            detail="repression is persistent rather than a one-day event",
        ),
        _gate(
            "repression_exposure",
            repression,
            config.d_repression_exposure,
            detail="candidate benefits from the repression channel",
        ),
        _gate(
            "real_asset_support",
            real_asset,
            config.d_real_asset_support,
            detail="cash flow or replacement value has real-asset support",
        ),
    )
    score = repression * real_asset * valuation
    return gates, score


def assess_candidate(
    candidate: OpportunityCandidate,
    context: RegimeContext,
    config: ScannerConfig | None = None,
) -> OpportunityAssessment:
    config = config or ScannerConfig()
    missing = _missing_requirements(candidate, context, config)
    impairment_score = candidate.impairment.maximum
    impairment_reasons = candidate.impairment.reasons(
        config.permanent_impairment_block
    )

    if missing:
        return OpportunityAssessment(
            asset_id=candidate.asset_id,
            opportunity_class=candidate.opportunity_class,
            status=OpportunityStatus.PENDING_DATA,
            score=None,
            gate_ratio=0.0,
            gates=(),
            missing_requirements=missing,
            impairment_score=impairment_score,
            impairment_reasons=impairment_reasons,
            regime_engine=context.engine,
        )

    if candidate.opportunity_class is OpportunityClass.B:
        gates, pre_impairment_score = _assess_b(candidate, context, config)
    elif candidate.opportunity_class is OpportunityClass.C:
        gates, pre_impairment_score = _assess_c(candidate, context, config)
    else:
        gates, pre_impairment_score = _assess_d(candidate, context, config)

    gate_ratio = sum(gate.passed for gate in gates) / len(gates)
    score = pre_impairment_score * (1.0 - impairment_score)

    if impairment_score >= config.permanent_impairment_block:
        status = OpportunityStatus.OFF
    elif all(gate.passed for gate in gates) and score >= config.on_score:
        status = OpportunityStatus.ON
    elif (
        gate_ratio >= config.minimum_watch_gate_ratio
        and score >= config.watch_score
    ):
        status = OpportunityStatus.WATCH
    else:
        status = OpportunityStatus.OFF

    return OpportunityAssessment(
        asset_id=candidate.asset_id,
        opportunity_class=candidate.opportunity_class,
        status=status,
        score=score,
        gate_ratio=gate_ratio,
        gates=gates,
        missing_requirements=(),
        impairment_score=impairment_score,
        impairment_reasons=impairment_reasons,
        regime_engine=context.engine,
    )


def scan_candidates(
    candidates: list[OpportunityCandidate],
    context: RegimeContext,
    config: ScannerConfig | None = None,
) -> tuple[OpportunityAssessment, ...]:
    return tuple(
        assess_candidate(candidate, context, config)
        for candidate in candidates
    )
