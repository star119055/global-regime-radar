from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ModuleFeatureGate:
    feature_id: str
    earliest_valid_at: datetime
    allowed_universes: frozenset[str]

    def __post_init__(self) -> None:
        if (
            self.earliest_valid_at.tzinfo is None
            or self.earliest_valid_at.utcoffset() is None
        ):
            raise ValueError("earliest_valid_at must be timezone-aware")

    def allowed(self, universe: str, decision_time: datetime) -> bool:
        if decision_time.tzinfo is None or decision_time.utcoffset() is None:
            raise ValueError("decision_time must be timezone-aware")
        return (
            universe in self.allowed_universes
            and decision_time >= self.earliest_valid_at
        )


def require_feature_availability(
    feature_ids: set[str],
    gates: dict[str, ModuleFeatureGate],
    universe: str,
    decision_time: datetime,
) -> None:
    for feature_id in sorted(feature_ids):
        gate = gates.get(feature_id)
        if gate is None:
            raise ValueError(f"missing feature gate: {feature_id}")
        if not gate.allowed(universe, decision_time):
            raise ValueError(
                f"feature not valid for {universe} at {decision_time.isoformat()}: "
                f"{feature_id}"
            )
