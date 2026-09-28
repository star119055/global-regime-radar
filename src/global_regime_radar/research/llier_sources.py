from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LLIERSourceClass(str, Enum):
    AUTHORITATIVE_COHORT_CAPABLE = "AUTHORITATIVE_COHORT_CAPABLE"
    AGGREGATE_CONTEXT_ONLY = "AGGREGATE_CONTEXT_ONLY"
    PROCESS_METADATA_ONLY = "PROCESS_METADATA_ONLY"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class LLIERSourceCapability:
    source_id: str
    stable_project_id: bool
    project_mw: bool
    repeatable_status_history: bool
    explicit_exit_events: bool
    process_regime_metadata: bool
    machine_readable: bool
    aggregate_status_only: bool = False
    available: bool = True

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ValueError("source_id cannot be empty")


def classify_llier_source(source: LLIERSourceCapability) -> LLIERSourceClass:
    if not source.available:
        return LLIERSourceClass.UNAVAILABLE

    authoritative = all(
        (
            source.stable_project_id,
            source.project_mw,
            source.repeatable_status_history,
            source.explicit_exit_events,
        )
    )
    if authoritative and not source.aggregate_status_only:
        return LLIERSourceClass.AUTHORITATIVE_COHORT_CAPABLE

    if source.aggregate_status_only:
        return LLIERSourceClass.AGGREGATE_CONTEXT_ONLY

    if (
        source.process_regime_metadata
        and not source.stable_project_id
        and not source.project_mw
        and not source.repeatable_status_history
    ):
        return LLIERSourceClass.PROCESS_METADATA_ONLY

    return LLIERSourceClass.UNAVAILABLE


def source_gate_summary(
    sources: list[LLIERSourceCapability],
) -> dict[str, object]:
    classifications = {
        source.source_id: classify_llier_source(source).value
        for source in sources
    }
    authoritative = sorted(
        source_id
        for source_id, classification in classifications.items()
        if classification == LLIERSourceClass.AUTHORITATIVE_COHORT_CAPABLE.value
    )
    return {
        "classifications": classifications,
        "authoritative_sources": authoritative,
        "authoritative_source_available": bool(authoritative),
        "A_coverage_increment": 0.0 if not authoritative else None,
    }
