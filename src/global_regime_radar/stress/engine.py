from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum


class StressLevel(IntEnum):
    L1 = 1
    L2 = 2
    L3 = 3
    L4 = 4

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class StressConfig:
    pressure_threshold: float = 0.5
    impairment_threshold: float = 0.7
    upgrade_confirmation_days: int = 2
    downgrade_confirmation_days: int = 5

    def __post_init__(self) -> None:
        if not 0.0 <= self.pressure_threshold <= 1.0:
            raise ValueError("pressure_threshold must be in [0, 1]")
        if not 0.0 <= self.impairment_threshold <= 1.0:
            raise ValueError("impairment_threshold must be in [0, 1]")
        if self.pressure_threshold > self.impairment_threshold:
            raise ValueError("pressure_threshold must be <= impairment_threshold")
        if self.upgrade_confirmation_days < 1:
            raise ValueError("upgrade_confirmation_days must be >= 1")
        if self.downgrade_confirmation_days < 1:
            raise ValueError("downgrade_confirmation_days must be >= 1")


@dataclass(frozen=True)
class StressInputs:
    funding: float
    price_discovery: float
    intermediation: float
    controller_intervention: bool = False
    forced_deleveraging: bool = False

    def __post_init__(self) -> None:
        for field_name in ("funding", "price_discovery", "intermediation"):
            value = getattr(self, field_name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field_name} must be in [0, 1]")

    @property
    def market_functions(self) -> tuple[float, float, float]:
        return self.funding, self.price_discovery, self.intermediation


@dataclass(frozen=True)
class StressAssessment:
    as_of: datetime
    inputs: StressInputs
    raw_level: StressLevel
    confirmed_level: StressLevel
    candidate_level: StressLevel | None
    confirmation_count: int


@dataclass(frozen=True)
class StressTransition:
    as_of: datetime
    from_level: StressLevel
    to_level: StressLevel
    confirmation_count: int


def classify_stress(
    inputs: StressInputs,
    config: StressConfig | None = None,
) -> StressLevel:
    config = config or StressConfig()
    values = inputs.market_functions

    impaired = sum(value >= config.impairment_threshold for value in values)
    pressured = sum(value >= config.pressure_threshold for value in values)

    base_level = StressLevel.L1
    if impaired >= 2:
        base_level = StressLevel.L3
    elif pressured >= 1:
        base_level = StressLevel.L2

    if (
        base_level >= StressLevel.L3
        and inputs.controller_intervention
        and inputs.forced_deleveraging
    ):
        return StressLevel.L4

    return base_level


class StressEngine:
    def __init__(
        self,
        config: StressConfig | None = None,
        initial_level: StressLevel = StressLevel.L1,
    ) -> None:
        self.config = config or StressConfig()
        self._level = initial_level
        self._candidate: StressLevel | None = None
        self._confirmation_count = 0
        self._last_as_of: datetime | None = None
        self._transitions: list[StressTransition] = []

    @property
    def level(self) -> StressLevel:
        return self._level

    @property
    def transitions(self) -> tuple[StressTransition, ...]:
        return tuple(self._transitions)

    def _required_confirmation(self, candidate: StressLevel) -> int:
        if candidate > self._level:
            return self.config.upgrade_confirmation_days
        return self.config.downgrade_confirmation_days

    def update(self, as_of: datetime, inputs: StressInputs) -> StressAssessment:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        if self._last_as_of is not None and as_of <= self._last_as_of:
            raise ValueError("as_of must increase strictly between updates")
        self._last_as_of = as_of

        raw_level = classify_stress(inputs, self.config)

        if raw_level == self._level:
            self._candidate = None
            self._confirmation_count = 0
        else:
            if raw_level != self._candidate:
                self._candidate = raw_level
                self._confirmation_count = 1
            else:
                self._confirmation_count += 1

            required = self._required_confirmation(raw_level)
            if self._confirmation_count >= required:
                prior = self._level
                confirmed_count = self._confirmation_count
                self._level = raw_level
                self._transitions.append(
                    StressTransition(
                        as_of=as_of,
                        from_level=prior,
                        to_level=self._level,
                        confirmation_count=confirmed_count,
                    )
                )
                self._candidate = None
                self._confirmation_count = 0

        return StressAssessment(
            as_of=as_of,
            inputs=inputs,
            raw_level=raw_level,
            confirmed_level=self._level,
            candidate_level=self._candidate,
            confirmation_count=self._confirmation_count,
        )
