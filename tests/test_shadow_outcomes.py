import json
from datetime import UTC, datetime, timedelta

import pytest

from global_regime_radar.live.evidence import (
    LiveEvidenceDocument,
    LiveEvidenceItem,
    write_document,
)
from global_regime_radar.shadow.outcomes import (
    build_outcome,
    build_scorecard,
    mature_outcomes,
    scan_runs,
)


STATES = ("A", "B", "C1", "C2", "C3", "D")
ENGINES = ("baseline0", "baseline1", "ukf")


def dt(day: int) -> datetime:
    return datetime(2026, 1, day, 0, 30, tzinfo=UTC)


def _write_run(root, day: int, run_id: str, value: float) -> None:
    run_dir = root / "runs" / f"2026-01-{day:02d}" / run_id
    run_dir.mkdir(parents=True)
    payload = {
        "run_id": run_id,
        "decision_time": dt(day).isoformat(),
        "generated_at": (dt(day) + timedelta(minutes=1)).isoformat(),
        "status": "COMPLETED",
        "results": [
            {
                "engine": engine,
                "states": [
                    {
                        "state": state,
                        "value": value + index * 0.01,
                        "variance": 0.02,
                        "confidence": "Medium",
                    }
                    for index, state in enumerate(STATES)
                ],
            }
            for engine in ENGINES
        ],
        "disagreements": [
            {"state": state, "spread": 0.01} for state in STATES
        ],
    }
    (run_dir / "shadow.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )
    evidence = LiveEvidenceDocument(
        as_of=dt(day),
        dataset_hash=f"dataset-{day}",
        source_hashes={"fixture": f"hash-{day}"},
        items=tuple(
            LiveEvidenceItem(
                state=state,
                key=f"{state}-signal",
                activation=value + index * 0.01,
                weight=1.0,
                measurement_variance=0.02,
                attribution_group=f"{state}-group",
                evidence_ids=(f"{run_id}-{state}",),
                note="fixture",
            )
            for index, state in enumerate(STATES)
        ),
        source_failures=(),
    )
    write_document(evidence, run_dir / "live-evidence.json")


def test_mature_outcome_is_append_only_and_uses_later_observed_composite(tmp_path):
    _write_run(tmp_path, 1, "origin", 0.50)
    _write_run(tmp_path, 6, "target", 0.70)

    written = mature_outcomes(
        tmp_path,
        horizons=(5,),
        minimum_target_coverage=0.40,
        maximum_target_lag_days=1.0,
    )
    assert len(written) == 1
    payload = json.loads(written[0].read_text(encoding="utf-8"))
    assert payload["origin_run_id"] == "origin"
    assert payload["target_run_id"] == "target"
    assert payload["metric_semantics"].endswith("not_prediction_accuracy")
    assert payload["engines"][0]["mae"] == pytest.approx(0.2)

    second = mature_outcomes(
        tmp_path,
        horizons=(5,),
        minimum_target_coverage=0.40,
        maximum_target_lag_days=1.0,
    )
    assert second == []


def test_outcome_waits_until_horizon_exists(tmp_path):
    _write_run(tmp_path, 1, "origin", 0.50)
    assert mature_outcomes(
        tmp_path,
        horizons=(5,),
        minimum_target_coverage=0.40,
        maximum_target_lag_days=1.0,
    ) == []


def test_scorecard_summarizes_runs_disagreement_and_matured_outcomes(tmp_path):
    _write_run(tmp_path, 1, "origin", 0.50)
    _write_run(tmp_path, 6, "target", 0.70)
    mature_outcomes(
        tmp_path,
        horizons=(5,),
        minimum_target_coverage=0.40,
        maximum_target_lag_days=1.0,
    )
    scorecard = build_scorecard(tmp_path)
    assert scorecard["total_runs"] == 2
    assert scorecard["promotion_eligible_runs"] == 2
    assert scorecard["matured_outcome_counts"]["5d"] == 1
    assert scorecard["mean_engine_spread_by_state"]["B"] == 0.01
    assert scorecard["mean_forward_consistency_mae"]["baseline0"] == pytest.approx(0.2)


def test_scan_runs_is_chronological(tmp_path):
    _write_run(tmp_path, 6, "later", 0.70)
    _write_run(tmp_path, 1, "earlier", 0.50)
    assert [run.run_id for run in scan_runs(tmp_path)] == ["earlier", "later"]


def test_build_outcome_requires_three_engine_origin(tmp_path):
    _write_run(tmp_path, 1, "origin", 0.50)
    _write_run(tmp_path, 6, "target", 0.70)
    runs = scan_runs(tmp_path)
    payload = runs[0].payload
    payload["results"] = payload["results"][:-1]
    assert build_outcome(
        runs[0],
        runs[1],
        5,
        minimum_target_coverage=0.40,
    ) is None
