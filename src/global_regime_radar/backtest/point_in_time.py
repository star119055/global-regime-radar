from datetime import datetime
from typing import Iterable

from global_regime_radar.data.contracts import Observation


def available_observations(
    observations: Iterable[Observation], decision_time: datetime
) -> list[Observation]:
    return [obs for obs in observations if obs.available_at <= decision_time]
