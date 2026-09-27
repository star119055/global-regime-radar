from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from global_regime_radar.backtest.point_in_time import point_in_time_snapshot
from global_regime_radar.data.contracts import (
    DataVintage,
    FeatureDependency,
    Observation,
)
from global_regime_radar.data.dependencies import validate_no_duplicate_state_contribution
from global_regime_radar.data.hashing import dataset_snapshot_hash, make_vintage_id, sha256_bytes


def dt(day: int) -> datetime:
    return datetime(2020, 1, day, tzinfo=UTC)


def vintage(source_hash: str, revision: int, day: int) -> DataVintage:
    return DataVintage(
        vintage_id=make_vintage_id("treasury", source_hash, revision),
        source_id="treasury",
        retrieved_at=dt(day),
        source_hash=source_hash,
        revision_number=revision,
    )


def observation(
    *,
    observation_id: str,
    value: float | None,
    available_day: int,
    vintage_id: str,
    ingested_day: int = 10,
) -> Observation:
    return Observation(
        observation_id=observation_id,
        feature_id="auction_tail",
        source_id="treasury",
        entity_id="30Y",
        value=value,
        observation_start=dt(1),
        observation_end=dt(1),
        published_at=dt(available_day),
        available_at=dt(available_day),
        ingested_at=dt(ingested_day),
        vintage_id=vintage_id,
    )


def test_future_revision_does_not_leak_backward():
    h1 = sha256_bytes(b"release-1")
    h2 = sha256_bytes(b"release-2")
    v1 = vintage(h1, 0, 2)
    v2 = vintage(h2, 1, 5)

    original = observation(
        observation_id="o1",
        value=1.2,
        available_day=2,
        vintage_id=v1.vintage_id,
    )
    revised = observation(
        observation_id="o2",
        value=0.8,
        available_day=5,
        vintage_id=v2.vintage_id,
    )

    before_revision = point_in_time_snapshot([revised, original], [v2, v1], dt(3))
    after_revision = point_in_time_snapshot([revised, original], [v2, v1], dt(6))

    assert [x.value for x in before_revision] == [1.2]
    assert [x.value for x in after_revision] == [0.8]


def test_ingestion_time_is_audit_metadata_not_historical_gate():
    h1 = sha256_bytes(b"release-1")
    v1 = vintage(h1, 0, 10)
    backfilled = observation(
        observation_id="o1",
        value=1.2,
        available_day=2,
        ingested_day=10,
        vintage_id=v1.vintage_id,
    )

    snapshot = point_in_time_snapshot([backfilled], [v1], dt(3))
    assert snapshot[0].value == 1.2


def test_missing_remains_missing():
    h1 = sha256_bytes(b"release-1")
    v1 = vintage(h1, 0, 2)
    obs = observation(
        observation_id="o1",
        value=None,
        available_day=2,
        vintage_id=v1.vintage_id,
    )

    assert obs.is_missing
    assert point_in_time_snapshot([obs], [v1], dt(3))[0].value is None


def test_dataset_hash_is_order_independent_and_revision_sensitive():
    h1 = sha256_bytes(b"release-1")
    h2 = sha256_bytes(b"release-2")
    v1 = vintage(h1, 0, 2)
    v2 = vintage(h2, 1, 5)
    o1 = observation(
        observation_id="o1",
        value=1.2,
        available_day=2,
        vintage_id=v1.vintage_id,
    )
    o2 = observation(
        observation_id="o2",
        value=0.8,
        available_day=5,
        vintage_id=v2.vintage_id,
    )

    hash_a = dataset_snapshot_hash([o1, o2], [v1, v2])
    hash_b = dataset_snapshot_hash([o2, o1], [v2, v1])
    hash_old_only = dataset_snapshot_hash([o1], [v1])

    assert hash_a == hash_b
    assert hash_a != hash_old_only


def test_dataset_hash_requires_vintage_metadata():
    h1 = sha256_bytes(b"release-1")
    v1 = vintage(h1, 0, 2)
    obs = observation(
        observation_id="o1",
        value=1.2,
        available_day=2,
        vintage_id=v1.vintage_id,
    )

    with pytest.raises(ValueError, match="missing vintage metadata"):
        dataset_snapshot_hash([obs], [])


def test_duplicate_contribution_to_same_state_is_rejected():
    dependencies = [
        FeatureDependency(
            parent_feature_id="transformer_lead_time",
            child_indicator_id=8,
            target_state="C3",
            attribution_group="grid_equipment",
        ),
        FeatureDependency(
            parent_feature_id="transformer_lead_time",
            child_indicator_id=15,
            target_state="C3",
            attribution_group="hydro_gas",
        ),
    ]

    with pytest.raises(ValueError, match="multiple indicators"):
        validate_no_duplicate_state_contribution(dependencies)


def test_same_raw_feature_can_feed_different_states():
    dependencies = [
        FeatureDependency(
            parent_feature_id="hydro_output",
            child_indicator_id=15,
            target_state="C1",
            attribution_group="energy",
        ),
        FeatureDependency(
            parent_feature_id="hydro_output",
            child_indicator_id=15,
            target_state="C3",
            attribution_group="physical_delivery",
        ),
    ]

    validate_no_duplicate_state_contribution(dependencies)


def test_naive_timestamp_is_rejected():
    h1 = sha256_bytes(b"release-1")
    naive_timestamp = dt(2).replace(tzinfo=None)

    with pytest.raises(ValidationError, match="timezone-aware"):
        Observation(
            observation_id="o1",
            feature_id="auction_tail",
            source_id="treasury",
            value=1.0,
            available_at=naive_timestamp,
            ingested_at=dt(3),
            vintage_id=make_vintage_id("treasury", h1, 0),
        )


def test_temporal_order_is_rejected():
    h1 = sha256_bytes(b"release-1")

    with pytest.raises(ValidationError, match="available_at must be >= published_at"):
        Observation(
            observation_id="o1",
            feature_id="auction_tail",
            source_id="treasury",
            value=1.0,
            published_at=dt(3),
            available_at=dt(2),
            ingested_at=dt(4),
            vintage_id=make_vintage_id("treasury", h1, 0),
        )
