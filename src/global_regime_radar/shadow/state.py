from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from global_regime_radar.filtering.ukf import UKFState
from global_regime_radar.regime.dynamics import DynamicState

STATES = ("A", "B", "C1", "C2", "C3", "D")


@dataclass(frozen=True)
class ShadowPriorState:
    prior_time: datetime
    dynamic: dict[str, DynamicState]
    ukf: UKFState

    def __post_init__(self) -> None:
        if self.prior_time.tzinfo is None or self.prior_time.utcoffset() is None:
            raise ValueError("prior_time must be timezone-aware")
        if set(self.dynamic) != set(STATES):
            raise ValueError("dynamic state must contain exactly A/B/C1/C2/C3/D")
        if self.ukf.as_of != self.prior_time:
            raise ValueError("UKF as_of must equal prior_time")


def prior_payload(state: ShadowPriorState) -> dict[str, object]:
    return {
        "schema_version": 1,
        "prior_time": state.prior_time.isoformat(),
        "dynamic": {
            key: {
                "state": state.dynamic[key].state,
                "value": state.dynamic[key].value,
                "variance": state.dynamic[key].variance,
            }
            for key in STATES
        },
        "ukf": {
            "as_of": state.ukf.as_of.isoformat(),
            "mean": state.ukf.mean.tolist(),
            "covariance": state.ukf.covariance.tolist(),
        },
    }


def write_prior_state(state: ShadowPriorState, path: Path) -> None:
    path.write_text(
        json.dumps(
            prior_payload(state),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )


def load_prior_state(path: Path) -> ShadowPriorState:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported shadow prior schema_version")

    prior_time = datetime.fromisoformat(payload["prior_time"])
    dynamic = {
        key: DynamicState(
            state=payload["dynamic"][key]["state"],
            value=float(payload["dynamic"][key]["value"]),
            variance=float(payload["dynamic"][key]["variance"]),
        )
        for key in STATES
    }
    ukf_payload = payload["ukf"]
    ukf = UKFState(
        mean=np.asarray(ukf_payload["mean"], dtype=float),
        covariance=np.asarray(ukf_payload["covariance"], dtype=float),
        as_of=datetime.fromisoformat(ukf_payload["as_of"]),
    )
    return ShadowPriorState(
        prior_time=prior_time,
        dynamic=dynamic,
        ukf=ukf,
    )
