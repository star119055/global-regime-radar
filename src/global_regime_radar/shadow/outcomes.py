from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

from global_regime_radar.live.evidence import load_document
from global_regime_radar.regime.baseline import estimate_regime

STATES = ("A", "B", "C1", "C2", "C3", "D")
ENGINES = ("baseline0", "baseline1", "ukf")


@dataclass(frozen=True)
class TargetState:
    state: str
    observed_composite: float
    coverage: float


@dataclass(frozen=True)
class EngineForwardError:
    engine: str
    absolute_errors: dict[str, float]
    mae: float


@dataclass(frozen=True)
class OutcomeAttachment:
    origin_run_id: str
    horizon_days: int
    origin_decision_time: datetime
    target_run_id: str
    target_decision_time: datetime
    target_lag_days: float
    minimum_target_coverage: float
    targets: tuple[TargetState, ...]
    engines: tuple[EngineForwardError, ...]


@dataclass(frozen=True)
class LedgerRun:
    run_id: str
    decision_time: datetime
    run_dir: Path
    payload: dict[str, object]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mature prospective shadow outcomes")
    parser.add_argument("--ledger-root", type=Path, required=True)
    parser.add_argument("--horizons", type=int, nargs="+", default=[5, 20, 60])
    parser.add_argument("--minimum-target-coverage", type=float, default=0.40)
    parser.add_argument("--maximum-target-lag-days", type=float, default=2.0)
    return parser.parse_args()


def scan_runs(ledger_root: Path) -> list[LedgerRun]:
    runs: list[LedgerRun] = []
    for shadow_path in ledger_root.glob("runs/*/*/shadow.json"):
        payload = json.loads(shadow_path.read_text(encoding="utf-8"))
        decision_time = datetime.fromisoformat(payload["decision_time"])
        runs.append(
            LedgerRun(
                run_id=str(payload["run_id"]),
                decision_time=decision_time,
                run_dir=shadow_path.parent,
                payload=payload,
            )
        )
    return sorted(runs, key=lambda item: (item.decision_time, item.run_id))


def select_target_run(
    runs: list[LedgerRun],
    origin: LedgerRun,
    horizon_days: int,
    *,
    maximum_target_lag_days: float,
) -> LedgerRun | None:
    if horizon_days <= 0:
        raise ValueError("horizon_days must be positive")
    target_time = origin.decision_time + timedelta(days=horizon_days)
    candidates = [run for run in runs if run.decision_time >= target_time]
    if not candidates:
        return None
    target = candidates[0]
    lag_days = (target.decision_time - target_time).total_seconds() / 86400.0
    if lag_days > maximum_target_lag_days:
        return None
    return target


def _target_states(
    target: LedgerRun,
    *,
    minimum_target_coverage: float,
) -> tuple[TargetState, ...]:
    evidence_path = target.run_dir / "live-evidence.json"
    if not evidence_path.exists():
        return ()

    document = load_document(evidence_path)
    estimates = estimate_regime(document.evidence)
    result = []
    for state in STATES:
        estimate = estimates[state]
        if (
            estimate.observed_composite is not None
            and estimate.coverage >= minimum_target_coverage
        ):
            result.append(
                TargetState(
                    state=state,
                    observed_composite=estimate.observed_composite,
                    coverage=estimate.coverage,
                )
            )
    return tuple(result)


def build_outcome(
    origin: LedgerRun,
    target: LedgerRun,
    horizon_days: int,
    *,
    minimum_target_coverage: float,
) -> OutcomeAttachment | None:
    targets = _target_states(
        target,
        minimum_target_coverage=minimum_target_coverage,
    )
    if not targets:
        return None

    target_values = {item.state: item.observed_composite for item in targets}
    results = {
        str(result["engine"]): {
            str(row["state"]): float(row["value"])
            for row in result["states"]
        }
        for result in origin.payload.get("results", [])
    }
    if set(results) != set(ENGINES):
        return None

    engine_errors = []
    for engine in ENGINES:
        errors = {
            state: abs(results[engine][state] - target_value)
            for state, target_value in target_values.items()
        }
        mae = sum(errors.values()) / len(errors)
        engine_errors.append(
            EngineForwardError(
                engine=engine,
                absolute_errors=errors,
                mae=mae,
            )
        )

    target_due = origin.decision_time + timedelta(days=horizon_days)
    lag_days = (target.decision_time - target_due).total_seconds() / 86400.0
    return OutcomeAttachment(
        origin_run_id=origin.run_id,
        horizon_days=horizon_days,
        origin_decision_time=origin.decision_time,
        target_run_id=target.run_id,
        target_decision_time=target.decision_time,
        target_lag_days=lag_days,
        minimum_target_coverage=minimum_target_coverage,
        targets=targets,
        engines=tuple(engine_errors),
    )


def outcome_payload(outcome: OutcomeAttachment) -> dict[str, object]:
    return {
        "origin_run_id": outcome.origin_run_id,
        "horizon_days": outcome.horizon_days,
        "origin_decision_time": outcome.origin_decision_time.isoformat(),
        "target_run_id": outcome.target_run_id,
        "target_decision_time": outcome.target_decision_time.isoformat(),
        "target_lag_days": outcome.target_lag_days,
        "minimum_target_coverage": outcome.minimum_target_coverage,
        "metric_semantics": (
            "forward_consistency_against_later_observed_composite;"
            "not_prediction_accuracy"
        ),
        "targets": [asdict(item) for item in outcome.targets],
        "engines": [asdict(item) for item in outcome.engines],
    }


def write_outcome(ledger_root: Path, outcome: OutcomeAttachment) -> Path:
    target_dir = ledger_root / "outcomes" / outcome.origin_run_id
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{outcome.horizon_days}d.json"
    if path.exists():
        raise FileExistsError(f"refusing to overwrite outcome attachment: {path}")
    path.write_text(
        json.dumps(
            outcome_payload(outcome),
            sort_keys=True,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def mature_outcomes(
    ledger_root: Path,
    *,
    horizons: tuple[int, ...],
    minimum_target_coverage: float,
    maximum_target_lag_days: float,
) -> list[Path]:
    if not 0.0 <= minimum_target_coverage <= 1.0:
        raise ValueError("minimum_target_coverage must be within [0, 1]")
    runs = scan_runs(ledger_root)
    written: list[Path] = []

    for origin in runs:
        for horizon in horizons:
            path = ledger_root / "outcomes" / origin.run_id / f"{horizon}d.json"
            if path.exists():
                continue
            target = select_target_run(
                runs,
                origin,
                horizon,
                maximum_target_lag_days=maximum_target_lag_days,
            )
            if target is None:
                continue
            outcome = build_outcome(
                origin,
                target,
                horizon,
                minimum_target_coverage=minimum_target_coverage,
            )
            if outcome is not None:
                written.append(write_outcome(ledger_root, outcome))
    return written


def _outcome_payloads(ledger_root: Path) -> list[dict[str, object]]:
    payloads = []
    for path in ledger_root.glob("outcomes/*/*d.json"):
        payloads.append(json.loads(path.read_text(encoding="utf-8")))
    return payloads


def build_scorecard(ledger_root: Path) -> dict[str, object]:
    runs = scan_runs(ledger_root)
    outcomes = _outcome_payloads(ledger_root)
    pending = sum(run.payload.get("status") == "PENDING_DATA" for run in runs)
    completed = sum(run.payload.get("status") == "COMPLETED" for run in runs)

    disagreement: dict[str, list[float]] = {state: [] for state in STATES}
    for run in runs:
        for row in run.payload.get("disagreements", []):
            disagreement[str(row["state"])].append(float(row["spread"]))

    latest_states: dict[str, dict[str, float]] = {}
    if runs:
        for result in runs[-1].payload.get("results", []):
            latest_states[str(result["engine"])] = {
                str(row["state"]): float(row["value"])
                for row in result["states"]
            }

    outcome_counts: dict[str, int] = {}
    maes: dict[str, list[float]] = {engine: [] for engine in ENGINES}
    for outcome in outcomes:
        horizon_key = f"{int(outcome['horizon_days'])}d"
        outcome_counts[horizon_key] = outcome_counts.get(horizon_key, 0) + 1
        for engine in outcome.get("engines", []):
            maes[str(engine["engine"])].append(float(engine["mae"]))

    return {
        "schema_version": 1,
        "total_runs": len(runs),
        "pending_runs": pending,
        "promotion_eligible_runs": completed,
        "first_decision_time": runs[0].decision_time.isoformat() if runs else None,
        "latest_decision_time": runs[-1].decision_time.isoformat() if runs else None,
        "mean_engine_spread_by_state": {
            state: (
                sum(values) / len(values)
                if values
                else None
            )
            for state, values in disagreement.items()
        },
        "latest_engine_states": latest_states,
        "matured_outcome_counts": outcome_counts,
        "mean_forward_consistency_mae": {
            engine: (sum(values) / len(values) if values else None)
            for engine, values in maes.items()
        },
        "metric_semantics": (
            "forward consistency compares an origin state estimate with a later "
            "observation-driven composite; it is not prediction accuracy"
        ),
    }


def write_scorecard(ledger_root: Path) -> Path:
    path = ledger_root / "scorecard.json"
    path.write_text(
        json.dumps(
            build_scorecard(ledger_root),
            sort_keys=True,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def main() -> int:
    args = _parse_args()
    mature_outcomes(
        args.ledger_root,
        horizons=tuple(args.horizons),
        minimum_target_coverage=args.minimum_target_coverage,
        maximum_target_lag_days=args.maximum_target_lag_days,
    )
    write_scorecard(args.ledger_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
