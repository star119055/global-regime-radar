from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from global_regime_radar.filtering.ukf import (
    RegimeMeasurement,
    initialize_filter,
    predict,
    step,
    summarize,
    update,
)
from global_regime_radar.regime.dynamics import Coupling, Jump


HALF_LIFE = {
    "A": 120.0,
    "B": 7.0,
    "C1": 60.0,
    "C2": 90.0,
    "C3": 180.0,
    "D": 270.0,
}
ZERO_Q = {state: 0.0 for state in HALF_LIFE}


def dt(day: int = 1) -> datetime:
    return datetime(2026, 9, day, tzinfo=UTC)


def initial(variance: float = 0.01):
    return initialize_filter(
        {state: 0.5 for state in HALF_LIFE},
        {state: variance for state in HALF_LIFE},
        as_of=dt(),
    )


def test_no_measurement_preserves_mean_and_grows_covariance():
    state = initial()
    q = {state: 0.001 for state in HALF_LIFE}
    predicted = predict(
        state,
        as_of=dt() + timedelta(days=1),
        half_life_days=HALF_LIFE,
        process_variance_per_day=q,
    )
    assert np.allclose(predicted.mean, state.mean, atol=1e-10)
    assert np.all(np.diag(predicted.covariance) > np.diag(state.covariance))


def test_high_confidence_measurement_moves_more_than_low_confidence():
    state = initial()
    high = update(
        state,
        [RegimeMeasurement("B", 0.9, variance=0.001)],
    )
    low = update(
        state,
        [RegimeMeasurement("B", 0.9, variance=0.5)],
    )
    high_b = summarize(high)["B"].value
    low_b = summarize(low)["B"].value
    assert high_b > low_b


def test_partial_measurement_does_not_zero_fill_other_states():
    state = initial()
    posterior = update(
        state,
        [RegimeMeasurement("B", 0.8, variance=0.01)],
    )
    summary = summarize(posterior)
    assert summary["B"].value > 0.5
    assert summary["C3"].value == pytest.approx(0.5, abs=1e-6)


def test_fast_state_process_variance_allows_faster_adaptation():
    state = initial(variance=0.001)
    q = {key: 0.0001 for key in HALF_LIFE}
    q["B"] = 0.1
    predicted = predict(
        state,
        as_of=dt() + timedelta(days=1),
        half_life_days=HALF_LIFE,
        process_variance_per_day=q,
    )
    posterior = update(
        predicted,
        [
            RegimeMeasurement("A", 0.8, variance=0.02),
            RegimeMeasurement("B", 0.8, variance=0.02),
        ],
    )
    summary = summarize(posterior)
    assert summary["B"].value > summary["A"].value


def test_jump_applies_immediately():
    state = initial(variance=1e-6)
    predicted = predict(
        state,
        as_of=dt() + timedelta(days=1),
        half_life_days=HALF_LIFE,
        process_variance_per_day=ZERO_Q,
        jumps=[Jump("D", 0.15, "policy")],
    )
    assert summarize(predicted)["D"].value > 0.64


def test_sparse_coupling_changes_target_direction():
    state = initialize_filter(
        {
            "A": 0.5,
            "B": 0.5,
            "C1": 0.5,
            "C2": 0.5,
            "C3": 0.9,
            "D": 0.5,
        },
        {key: 1e-5 for key in HALF_LIFE},
        as_of=dt(),
    )
    predicted = predict(
        state,
        as_of=dt() + timedelta(days=30),
        half_life_days=HALF_LIFE,
        process_variance_per_day=ZERO_Q,
        couplings=[Coupling("C3", "A", -0.2)],
    )
    assert summarize(predicted)["A"].value < 0.5


def test_step_is_deterministic_and_bounded():
    state = initial()
    q = {key: 0.001 for key in HALF_LIFE}
    measurements = [RegimeMeasurement("B", 0.75, variance=0.02)]
    first = step(
        state,
        measurements,
        as_of=dt() + timedelta(days=1),
        half_life_days=HALF_LIFE,
        process_variance_per_day=q,
    )
    second = step(
        state,
        measurements,
        as_of=dt() + timedelta(days=1),
        half_life_days=HALF_LIFE,
        process_variance_per_day=q,
    )
    assert np.allclose(first.mean, second.mean)
    assert np.allclose(first.covariance, second.covariance)
    summary = summarize(first)
    assert all(0.0 <= item.value <= 1.0 for item in summary.values())


def test_covariance_is_symmetric_positive_semidefinite():
    posterior = update(
        initial(),
        [
            RegimeMeasurement("A", 0.7, variance=0.01),
            RegimeMeasurement("B", 0.8, variance=0.02),
        ],
    )
    assert np.allclose(posterior.covariance, posterior.covariance.T)
    assert np.min(np.linalg.eigvalsh(posterior.covariance)) >= -1e-10
