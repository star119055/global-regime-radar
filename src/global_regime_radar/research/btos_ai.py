from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import yaml


@dataclass(frozen=True)
class AIResearchSnapshot:
    snapshot_id: str
    available_at: datetime
    collection_start: str
    collection_end: str
    paper_reference_period: str
    sources: tuple[dict[str, str], ...]
    facts: dict[str, float]
    authoritative_state_input: bool
    candidate_state: str
    blocked_indicator_keys: tuple[str, ...]
    interpretation: str
    causal_claim_allowed: bool
    notes: tuple[str, ...]
    snapshot_hash: str

    def __post_init__(self) -> None:
        if self.available_at.tzinfo is None or self.available_at.utcoffset() is None:
            raise ValueError("available_at must be timezone-aware")
        if self.authoritative_state_input:
            raise ValueError("BTOS research snapshot cannot be an authoritative state input")
        if self.causal_claim_allowed:
            raise ValueError("BTOS research snapshot cannot authorize causal claims")
        if self.candidate_state != "A":
            raise ValueError("BTOS AI research snapshot candidate_state must be A")


def _aware(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("snapshot available_at must be timezone-aware")
    return parsed


def _snapshot_hash(payload: dict[str, object]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def select_snapshot(
    raw_payload: bytes,
    decision_time: datetime,
) -> AIResearchSnapshot | None:
    if decision_time.tzinfo is None or decision_time.utcoffset() is None:
        raise ValueError("decision_time must be timezone-aware")

    payload = yaml.safe_load(raw_payload.decode("utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("snapshots"), list):
        raise TypeError("BTOS research registry must contain a snapshots list")

    eligible: list[tuple[datetime, dict[str, object]]] = []
    for row in payload["snapshots"]:
        if not isinstance(row, dict):
            raise TypeError("BTOS research snapshot must be a mapping")
        available_at = _aware(str(row["available_at"]))
        if available_at <= decision_time:
            eligible.append((available_at, row))

    if not eligible:
        return None

    available_at, selected = max(eligible, key=lambda item: item[0])
    semantics = selected.get("semantics")
    facts = selected.get("facts")
    sources = selected.get("sources")
    if not isinstance(semantics, dict):
        raise TypeError("BTOS research snapshot semantics must be a mapping")
    if not isinstance(facts, dict):
        raise TypeError("BTOS research snapshot facts must be a mapping")
    if not isinstance(sources, list):
        raise TypeError("BTOS research snapshot sources must be a list")

    canonical_selected = json.loads(
        json.dumps(selected, sort_keys=True, ensure_ascii=False)
    )
    return AIResearchSnapshot(
        snapshot_id=str(selected["snapshot_id"]),
        available_at=available_at,
        collection_start=str(selected["collection_start"]),
        collection_end=str(selected["collection_end"]),
        paper_reference_period=str(selected["paper_reference_period"]),
        sources=tuple(
            {str(key): str(value) for key, value in source.items()}
            for source in sources
        ),
        facts={str(key): float(value) for key, value in facts.items()},
        authoritative_state_input=bool(semantics["authoritative_state_input"]),
        candidate_state=str(semantics["candidate_state"]),
        blocked_indicator_keys=tuple(
            str(value) for value in semantics["blocked_indicator_keys"]
        ),
        interpretation=str(semantics["interpretation"]),
        causal_claim_allowed=bool(semantics["causal_claim_allowed"]),
        notes=tuple(str(value) for value in semantics.get("notes", [])),
        snapshot_hash=_snapshot_hash(canonical_selected),
    )


def research_payload(
    snapshot: AIResearchSnapshot | None,
    *,
    decision_time: datetime,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "decision_time": decision_time.isoformat(),
        "status": "AVAILABLE" if snapshot is not None else "NOT_YET_AVAILABLE",
        "authoritative_state_input": False if snapshot is None else snapshot.authoritative_state_input,
        "snapshot": asdict(snapshot) if snapshot is not None else None,
        "state_effect": {
            "A_coverage_increment": 0.0,
            "reason": (
                "Research context is intentionally excluded from authoritative "
                "state evidence. APCR-DiD, LLIER and GEOI remain separate contracts."
            ),
        },
    }


def write_research_context(
    snapshot: AIResearchSnapshot | None,
    *,
    decision_time: datetime,
    path: Path,
) -> None:
    path.write_text(
        json.dumps(
            research_payload(snapshot, decision_time=decision_time),
            sort_keys=True,
            ensure_ascii=False,
            indent=2,
            default=lambda value: value.isoformat() if isinstance(value, datetime) else value,
        )
        + "\n",
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render BTOS AI research context")
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("config/btos_ai_research_snapshots.yaml"),
    )
    parser.add_argument("--live-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    live_payload = json.loads(args.live_evidence.read_text(encoding="utf-8"))
    decision_time = datetime.fromisoformat(live_payload["as_of"])
    snapshot = select_snapshot(args.registry.read_bytes(), decision_time)
    write_research_context(
        snapshot,
        decision_time=decision_time,
        path=args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
