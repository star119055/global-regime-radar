import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from global_regime_radar.backtest.point_in_time import point_in_time_snapshot
from global_regime_radar.data.contracts import DataVintage, Observation


@dataclass(frozen=True)
class SensitivityScenario:
    parameter: str
    pct_delta: int
    value: float


def sensitivity_scenarios(
    parameters: dict[str, float],
    deltas: tuple[int, ...] = (10, 20),
) -> list[SensitivityScenario]:
    scenarios: list[SensitivityScenario] = []
    for parameter in sorted(parameters):
        base = parameters[parameter]
        for pct in deltas:
            if pct <= 0:
                raise ValueError("sensitivity deltas must be positive")
            for signed_pct in (-pct, pct):
                scenarios.append(
                    SensitivityScenario(
                        parameter=parameter,
                        pct_delta=signed_pct,
                        value=base * (1.0 + signed_pct / 100.0),
                    )
                )
    return scenarios


def point_in_time_snapshot_with_lags(
    observations: Iterable[Observation],
    vintages: Iterable[DataVintage],
    decision_time: datetime,
    lag_by_feature: dict[str, timedelta],
) -> list[Observation]:
    eligible = [
        obs
        for obs in observations
        if obs.available_at + lag_by_feature.get(obs.feature_id, timedelta())
        <= decision_time
    ]
    return point_in_time_snapshot(eligible, vintages, decision_time)


def deterministic_missing_mask(
    observations: Iterable[Observation],
    pct: float,
    seed: str,
) -> list[Observation]:
    if not 0 <= pct <= 100:
        raise ValueError("pct must be in [0, 100]")

    values = list(observations)
    mask_count = round(len(values) * pct / 100.0)
    ranked = sorted(
        values,
        key=lambda obs: hashlib.sha256(
            f"{seed}|{obs.observation_id}".encode()
        ).hexdigest(),
    )
    masked_ids = {obs.observation_id for obs in ranked[:mask_count]}

    result: list[Observation] = []
    for obs in values:
        if obs.observation_id not in masked_ids:
            result.append(obs)
            continue

        flag = "stress:masked"
        if obs.quality_flag:
            flag = f"{obs.quality_flag};{flag}"
        result.append(obs.model_copy(update={"value": None, "quality_flag": flag}))

    return result
