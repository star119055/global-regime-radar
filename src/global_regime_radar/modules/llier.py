from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class LLIERStatus(str, Enum):
    BASELINE_ELIGIBLE = "BASELINE_ELIGIBLE"
    ENERGIZED = "ENERGIZED"
    WITHDRAWN = "WITHDRAWN"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class LLIERProjectObservation:
    project_id: str
    observed_at: datetime
    mw: float
    status: LLIERStatus
    process_regime: str

    def __post_init__(self) -> None:
        if not self.project_id:
            raise ValueError("project_id cannot be empty")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if self.mw <= 0:
            raise ValueError("mw must be positive")
        if not self.process_regime:
            raise ValueError("process_regime cannot be empty")


@dataclass(frozen=True)
class LLIERCohortResult:
    baseline_at: datetime
    horizon_at: datetime
    process_regime: str
    baseline_projects: tuple[str, ...]
    baseline_mw: float
    energized_mw: float
    conversion_rate: float
    unresolved_exit_projects: tuple[str, ...]


def estimate_llier_cohort(
    observations: list[LLIERProjectObservation],
    *,
    baseline_at: datetime,
    horizon_at: datetime,
    process_regime: str,
    exit_policy: str = "block",
) -> LLIERCohortResult:
    if baseline_at.tzinfo is None or baseline_at.utcoffset() is None:
        raise ValueError("baseline_at must be timezone-aware")
    if horizon_at.tzinfo is None or horizon_at.utcoffset() is None:
        raise ValueError("horizon_at must be timezone-aware")
    if horizon_at <= baseline_at:
        raise ValueError("horizon_at must be after baseline_at")
    if exit_policy not in {"block", "count_as_failure", "censor"}:
        raise ValueError("unsupported exit_policy")

    rows = sorted(observations, key=lambda row: (row.project_id, row.observed_at))
    regimes = {row.process_regime for row in rows}
    if regimes - {process_regime}:
        raise ValueError("cohort contains observations from another process regime")

    by_project: dict[str, list[LLIERProjectObservation]] = {}
    for row in rows:
        by_project.setdefault(row.project_id, []).append(row)

    baseline: dict[str, LLIERProjectObservation] = {}
    for project_id, project_rows in by_project.items():
        eligible = [
            row
            for row in project_rows
            if row.observed_at <= baseline_at
            and row.status is LLIERStatus.BASELINE_ELIGIBLE
        ]
        if eligible:
            baseline[project_id] = eligible[-1]

    if not baseline:
        raise ValueError("LLIER requires a non-empty frozen baseline cohort")

    unresolved_exits: list[str] = []
    denominator = 0.0
    energized = 0.0

    for project_id, baseline_row in sorted(baseline.items()):
        later_rows = [
            row
            for row in by_project[project_id]
            if baseline_at < row.observed_at <= horizon_at
        ]
        terminal = later_rows[-1] if later_rows else baseline_row

        exited = terminal.status in {LLIERStatus.WITHDRAWN, LLIERStatus.CANCELLED}
        if exited and exit_policy == "block":
            unresolved_exits.append(project_id)
            continue
        if exited and exit_policy == "censor":
            continue

        denominator += baseline_row.mw
        if any(row.status is LLIERStatus.ENERGIZED for row in later_rows):
            energized += baseline_row.mw

    if unresolved_exits:
        raise ValueError(
            "LLIER exit treatment unresolved for projects: "
            + ",".join(unresolved_exits)
        )
    if denominator <= 0:
        raise ValueError("LLIER denominator is empty after exit policy")

    return LLIERCohortResult(
        baseline_at=baseline_at,
        horizon_at=horizon_at,
        process_regime=process_regime,
        baseline_projects=tuple(sorted(baseline)),
        baseline_mw=denominator,
        energized_mw=energized,
        conversion_rate=energized / denominator,
        unresolved_exit_projects=(),
    )


def aggregate_context_is_authoritative_llier(
    *,
    stable_project_ids_present: bool,
    frozen_baseline_cohort_present: bool,
    status_transition_history_present: bool,
) -> bool:
    return all(
        (
            stable_project_ids_present,
            frozen_baseline_cohort_present,
            status_transition_history_present,
        )
    )
