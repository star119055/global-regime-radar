from collections.abc import Iterable
from datetime import datetime

from global_regime_radar.data.contracts import DataVintage, Observation


def available_observations(
    observations: Iterable[Observation],
    decision_time: datetime,
) -> list[Observation]:
    return [obs for obs in observations if obs.is_available(decision_time)]


def point_in_time_snapshot(
    observations: Iterable[Observation],
    vintages: Iterable[DataVintage],
    decision_time: datetime,
) -> list[Observation]:
    vintage_map = {v.vintage_id: v for v in vintages}
    latest: dict[
        tuple[str, str | None, datetime | None, datetime | None],
        tuple[tuple[datetime, int, str], Observation],
    ] = {}

    for obs in available_observations(observations, decision_time):
        vintage = vintage_map.get(obs.vintage_id)
        if vintage is None:
            raise ValueError(f"missing vintage metadata for {obs.vintage_id}")

        rank = (obs.available_at, vintage.revision_number, obs.vintage_id)
        prior = latest.get(obs.natural_key)
        if prior is None or rank > prior[0]:
            latest[obs.natural_key] = (rank, obs)

    return sorted(
        (item[1] for item in latest.values()),
        key=lambda obs: (
            obs.feature_id,
            obs.entity_id or "",
            obs.observation_start or datetime.min.replace(tzinfo=decision_time.tzinfo),
            obs.observation_end or datetime.min.replace(tzinfo=decision_time.tzinfo),
        ),
    )
