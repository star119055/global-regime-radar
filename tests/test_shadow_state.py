from datetime import UTC, datetime

import numpy as np

from global_regime_radar.filtering.ukf import initialize_filter
from global_regime_radar.regime.dynamics import DynamicState
from global_regime_radar.shadow.state import (
    ShadowPriorState,
    load_prior_state,
    write_prior_state,
)

STATES = ("A", "B", "C1", "C2", "C3", "D")


def test_shadow_prior_state_round_trip(tmp_path):
    as_of = datetime(2026, 9, 27, 0, 30, tzinfo=UTC)
    dynamic = {
        state: DynamicState(state, 0.4 + index * 0.05, 0.01 + index * 0.001)
        for index, state in enumerate(STATES)
    }
    ukf = initialize_filter(
        {state: dynamic[state].value for state in STATES},
        {state: dynamic[state].variance for state in STATES},
        as_of=as_of,
    )
    original = ShadowPriorState(as_of, dynamic, ukf)
    path = tmp_path / "state.json"

    write_prior_state(original, path)
    loaded = load_prior_state(path)

    assert loaded.prior_time == original.prior_time
    assert loaded.dynamic == original.dynamic
    assert np.allclose(loaded.ukf.mean, original.ukf.mean)
    assert np.allclose(loaded.ukf.covariance, original.ukf.covariance)


def test_shadow_prior_rejects_incomplete_dynamic_state():
    as_of = datetime(2026, 9, 27, 0, 30, tzinfo=UTC)
    ukf = initialize_filter(
        {state: 0.5 for state in STATES},
        {state: 0.01 for state in STATES},
        as_of=as_of,
    )

    try:
        ShadowPriorState(
            as_of,
            {"A": DynamicState("A", 0.5, 0.01)},
            ukf,
        )
    except ValueError as exc:
        assert "exactly A/B/C1/C2/C3/D" in str(exc)
    else:
        raise AssertionError("incomplete dynamic state must fail")
