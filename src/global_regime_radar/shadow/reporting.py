from __future__ import annotations

import json
from dataclasses import asdict

from global_regime_radar.shadow.engine import ShadowRun, ShadowStatus


def render_shadow_markdown(run: ShadowRun) -> str:
    lines = [
        f"# Shadow Mode — {run.decision_time.isoformat()}",
        "",
        f"**Status:** {run.status.value}",
        f"**Dataset:** `{run.dataset_hash}`",
        f"**Config:** `{run.config_hash}`",
        f"**Feature set:** `{run.feature_set_version}`",
        "",
    ]

    if run.status is ShadowStatus.PENDING_DATA:
        lines.append("## Missing requirements")
        lines.extend(f"- {item}" for item in run.missing_requirements)
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            "## Engine comparison",
            "| State | Baseline0 | Baseline1 | UKF | Max spread |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    states = {
        result.engine: {item.state: item.value for item in result.states}
        for result in run.results
    }
    spreads = {item.state: item.spread for item in run.disagreements}
    for state in ("A", "B", "C1", "C2", "C3", "D"):
        lines.append(
            f"| {state} | {states['baseline0'][state]:.3f} | "
            f"{states['baseline1'][state]:.3f} | "
            f"{states['ukf'][state]:.3f} | {spreads[state]:.3f} |"
        )
    return "\n".join(lines) + "\n"


def shadow_payload(run: ShadowRun) -> dict[str, object]:
    return {
        "run_id": run.run_id,
        "decision_time": run.decision_time.isoformat(),
        "generated_at": run.generated_at.isoformat(),
        "status": run.status.value,
        "dataset_hash": run.dataset_hash,
        "config_hash": run.config_hash,
        "feature_set_version": run.feature_set_version,
        "results": [
            {
                "engine": result.engine,
                "states": [asdict(item) for item in result.states],
            }
            for result in run.results
        ],
        "missing_requirements": list(run.missing_requirements),
        "disagreements": [asdict(item) for item in run.disagreements],
    }


def render_shadow_json(run: ShadowRun) -> str:
    return json.dumps(
        shadow_payload(run),
        sort_keys=True,
        ensure_ascii=False,
        indent=2,
    ) + "\n"
