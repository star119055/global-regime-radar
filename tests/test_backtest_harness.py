from datetime import UTC, datetime, timedelta

import pytest

from global_regime_radar.backtest.folds import (
    BacktestFold,
    FeatureAvailability,
    validate_fold_sequence,
)
from global_regime_radar.backtest.manifest import build_manifest
from global_regime_radar.backtest.metrics import (
    WarningPoint,
    evaluate_binary_warning,
    monotonicity_score,
)
from global_regime_radar.backtest.robustness import (
    deterministic_missing_mask,
    point_in_time_snapshot_with_lags,
    sensitivity_scenarios,
)
from global_regime_radar.data.contracts import DataVintage, Observation


def dt(year: int, month: int = 1, day: int = 1) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


def fold() -> BacktestFold:
    return BacktestFold(
        fold_id="WF06",
        universe="core_3",
        train_end=dt(2019, 12, 31),
        test_start=dt(2020, 1, 1),
        test_end=dt(2020, 12, 31),
    )


def observation(observation_id: str, available_at: datetime, value: float) -> Observation:
    return Observation(
        observation_id=observation_id,
        feature_id="repo_stress",
        source_id="nyfed",
        value=value,
        available_at=available_at,
        ingested_at=max(available_at, dt(2026)),
        vintage_id="v1",
    )


def vintage() -> DataVintage:
    return DataVintage(
        vintage_id="v1",
        source_id="nyfed",
        retrieved_at=dt(2026),
        source_hash="abc",
        revision_number=0,
    )


def test_fold_rejects_train_test_overlap():
    with pytest.raises(ValueError, match="train_end must be before test_start"):
        BacktestFold(
            fold_id="bad",
            universe="core",
            train_end=dt(2020, 1, 2),
            test_start=dt(2020, 1, 1),
            test_end=dt(2020, 1, 3),
        )


def test_fold_sequence_rejects_overlapping_test_windows():
    first = fold()
    second = BacktestFold(
        fold_id="WF07",
        universe="core_3",
        train_end=dt(2020, 1, 1),
        test_start=dt(2020, 6, 1),
        test_end=dt(2021, 1, 1),
    )
    with pytest.raises(ValueError, match="test windows overlap"):
        validate_fold_sequence([first, second])


def test_feature_availability_blocks_pre_history_use():
    availability = FeatureAvailability(
        feature_id="geoi",
        earliest_valid_at=dt(2024),
        universes=frozenset({"new_module"}),
    )

    assert not availability.allowed("core_3", dt(2023))
    assert not availability.allowed("new_module", dt(2023))
    assert availability.allowed("new_module", dt(2024))


def test_manifest_is_order_independent_for_parameter_keys():
    first = build_manifest(
        model_version="v6.1",
        feature_set_version="core-v1",
        fold=fold(),
        dataset_hash="dataset",
        code_commit="abcdef",
        parameters={"b": 2, "a": 1},
    )
    second = build_manifest(
        model_version="v6.1",
        feature_set_version="core-v1",
        fold=fold(),
        dataset_hash="dataset",
        code_commit="abcdef",
        parameters={"a": 1, "b": 2},
    )

    assert first.parameters_hash == second.parameters_hash
    assert first.run_id == second.run_id


def test_manifest_changes_when_parameter_changes():
    first = build_manifest(
        model_version="v6.1",
        feature_set_version="core-v1",
        fold=fold(),
        dataset_hash="dataset",
        code_commit="abcdef",
        parameters={"threshold": 0.5},
    )
    second = build_manifest(
        model_version="v6.1",
        feature_set_version="core-v1",
        fold=fold(),
        dataset_hash="dataset",
        code_commit="abcdef",
        parameters={"threshold": 0.6},
    )

    assert first.parameters_hash != second.parameters_hash
    assert first.run_id != second.run_id


def test_manifest_requires_dataset_and_code_identity():
    with pytest.raises(ValueError, match="dataset_hash"):
        build_manifest(
            model_version="v6.1",
            feature_set_version="core-v1",
            fold=fold(),
            dataset_hash="",
            code_commit="abcdef",
            parameters={},
        )


def test_additional_publication_lag_never_accelerates_data():
    obs = observation("o1", dt(2020, 1, 2), 1.0)

    without_lag = point_in_time_snapshot_with_lags(
        [obs],
        [vintage()],
        dt(2020, 1, 3),
        {},
    )
    with_lag = point_in_time_snapshot_with_lags(
        [obs],
        [vintage()],
        dt(2020, 1, 3),
        {"repo_stress": timedelta(days=2)},
    )

    assert len(without_lag) == 1
    assert with_lag == []


def test_missing_mask_is_deterministic_and_preserves_rows():
    observations = [
        observation(f"o{index}", dt(2020, 1, 1), float(index))
        for index in range(10)
    ]

    first = deterministic_missing_mask(observations, 20, "seed")
    second = deterministic_missing_mask(observations, 20, "seed")

    assert [item.value for item in first] == [item.value for item in second]
    assert len(first) == 10
    assert sum(item.value is None for item in first) == 2
    assert all(
        item.value is not None or "stress:masked" in (item.quality_flag or "")
        for item in first
    )


def test_sensitivity_changes_one_parameter_at_a_time():
    scenarios = sensitivity_scenarios({"threshold": 0.5}, deltas=(10, 20))

    assert [scenario.pct_delta for scenario in scenarios] == [-10, 10, -20, 20]
    assert scenarios[0].value == pytest.approx(0.45)
    assert scenarios[-1].value == pytest.approx(0.60)


def test_warning_metrics_capture_recall_false_alarm_and_lead_time():
    points = [
        WarningPoint(dt(2020, 1, day), active)
        for day, active in [
            (1, False),
            (2, True),
            (3, True),
            (4, False),
            (5, True),
            (6, False),
        ]
    ]
    events = [dt(2020, 1, 4)]
    metrics = evaluate_binary_warning(points, events, lead_window_days=3)

    assert metrics.episode_recall == 1.0
    assert metrics.false_negative_events == 0
    assert metrics.false_alarm_episodes == 1
    assert metrics.median_lead_days == 2.0
    assert metrics.time_in_warning == 0.5
    assert metrics.state_transition_count == 4


def test_warning_metrics_count_false_negative():
    points = [WarningPoint(dt(2020, 1, 1), False)]
    metrics = evaluate_binary_warning(points, [dt(2020, 1, 2)], lead_window_days=1)

    assert metrics.episode_recall == 0.0
    assert metrics.false_negative_events == 1
    assert metrics.median_lead_days is None


def test_monotonicity_score_distinguishes_ordering():
    assert monotonicity_score([(0.1, 0.2), (0.5, 0.6), (0.9, 0.8)]) == 1.0
    assert monotonicity_score([(0.1, 0.8), (0.5, 0.6), (0.9, 0.2)]) == 0.0
