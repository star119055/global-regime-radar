from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from global_regime_radar.reporting.snapshot import (
    DailySnapshot,
    EvidenceKind,
    snapshot_hash,
)


class TeamRole(str, Enum):
    RED = "RED"
    BLACK = "BLACK"


class SourceStatus(str, Enum):
    VERIFIED = "VERIFIED"
    STALE = "STALE"
    MISSING = "MISSING"
    CONFLICTED = "CONFLICTED"


class Disposition(str, Enum):
    ADMISSIBLE = "ADMISSIBLE"
    RECLASSIFIED = "RECLASSIFIED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class ArbitrationTrigger:
    required: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class SourceEvidence:
    source_id: str
    available_at: datetime
    status: SourceStatus = SourceStatus.VERIFIED

    def __post_init__(self) -> None:
        if self.available_at.tzinfo is None or self.available_at.utcoffset() is None:
            raise ValueError("available_at must be timezone-aware")


@dataclass(frozen=True)
class TeamClaim:
    claim_id: str
    role: TeamRole
    topic: str
    statement: str
    kind: EvidenceKind
    source_ids: tuple[str, ...] = ()
    target_states: tuple[str, ...] = ()
    missing_data: tuple[str, ...] = ()
    falsifier: str = ""
    conflict_group: str | None = None

    def __post_init__(self) -> None:
        if not self.claim_id.strip() or not self.topic.strip() or not self.statement.strip():
            raise ValueError("claim_id, topic and statement cannot be empty")
        for state in self.target_states:
            if state not in {"A", "B", "C1", "C2", "C3", "D"}:
                raise ValueError(f"unsupported state {state!r}")


@dataclass(frozen=True)
class ClaimDecision:
    claim_id: str
    role: TeamRole
    topic: str
    original_kind: EvidenceKind
    final_kind: EvidenceKind
    disposition: Disposition
    reason: str
    missing_sources: tuple[str, ...]


@dataclass(frozen=True)
class ArbitrationReport:
    as_of: datetime
    snapshot_hash: str
    trigger_reasons: tuple[str, ...]
    decisions: tuple[ClaimDecision, ...]
    unresolved_conflict_groups: tuple[str, ...]
    falsification_conditions: tuple[str, ...]
    missing_data: tuple[str, ...]


def detect_material_change(
    current: DailySnapshot,
    previous: DailySnapshot,
    *,
    state_delta_threshold: float = 0.05,
) -> ArbitrationTrigger:
    if state_delta_threshold < 0:
        raise ValueError("state_delta_threshold must be non-negative")

    current_states = {row.state: row.value for row in current.states}
    previous_states = {row.state: row.value for row in previous.states}
    reasons: list[str] = []

    for state in ("A", "B", "C1", "C2", "C3", "D"):
        delta = current_states[state] - previous_states[state]
        if abs(delta) >= state_delta_threshold:
            reasons.append(f"{state} changed {delta:+.3f}")

    if current.stress_level != previous.stress_level:
        reasons.append(
            f"Stress changed {previous.stress_level.name}->{current.stress_level.name}"
        )

    for key in ("B", "C", "D"):
        if current.fat_pitch[key] != previous.fat_pitch[key]:
            reasons.append(
                f"{key}-Fat changed "
                f"{previous.fat_pitch[key].value}->{current.fat_pitch[key].value}"
            )

    return ArbitrationTrigger(required=bool(reasons), reasons=tuple(reasons))


def arbitrate_claim(
    claim: TeamClaim,
    sources: dict[str, SourceEvidence],
    *,
    as_of: datetime,
) -> ClaimDecision:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")

    missing_sources = tuple(
        sorted(source_id for source_id in claim.source_ids if source_id not in sources)
    )
    future_sources = tuple(
        sorted(
            source_id
            for source_id in claim.source_ids
            if source_id in sources and sources[source_id].available_at > as_of
        )
    )
    unusable_sources = tuple(
        sorted(
            source_id
            for source_id in claim.source_ids
            if source_id in sources
            and sources[source_id].status
            in {SourceStatus.MISSING, SourceStatus.CONFLICTED}
        )
    )
    unavailable = tuple(sorted(set(missing_sources + future_sources + unusable_sources)))

    if claim.kind is EvidenceKind.OBSERVED:
        if not claim.source_ids:
            return ClaimDecision(
                claim_id=claim.claim_id,
                role=claim.role,
                topic=claim.topic,
                original_kind=claim.kind,
                final_kind=EvidenceKind.UNCERTAIN,
                disposition=Disposition.REJECTED,
                reason="Observed claim has no traceable source.",
                missing_sources=(),
            )
        if unavailable:
            return ClaimDecision(
                claim_id=claim.claim_id,
                role=claim.role,
                topic=claim.topic,
                original_kind=claim.kind,
                final_kind=EvidenceKind.UNCERTAIN,
                disposition=Disposition.RECLASSIFIED,
                reason="Observed claim depends on missing, conflicted, or future evidence.",
                missing_sources=unavailable,
            )

        stale = tuple(
            sorted(
                source_id
                for source_id in claim.source_ids
                if sources[source_id].status is SourceStatus.STALE
            )
        )
        if stale:
            return ClaimDecision(
                claim_id=claim.claim_id,
                role=claim.role,
                topic=claim.topic,
                original_kind=claim.kind,
                final_kind=EvidenceKind.UNCERTAIN,
                disposition=Disposition.RECLASSIFIED,
                reason="Observed claim relies on stale evidence.",
                missing_sources=stale,
            )

        return ClaimDecision(
            claim_id=claim.claim_id,
            role=claim.role,
            topic=claim.topic,
            original_kind=claim.kind,
            final_kind=EvidenceKind.OBSERVED,
            disposition=Disposition.ADMISSIBLE,
            reason="Point-in-time source evidence is available and verified.",
            missing_sources=(),
        )

    if claim.kind is EvidenceKind.INFERRED and not claim.falsifier.strip():
        return ClaimDecision(
            claim_id=claim.claim_id,
            role=claim.role,
            topic=claim.topic,
            original_kind=claim.kind,
            final_kind=EvidenceKind.UNCERTAIN,
            disposition=Disposition.RECLASSIFIED,
            reason="Inference has no explicit falsifier.",
            missing_sources=unavailable,
        )

    return ClaimDecision(
        claim_id=claim.claim_id,
        role=claim.role,
        topic=claim.topic,
        original_kind=claim.kind,
        final_kind=claim.kind,
        disposition=Disposition.ADMISSIBLE,
        reason="Claim remains explicitly labeled and does not masquerade as observed data.",
        missing_sources=unavailable,
    )


def build_arbitration_report(
    snapshot: DailySnapshot,
    trigger: ArbitrationTrigger,
    claims: list[TeamClaim],
    sources: dict[str, SourceEvidence],
) -> ArbitrationReport:
    if not trigger.required:
        raise ValueError("arbitration report requires a material-change trigger")

    decisions = tuple(
        arbitrate_claim(claim, sources, as_of=snapshot.as_of) for claim in claims
    )

    groups: dict[str, set[TeamRole]] = {}
    for claim, decision in zip(claims, decisions, strict=True):
        if claim.conflict_group is None:
            continue
        if decision.disposition is Disposition.REJECTED:
            continue
        groups.setdefault(claim.conflict_group, set()).add(claim.role)

    unresolved = tuple(
        sorted(group for group, roles in groups.items() if len(roles) > 1)
    )

    falsifiers = tuple(
        dict.fromkeys(claim.falsifier for claim in claims if claim.falsifier.strip())
    )
    missing_data = tuple(
        sorted(
            {
                item
                for claim in claims
                for item in claim.missing_data
            }
            | {
                source
                for decision in decisions
                for source in decision.missing_sources
            }
        )
    )

    return ArbitrationReport(
        as_of=snapshot.as_of,
        snapshot_hash=snapshot_hash(snapshot),
        trigger_reasons=trigger.reasons,
        decisions=decisions,
        unresolved_conflict_groups=unresolved,
        falsification_conditions=falsifiers,
        missing_data=missing_data,
    )
