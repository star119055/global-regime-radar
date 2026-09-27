from dataclasses import dataclass
from datetime import datetime


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


@dataclass(frozen=True)
class BacktestFold:
    fold_id: str
    universe: str
    train_end: datetime
    test_start: datetime
    test_end: datetime
    train_start: datetime | None = None

    def __post_init__(self) -> None:
        _require_aware(self.train_end, "train_end")
        _require_aware(self.test_start, "test_start")
        _require_aware(self.test_end, "test_end")
        if self.train_start is not None:
            _require_aware(self.train_start, "train_start")
            if self.train_start >= self.train_end:
                raise ValueError("train_start must be before train_end")
        if self.train_end >= self.test_start:
            raise ValueError("train_end must be before test_start")
        if self.test_start > self.test_end:
            raise ValueError("test_start must be <= test_end")


@dataclass(frozen=True)
class FeatureAvailability:
    feature_id: str
    earliest_valid_at: datetime
    universes: frozenset[str]

    def __post_init__(self) -> None:
        _require_aware(self.earliest_valid_at, "earliest_valid_at")

    def allowed(self, universe: str, decision_time: datetime) -> bool:
        _require_aware(decision_time, "decision_time")
        return universe in self.universes and decision_time >= self.earliest_valid_at


def validate_fold_sequence(folds: list[BacktestFold]) -> None:
    seen_ids: set[str] = set()
    for fold in folds:
        if fold.fold_id in seen_ids:
            raise ValueError(f"duplicate fold_id: {fold.fold_id}")
        seen_ids.add(fold.fold_id)

    ordered = sorted(folds, key=lambda fold: fold.test_start)
    for prior, current in zip(ordered, ordered[1:], strict=False):
        if current.test_start <= prior.test_end:
            raise ValueError(
                f"test windows overlap: {prior.fold_id} and {current.fold_id}"
            )
