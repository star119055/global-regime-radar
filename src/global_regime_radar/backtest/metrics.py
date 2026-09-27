from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import pairwise
from statistics import median


@dataclass(frozen=True)
class WarningPoint:
    as_of: datetime
    active: bool


@dataclass(frozen=True)
class WarningEpisode:
    start: datetime
    end: datetime


@dataclass(frozen=True)
class BacktestMetrics:
    episode_recall: float
    false_alarm_episodes: int
    false_negative_events: int
    median_lead_days: float | None
    time_in_warning: float
    state_transition_count: int
    mean_warning_dwell_days: float


def warning_episodes(points: list[WarningPoint]) -> list[WarningEpisode]:
    if not points:
        return []

    ordered = sorted(points, key=lambda point: point.as_of)
    episodes: list[WarningEpisode] = []
    start: datetime | None = None
    previous: datetime | None = None

    for point in ordered:
        if point.active and start is None:
            start = point.as_of
        elif not point.active and start is not None:
            assert previous is not None
            episodes.append(WarningEpisode(start=start, end=previous))
            start = None
        previous = point.as_of

    if start is not None:
        assert previous is not None
        episodes.append(WarningEpisode(start=start, end=previous))

    return episodes


def evaluate_binary_warning(
    points: list[WarningPoint],
    event_times: list[datetime],
    lead_window_days: int = 30,
) -> BacktestMetrics:
    if lead_window_days < 0:
        raise ValueError("lead_window_days must be non-negative")

    episodes = warning_episodes(points)
    ordered_points = sorted(points, key=lambda point: point.as_of)
    active_count = sum(point.active for point in ordered_points)
    time_in_warning = active_count / len(ordered_points) if ordered_points else 0.0

    transition_count = sum(
        current.active != prior.active
        for prior, current in pairwise(ordered_points)
    )

    event_hits = 0
    lead_days: list[float] = []
    for event in sorted(event_times):
        window_start = event - timedelta(days=lead_window_days)
        eligible = [
            point.as_of
            for point in ordered_points
            if point.active and window_start <= point.as_of <= event
        ]
        if eligible:
            event_hits += 1
            first_warning = min(eligible)
            lead_days.append((event - first_warning).total_seconds() / 86400.0)

    false_negative_events = len(event_times) - event_hits
    episode_recall = event_hits / len(event_times) if event_times else 1.0

    false_alarm_episodes = 0
    for episode in episodes:
        horizon_end = episode.end + timedelta(days=lead_window_days)
        if not any(episode.start <= event <= horizon_end for event in event_times):
            false_alarm_episodes += 1

    dwell_days = [
        (episode.end - episode.start).total_seconds() / 86400.0 + 1.0
        for episode in episodes
    ]

    return BacktestMetrics(
        episode_recall=episode_recall,
        false_alarm_episodes=false_alarm_episodes,
        false_negative_events=false_negative_events,
        median_lead_days=median(lead_days) if lead_days else None,
        time_in_warning=time_in_warning,
        state_transition_count=transition_count,
        mean_warning_dwell_days=(
            sum(dwell_days) / len(dwell_days) if dwell_days else 0.0
        ),
    )


def monotonicity_score(
    state_and_future_stress: list[tuple[float, float]],
) -> float:
    comparable = 0
    consistent = 0

    for index, (state_i, future_i) in enumerate(state_and_future_stress):
        for state_j, future_j in state_and_future_stress[index + 1 :]:
            if state_i == state_j or future_i == future_j:
                continue
            comparable += 1
            if (state_i < state_j) == (future_i < future_j):
                consistent += 1

    return consistent / comparable if comparable else 1.0
