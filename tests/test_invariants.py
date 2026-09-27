from datetime import UTC, datetime

from global_regime_radar.data.contracts import Observation
from global_regime_radar.signals.freshness import freshness, measurement_variance


def test_half_life_definition():
    assert abs(freshness(10, 10) - 0.5) < 1e-12


def test_stale_data_increases_uncertainty():
    fresh = measurement_variance(1.0, freshness_value=1.0, confidence=1.0)
    stale = measurement_variance(1.0, freshness_value=0.25, confidence=1.0)
    assert stale > fresh


def test_available_at_is_point_in_time_gate():
    obs = Observation(
        observation_id="o1",
        feature_id="auction_tail",
        source_id="treasury",
        value=1.0,
        available_at=datetime(2020, 1, 2, tzinfo=UTC),
        ingested_at=datetime(2020, 1, 2, tzinfo=UTC),
        vintage_id="v1",
    )
    assert not obs.is_available(datetime(2020, 1, 1, tzinfo=UTC))
    assert obs.is_available(datetime(2020, 1, 2, tzinfo=UTC))
