from datetime import UTC, datetime

from global_regime_radar.backtest.episodes import (
    EpisodeDefinition,
    EpisodePoint,
    EpisodeStatus,
    evaluate_episode,
)
from global_regime_radar.stress.engine import StressLevel


def dt(day: int) -> datetime:
    return datetime(2020, 3, day, tzinfo=UTC)


def definition() -> EpisodeDefinition:
    return EpisodeDefinition(
        episode_id="treasury_2020_03",
        name="March 2020 Treasury-market dysfunction",
        event_start=dt(9),
        event_end=dt(23),
        lead_window_days=5,
        required_features=frozenset({"depth", "funding", "dealer"}),
        min_peak_stress=StressLevel.L3,
        expected_state_peaks={"B": 0.75},
    )


def point(
    day: int,
    stress: StressLevel,
    b_value: float,
    features: frozenset[str] | None = None,
) -> EpisodePoint:
    return EpisodePoint(
        as_of=dt(day),
        stress_level=stress,
        states={"B": b_value},
        available_features=features or frozenset({"depth", "funding", "dealer"}),
    )


def test_episode_pass_records_lead_time():
    result = evaluate_episode(
        definition(),
        [
            point(5, StressLevel.L2, 0.60),
            point(7, StressLevel.L3, 0.80),
            point(12, StressLevel.L4, 0.90),
        ],
    )
    assert result.status is EpisodeStatus.PASS
    assert result.peak_stress is StressLevel.L4
    assert result.state_peaks["B"] == 0.90
    assert result.first_trigger_at == dt(7)
    assert result.lead_days == 2.0


def test_missing_required_feature_is_pending_not_fail():
    result = evaluate_episode(
        definition(),
        [
            point(
                10,
                StressLevel.L4,
                0.90,
                frozenset({"depth", "funding"}),
            )
        ],
    )
    assert result.status is EpisodeStatus.PENDING_DATA
    assert result.missing_features == ("dealer",)


def test_complete_data_but_weak_response_fails():
    result = evaluate_episode(
        definition(),
        [
            point(8, StressLevel.L2, 0.55),
            point(12, StressLevel.L2, 0.65),
        ],
    )
    assert result.status is EpisodeStatus.FAIL
    assert any("peak stress" in reason for reason in result.reasons)
    assert any("B peak" in reason for reason in result.reasons)


def test_no_points_is_pending():
    result = evaluate_episode(definition(), [])
    assert result.status is EpisodeStatus.PENDING_DATA
    assert result.peak_stress is None


def test_points_outside_episode_window_do_not_count():
    result = evaluate_episode(
        definition(),
        [point(3, StressLevel.L4, 0.95)],
    )
    assert result.status is EpisodeStatus.PENDING_DATA


def test_thresholds_are_contract_not_probability():
    result = evaluate_episode(
        definition(),
        [
            point(9, StressLevel.L3, 0.75),
        ],
    )
    assert result.status is EpisodeStatus.PASS
    assert result.state_peaks["B"] == 0.75
