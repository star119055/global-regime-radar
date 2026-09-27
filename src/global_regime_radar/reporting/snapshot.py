from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum

from global_regime_radar.stress.engine import StressLevel

_STATES = ("A", "B", "C1", "C2", "C3", "D")


class EvidenceKind(str, Enum):
    OBSERVED = "Observed"
    INFERRED = "Inferred"
    UNCERTAIN = "Uncertain"


class FatPitchStatus(str, Enum):
    OFF = "OFF"
    WATCH = "WATCH"
    ON = "ON"


@dataclass(frozen=True)
class StateRow:
    state: str
    value: float
    delta: float
    confidence: str
    coverage: float
    variance: float

    def __post_init__(self) -> None:
        if self.state not in _STATES:
            raise ValueError(f"unsupported state {self.state!r}")
        if not 0.0 <= self.value <= 1.0:
            raise ValueError("value must be within [0, 1]")
        if not 0.0 <= self.coverage <= 1.0:
            raise ValueError("coverage must be within [0, 1]")
        if self.variance < 0:
            raise ValueError("variance must be non-negative")


@dataclass(frozen=True)
class ChangeDriver:
    key: str
    label: str
    impact: float
    detail: str


@dataclass(frozen=True)
class EvidenceItem:
    kind: EvidenceKind
    claim: str
    source_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class FeedbackLoop:
    label: str
    chain: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.chain) < 2:
            raise ValueError("feedback loop must have at least two nodes")


@dataclass(frozen=True)
class DailySnapshot:
    as_of: datetime
    generated_at: datetime
    model_version: str
    conclusion: str
    states: tuple[StateRow, ...]
    stress_level: StressLevel
    fat_pitch: dict[str, FatPitchStatus]
    top_changes: tuple[ChangeDriver, ...]
    feedback_loop: FeedbackLoop
    evidence: tuple[EvidenceItem, ...]
    next_confirmation: str
    falsification_conditions: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("as_of", "generated_at"):
            value = getattr(self, field_name)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{field_name} must be timezone-aware")

        state_keys = tuple(row.state for row in self.states)
        if len(state_keys) != len(_STATES) or set(state_keys) != set(_STATES):
            raise ValueError("snapshot must contain exactly A/B/C1/C2/C3/D once each")
        if len(self.top_changes) > 3:
            raise ValueError("top_changes may contain at most three drivers")
        if set(self.fat_pitch) != {"B", "C", "D"}:
            raise ValueError("fat_pitch must contain exactly B/C/D")
        if not self.conclusion.strip():
            raise ValueError("conclusion cannot be empty")
        if not self.next_confirmation.strip():
            raise ValueError("next_confirmation cannot be empty")


def select_top_drivers(drivers: list[ChangeDriver]) -> tuple[ChangeDriver, ...]:
    return tuple(
        sorted(drivers, key=lambda item: (-abs(item.impact), item.key))[:3]
    )


def canonical_payload(snapshot: DailySnapshot) -> dict[str, object]:
    return {
        "as_of": snapshot.as_of.isoformat(),
        "model_version": snapshot.model_version,
        "conclusion": snapshot.conclusion,
        "states": [
            {
                "state": row.state,
                "value": row.value,
                "delta": row.delta,
                "confidence": row.confidence,
                "coverage": row.coverage,
                "variance": row.variance,
            }
            for row in sorted(snapshot.states, key=lambda row: _STATES.index(row.state))
        ],
        "stress_level": snapshot.stress_level.name,
        "fat_pitch": {
            key: snapshot.fat_pitch[key].value for key in ("B", "C", "D")
        },
        "top_changes": [asdict(item) for item in snapshot.top_changes],
        "feedback_loop": {
            "label": snapshot.feedback_loop.label,
            "chain": list(snapshot.feedback_loop.chain),
        },
        "evidence": [
            {
                "kind": item.kind.value,
                "claim": item.claim,
                "source_ids": list(item.source_ids),
            }
            for item in snapshot.evidence
        ],
        "next_confirmation": snapshot.next_confirmation,
        "falsification_conditions": list(snapshot.falsification_conditions),
    }


def snapshot_hash(snapshot: DailySnapshot) -> str:
    raw = json.dumps(
        canonical_payload(snapshot),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def snapshot_id(snapshot: DailySnapshot) -> str:
    return f"{snapshot.as_of.date().isoformat()}:{snapshot.model_version}:{snapshot_hash(snapshot)[:12]}"


def render_markdown(snapshot: DailySnapshot) -> str:
    lines = [
        f"# Global Regime Radar — {snapshot.as_of.date().isoformat()}",
        "",
        "## 一句话结论",
        snapshot.conclusion,
        "",
        "## State Matrix",
        "| State | Value | Δ | Confidence | Coverage |",
        "|---|---:|---:|---|---:|",
    ]

    rows = sorted(snapshot.states, key=lambda row: _STATES.index(row.state))
    for row in rows:
        lines.append(
            f"| {row.state} | {row.value:.2f} | {row.delta:+.2f} | "
            f"{row.confidence} | {row.coverage:.0%} |"
        )

    lines.extend(
        [
            "",
            f"**Stress:** {snapshot.stress_level.name}",
            "",
            "**Fat Pitch:** "
            + " · ".join(
                f"{key}-Fat {snapshot.fat_pitch[key].value}" for key in ("B", "C", "D")
            ),
            "",
            "## 今日 Top 3 变化",
        ]
    )
    if snapshot.top_changes:
        for item in snapshot.top_changes:
            lines.append(
                f"- **{item.label}** ({item.impact:+.3f}): {item.detail}"
            )
    else:
        lines.append("- No material model-changing driver.")

    lines.extend(
        [
            "",
            "## 主导 Feedback Loop",
            f"**{snapshot.feedback_loop.label}:** "
            + " → ".join(snapshot.feedback_loop.chain),
            "",
            "## 关键新证据",
        ]
    )
    if snapshot.evidence:
        for item in snapshot.evidence:
            sources = f" [{', '.join(item.source_ids)}]" if item.source_ids else ""
            lines.append(f"- **{item.kind.value}**: {item.claim}{sources}")
    else:
        lines.append("- No new evidence.")

    lines.extend(
        [
            "",
            "## 下一确认事件",
            snapshot.next_confirmation,
            "",
            "## 模型证伪条件",
        ]
    )
    if snapshot.falsification_conditions:
        lines.extend(f"- {item}" for item in snapshot.falsification_conditions)
    else:
        lines.append("- None specified.")

    return "\n".join(lines) + "\n"
