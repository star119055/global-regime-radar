from datetime import UTC, datetime

import pytest

from global_regime_radar.arbitration.engine import (
    Disposition,
    SourceEvidence,
    SourceStatus,
    TeamClaim,
    TeamRole,
    arbitrate_claim,
    build_arbitration_report,
    detect_material_change,
)
from global_regime_radar.reporting.snapshot import (
    DailySnapshot,
    EvidenceKind,
    FatPitchStatus,
    FeedbackLoop,
    StateRow,
)
from global_regime_radar.stress.engine import StressLevel


def dt(day: int = 27) -> datetime:
    return datetime(2026, 9, day, 8, 30, tzinfo=UTC)


def snapshot(
    b: float,
    stress: StressLevel = StressLevel.L1,
    b_fat: FatPitchStatus = FatPitchStatus.OFF,
) -> DailySnapshot:
    states = []
    for state in ("A", "B", "C1", "C2", "C3", "D"):
        value = b if state == "B" else 0.5
        states.append(StateRow(state, value, 0.0, "Medium", 0.8, 0.04))
    return DailySnapshot(
        as_of=dt(),
        generated_at=dt(),
        model_version="v6.1",
        conclusion="test",
        states=tuple(states),
        stress_level=stress,
        fat_pitch={
            "B": b_fat,
            "C": FatPitchStatus.OFF,
            "D": FatPitchStatus.OFF,
        },
        top_changes=(),
        feedback_loop=FeedbackLoop("test", ("B", "A")),
        evidence=(),
        next_confirmation="next event",
        falsification_conditions=("condition",),
    )


def test_material_state_change_triggers_arbitration():
    trigger = detect_material_change(snapshot(0.60), snapshot(0.50))
    assert trigger.required
    assert any("B changed" in reason for reason in trigger.reasons)


def test_small_change_without_other_transition_does_not_trigger():
    trigger = detect_material_change(snapshot(0.52), snapshot(0.50))
    assert not trigger.required


def test_stress_change_triggers_even_without_state_move():
    trigger = detect_material_change(
        snapshot(0.50, StressLevel.L2),
        snapshot(0.50, StressLevel.L1),
    )
    assert trigger.required


def test_observed_claim_without_source_is_rejected():
    decision = arbitrate_claim(
        TeamClaim(
            "c1",
            TeamRole.RED,
            "repo",
            "Repo stress rose.",
            EvidenceKind.OBSERVED,
        ),
        {},
        as_of=dt(),
    )
    assert decision.disposition is Disposition.REJECTED
    assert decision.final_kind is EvidenceKind.UNCERTAIN


def test_future_source_cannot_support_observed_claim():
    decision = arbitrate_claim(
        TeamClaim(
            "c1",
            TeamRole.RED,
            "repo",
            "Repo stress rose.",
            EvidenceKind.OBSERVED,
            source_ids=("s1",),
        ),
        {
            "s1": SourceEvidence(
                "s1",
                datetime(2026, 9, 28, 8, 30, tzinfo=UTC),
            )
        },
        as_of=dt(),
    )
    assert decision.disposition is Disposition.RECLASSIFIED
    assert decision.missing_sources == ("s1",)


def test_stale_source_is_reclassified_uncertain():
    decision = arbitrate_claim(
        TeamClaim(
            "c1",
            TeamRole.RED,
            "repo",
            "Repo stress rose.",
            EvidenceKind.OBSERVED,
            source_ids=("s1",),
        ),
        {
            "s1": SourceEvidence(
                "s1",
                dt(26),
                status=SourceStatus.STALE,
            )
        },
        as_of=dt(),
    )
    assert decision.final_kind is EvidenceKind.UNCERTAIN


def test_verified_point_in_time_source_is_admissible():
    decision = arbitrate_claim(
        TeamClaim(
            "c1",
            TeamRole.RED,
            "repo",
            "Repo stress rose.",
            EvidenceKind.OBSERVED,
            source_ids=("s1",),
        ),
        {"s1": SourceEvidence("s1", dt(26))},
        as_of=dt(),
    )
    assert decision.disposition is Disposition.ADMISSIBLE
    assert decision.final_kind is EvidenceKind.OBSERVED


def test_inference_without_falsifier_is_reclassified():
    decision = arbitrate_claim(
        TeamClaim(
            "c2",
            TeamRole.BLACK,
            "credit",
            "Dealer stress may spill into credit.",
            EvidenceKind.INFERRED,
        ),
        {},
        as_of=dt(),
    )
    assert decision.disposition is Disposition.RECLASSIFIED


def test_conflicting_roles_are_not_resolved_by_vote():
    current = snapshot(0.60)
    trigger = detect_material_change(current, snapshot(0.50))
    claims = [
        TeamClaim(
            "red-1",
            TeamRole.RED,
            "funding",
            "The move may be a reporting artifact.",
            EvidenceKind.INFERRED,
            falsifier="A second independent funding source confirms the move.",
            conflict_group="funding-direction",
        ),
        TeamClaim(
            "black-1",
            TeamRole.BLACK,
            "funding",
            "Funding stress may be nonlinear.",
            EvidenceKind.INFERRED,
            falsifier="Funding spreads normalize for five sessions.",
            conflict_group="funding-direction",
        ),
    ]
    report = build_arbitration_report(current, trigger, claims, {})
    assert report.unresolved_conflict_groups == ("funding-direction",)
    assert len(report.decisions) == 2


def test_report_requires_material_trigger():
    with pytest.raises(ValueError, match="material-change trigger"):
        build_arbitration_report(
            snapshot(0.50),
            detect_material_change(snapshot(0.50), snapshot(0.50)),
            [],
            {},
        )
