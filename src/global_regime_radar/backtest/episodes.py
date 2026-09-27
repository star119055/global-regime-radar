from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from global_regime_radar.stress.engine import StressLevel


class EpisodeStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    PENDING_DATA = "PENDING_DATA"


@dataclass(frozen=True)
class EpisodeDefinition:
    episode_id: str
    name: str
    event_start: datetime
    event_end: datetime
    lead_window_days: int
    required_features: frozenset[str]
    min_peak_stress: StressLevel | None = None
    expected_state_peaks: dict[str, float] | None = None

    def __post_init__(self) -> None:
        if self.event_start.tzinfo is None or self.event_start.utcoffset() is None:
            raise ValueError("event_start must be timezone-aware")
        if self.event_end.tzinfo is None or self.event_end.utcoffset() is None:
            raise ValueError("event_end must be timezone-aware")
        if self.event_end < self.event_start:
            raise ValueError("event_end must be >= event_start")
        if self.lead_window_days < 0:
            raise ValueError("lead_window_days must be non-negative")
        for state, value in (self.expected_state_peaks or {}).items():
            if state not in {"A", "B", "C1", "C2", "C3", "D"}:
                raise ValueError(f"unsupported state {state!r}")
            if not 0.0 <= value <= 1.0:
                raise ValueError("state peak thresholds must be within [0, 1]")


@dataclass(frozen=True)
class EpisodePoint:
    as_of: datetime
    stress_level: StressLevel
    states: dict[str, float]
    available_features: frozenset[str]

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        for state, value in self.states.items():
            if state not in {"A", "B", "C1", "C2", "C3", "D"}:
                raise ValueError(f"unsupported state {state!r}")
            if not 0.0 <= value <= 1.0:
                raise ValueError("state values must be within [0, 1]")


@dataclass(frozen=True)
class EpisodeEvaluation:
    episode_id: str
    status: EpisodeStatus
    missing_features: tuple[str, ...]
    peak_stress: StressLevel | None
    state_peaks: dict[str, float]
    first_trigger_at: datetime | None
    lead_days: float | None
    reasons: tuple[str, ...]


def _window(definition: EpisodeDefinition) -> tuple[datetime, datetime]:
    return (
        definition.event_start - timedelta(days=definition.lead_window_days),
        definition.event_end,
    )


def _qualifies(point: EpisodePoint, definition: EpisodeDefinition) -> bool:
    if (
        definition.min_peak_stress is not None
        and point.stress_level < definition.min_peak_stress
    ):
        return False
    for state, threshold in (definition.expected_state_peaks or {}).items():
        if point.states.get(state, 0.0) < threshold:
            return False
    return True


def evaluate_episode(
    definition: EpisodeDefinition,
    timeline: list[EpisodePoint],
) -> EpisodeEvaluation:
    start, end = _window(definition)
    points = sorted(
        (point for point in timeline if start <= point.as_of <= end),
        key=lambda point: point.as_of,
    )

    if not points:
        return EpisodeEvaluation(
            episode_id=definition.episode_id,
            status=EpisodeStatus.PENDING_DATA,
            missing_features=tuple(sorted(definition.required_features)),
            peak_stress=None,
            state_peaks={},
            first_trigger_at=None,
            lead_days=None,
            reasons=("no timeline points in evaluation window",),
        )

    available = frozenset().union(*(point.available_features for point in points))
    missing = tuple(sorted(definition.required_features - available))
    if missing:
        return EpisodeEvaluation(
            episode_id=definition.episode_id,
            status=EpisodeStatus.PENDING_DATA,
            missing_features=missing,
            peak_stress=max(point.stress_level for point in points),
            state_peaks=_state_peaks(points),
            first_trigger_at=None,
            lead_days=None,
            reasons=("required point-in-time features are missing",),
        )

    peak_stress = max(point.stress_level for point in points)
    state_peaks = _state_peaks(points)

    reasons: list[str] = []
    if (
        definition.min_peak_stress is not None
        and peak_stress < definition.min_peak_stress
    ):
        reasons.append(
            f"peak stress {peak_stress.name} below required "
            f"{definition.min_peak_stress.name}"
        )

    for state, threshold in (definition.expected_state_peaks or {}).items():
        actual = state_peaks.get(state)
        if actual is None or actual < threshold:
            reasons.append(
                f"{state} peak {actual if actual is not None else 'missing'} "
                f"below required {threshold:.2f}"
            )

    trigger = next((point for point in points if _qualifies(point, definition)), None)
    lead_days = None
    if trigger is not None:
        lead_days = (definition.event_start - trigger.as_of).total_seconds() / 86400.0

    status = EpisodeStatus.PASS if not reasons else EpisodeStatus.FAIL
    return EpisodeEvaluation(
        episode_id=definition.episode_id,
        status=status,
        missing_features=(),
        peak_stress=peak_stress,
        state_peaks=state_peaks,
        first_trigger_at=trigger.as_of if trigger is not None else None,
        lead_days=lead_days,
        reasons=tuple(reasons),
    )


def _state_peaks(points: list[EpisodePoint]) -> dict[str, float]:
    keys = sorted({key for point in points for key in point.states})
    return {
        key: max(point.states[key] for point in points if key in point.states)
        for key in keys
    }


def evaluate_catalog(
    definitions: list[EpisodeDefinition],
    timeline: list[EpisodePoint],
) -> list[EpisodeEvaluation]:
    return [evaluate_episode(definition, timeline) for definition in definitions]
