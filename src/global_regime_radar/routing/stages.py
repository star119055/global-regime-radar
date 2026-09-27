from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum


class EvidenceStage(IntEnum):
    EXPECTED = 1
    CONFIRMED = 2
    MACRO_TRANSMITTED = 3


@dataclass(frozen=True)
class StageTransition:
    as_of: datetime
    from_stage: EvidenceStage
    to_stage: EvidenceStage
    evidence_id: str


class StageTracker:
    def __init__(self, initial_stage: EvidenceStage = EvidenceStage.EXPECTED) -> None:
        self._stage = initial_stage
        self._history: list[StageTransition] = []

    @property
    def stage(self) -> EvidenceStage:
        return self._stage

    @property
    def history(self) -> tuple[StageTransition, ...]:
        return tuple(self._history)

    def advance(
        self,
        as_of: datetime,
        to_stage: EvidenceStage,
        evidence_id: str,
    ) -> StageTransition | None:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        if to_stage < self._stage:
            raise ValueError("evidence stage cannot move backward")
        if to_stage == self._stage:
            return None

        transition = StageTransition(
            as_of=as_of,
            from_stage=self._stage,
            to_stage=to_stage,
            evidence_id=evidence_id,
        )
        self._stage = to_stage
        self._history.append(transition)
        return transition
