from datetime import UTC, datetime

from global_regime_radar.opportunity.scanner import (
    MetricEvidence,
    OpportunityCandidate,
    OpportunityClass,
    OpportunityStatus,
    PermanentImpairment,
    RegimeContext,
    assess_candidate,
)
from global_regime_radar.stress.engine import StressLevel


def metric(value: float | None, key: str) -> MetricEvidence:
    return MetricEvidence(
        value=value,
        evidence_ids=(f"evidence:{key}",) if value is not None else (),
    )


def context(
    *,
    b: float = 0.7,
    c1: float = 0.7,
    c3: float = 0.7,
    d: float = 0.7,
    stress: StressLevel = StressLevel.L3,
    d_days: int = 120,
) -> RegimeContext:
    return RegimeContext(
        as_of=datetime(2026, 9, 27, tzinfo=UTC),
        engine="baseline1",
        states={
            "A": 0.5,
            "B": b,
            "C1": c1,
            "C2": 0.5,
            "C3": c3,
            "D": d,
        },
        state_coverage={state: 0.8 for state in ("A", "B", "C1", "C2", "C3", "D")},
        stress_level=stress,
        persistence_days={"D": d_days},
    )


def b_candidate(**overrides: float | None) -> OpportunityCandidate:
    values = {
        "price_damage": 0.9,
        "fundamental_damage": 0.3,
        "forced_liquidation": 0.8,
        "cash_flow_strength": 0.8,
    }
    values.update(overrides)
    return OpportunityCandidate(
        asset_id="asset-b",
        opportunity_class=OpportunityClass.B,
        metrics={key: metric(value, key) for key, value in values.items()},
        impairment=PermanentImpairment(),
    )


def c_candidate() -> OpportunityCandidate:
    return OpportunityCandidate(
        asset_id="asset-c",
        opportunity_class=OpportunityClass.C,
        metrics={
            "bottleneck_strength": metric(0.8, "bottleneck"),
            "cash_flow_strength": metric(0.8, "cash-flow"),
            "earnings_momentum": metric(0.7, "earnings"),
            "valuation_softness": metric(0.7, "valuation"),
        },
        impairment=PermanentImpairment(),
    )


def d_candidate() -> OpportunityCandidate:
    return OpportunityCandidate(
        asset_id="asset-d",
        opportunity_class=OpportunityClass.D,
        metrics={
            "repression_exposure": metric(0.8, "repression"),
            "real_asset_support": metric(0.8, "real-asset"),
            "valuation_softness": metric(0.7, "valuation"),
        },
        impairment=PermanentImpairment(),
    )


def test_b_fat_can_turn_on_when_price_damage_exceeds_fundamentals():
    result = assess_candidate(b_candidate(), context())
    assert result.status is OpportunityStatus.ON
    assert result.score is not None
    assert result.gate_ratio == 1.0


def test_large_drawdown_alone_cannot_trigger_b_fat():
    result = assess_candidate(
        b_candidate(
            fundamental_damage=0.85,
            forced_liquidation=0.2,
            cash_flow_strength=0.3,
        ),
        context(),
    )
    assert result.status is OpportunityStatus.OFF
    assert result.gate_ratio < 1.0


def test_low_stress_blocks_b_fat_even_with_dislocation():
    result = assess_candidate(
        b_candidate(),
        context(stress=StressLevel.L1),
    )
    assert result.status is not OpportunityStatus.ON


def test_c_fat_requires_physical_bottleneck_and_cash_flow():
    result = assess_candidate(c_candidate(), context())
    assert result.status is OpportunityStatus.ON
    assert all(gate.passed for gate in result.gates)


def test_d_fat_requires_persistence():
    result = assess_candidate(d_candidate(), context(d_days=20))
    assert result.status is not OpportunityStatus.ON
    assert any(gate.name == "D_persistence" and not gate.passed for gate in result.gates)


def test_permanent_impairment_hard_blocks_candidate():
    candidate = OpportunityCandidate(
        asset_id="impaired",
        opportunity_class=OpportunityClass.C,
        metrics=c_candidate().metrics,
        impairment=PermanentImpairment(technological_obsolescence=0.8),
    )
    result = assess_candidate(candidate, context())
    assert result.status is OpportunityStatus.OFF
    assert "technological obsolescence" in result.impairment_reasons


def test_missing_metric_returns_pending_data():
    result = assess_candidate(
        b_candidate(cash_flow_strength=None),
        context(),
    )
    assert result.status is OpportunityStatus.PENDING_DATA
    assert result.score is None
    assert "metric:cash_flow_strength:missing" in result.missing_requirements


def test_untraceable_metric_returns_pending_data():
    candidate = b_candidate()
    metrics = dict(candidate.metrics)
    metrics["cash_flow_strength"] = MetricEvidence(value=0.8)
    candidate = OpportunityCandidate(
        asset_id=candidate.asset_id,
        opportunity_class=candidate.opportunity_class,
        metrics=metrics,
        impairment=candidate.impairment,
    )
    result = assess_candidate(candidate, context())
    assert result.status is OpportunityStatus.PENDING_DATA
    assert "metric:cash_flow_strength:untraceable" in result.missing_requirements


def test_low_regime_coverage_returns_pending_data():
    ctx = context()
    coverage = dict(ctx.state_coverage)
    coverage["B"] = 0.1
    low_coverage = RegimeContext(
        as_of=ctx.as_of,
        engine=ctx.engine,
        states=ctx.states,
        state_coverage=coverage,
        stress_level=ctx.stress_level,
        persistence_days=ctx.persistence_days,
    )
    result = assess_candidate(b_candidate(), low_coverage)
    assert result.status is OpportunityStatus.PENDING_DATA


def test_explicit_engine_is_preserved_in_result():
    result = assess_candidate(c_candidate(), context())
    assert result.regime_engine == "baseline1"
