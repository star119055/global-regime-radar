from datetime import UTC, datetime

import pytest

from global_regime_radar.modules.llier import (
    LLIERProjectObservation,
    LLIERStatus,
    aggregate_context_is_authoritative_llier,
    estimate_llier_cohort,
)


def dt(day: int) -> datetime:
    return datetime(2026, 6, day, tzinfo=UTC)


def test_llier_uses_same_frozen_baseline_cohort():
    rows = [
        LLIERProjectObservation("A", dt(1), 100.0, LLIERStatus.BASELINE_ELIGIBLE, "legacy"),
        LLIERProjectObservation("B", dt(1), 200.0, LLIERStatus.BASELINE_ELIGIBLE, "legacy"),
        LLIERProjectObservation("A", dt(20), 120.0, LLIERStatus.ENERGIZED, "legacy"),
        LLIERProjectObservation("C", dt(10), 500.0, LLIERStatus.BASELINE_ELIGIBLE, "legacy"),
    ]
    result = estimate_llier_cohort(
        rows,
        baseline_at=dt(5),
        horizon_at=dt(30),
        process_regime="legacy",
    )
    assert result.baseline_projects == ("A", "B")
    assert result.baseline_mw == 300.0
    assert result.energized_mw == 100.0
    assert result.conversion_rate == pytest.approx(1 / 3)


def test_llier_blocks_unresolved_baseline_project_exit():
    rows = [
        LLIERProjectObservation("A", dt(1), 100.0, LLIERStatus.BASELINE_ELIGIBLE, "legacy"),
        LLIERProjectObservation("A", dt(20), 100.0, LLIERStatus.CANCELLED, "legacy"),
    ]
    with pytest.raises(ValueError, match="exit treatment unresolved"):
        estimate_llier_cohort(
            rows,
            baseline_at=dt(5),
            horizon_at=dt(30),
            process_regime="legacy",
        )


def test_llier_can_apply_predeclared_failure_exit_policy():
    rows = [
        LLIERProjectObservation("A", dt(1), 100.0, LLIERStatus.BASELINE_ELIGIBLE, "legacy"),
        LLIERProjectObservation("B", dt(1), 100.0, LLIERStatus.BASELINE_ELIGIBLE, "legacy"),
        LLIERProjectObservation("A", dt(20), 100.0, LLIERStatus.CANCELLED, "legacy"),
        LLIERProjectObservation("B", dt(20), 100.0, LLIERStatus.ENERGIZED, "legacy"),
    ]
    result = estimate_llier_cohort(
        rows,
        baseline_at=dt(5),
        horizon_at=dt(30),
        process_regime="legacy",
        exit_policy="count_as_failure",
    )
    assert result.conversion_rate == 0.5


def test_llier_rejects_silent_process_regime_mix():
    rows = [
        LLIERProjectObservation("A", dt(1), 100.0, LLIERStatus.BASELINE_ELIGIBLE, "legacy"),
        LLIERProjectObservation("A", dt(20), 100.0, LLIERStatus.ENERGIZED, "batch_zero"),
    ]
    with pytest.raises(ValueError, match="another process regime"):
        estimate_llier_cohort(
            rows,
            baseline_at=dt(5),
            horizon_at=dt(30),
            process_regime="legacy",
        )


def test_aggregate_queue_context_does_not_qualify_as_llier():
    assert not aggregate_context_is_authoritative_llier(
        stable_project_ids_present=False,
        frozen_baseline_cohort_present=False,
        status_transition_history_present=False,
    )
    assert aggregate_context_is_authoritative_llier(
        stable_project_ids_present=True,
        frozen_baseline_cohort_present=True,
        status_transition_history_present=True,
    )
