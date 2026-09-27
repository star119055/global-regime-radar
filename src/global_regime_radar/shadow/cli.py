from __future__ import annotations

import argparse
import hashlib
from datetime import UTC, datetime
from pathlib import Path

from global_regime_radar.live.evidence import load_document
from global_regime_radar.shadow.engine import pending_shadow_run
from global_regime_radar.shadow.reporting import (
    render_shadow_json,
    render_shadow_markdown,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Global Regime Radar shadow runner")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--decision-time")
    parser.add_argument("--feature-set-version", default="live-v1")
    parser.add_argument("--config-hash", default="unwired-live-config")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    generated_at = datetime.now(UTC)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.input is not None and args.input.exists():
        document = load_document(args.input)
        decision_time = (
            datetime.fromisoformat(args.decision_time)
            if args.decision_time
            else document.as_of
        )
        dataset_hash = document.dataset_hash
        missing = document.gaps
        if not missing:
            missing = ("shadow_state:persistence_adapter:not_implemented",)
    else:
        decision_time = (
            datetime.fromisoformat(args.decision_time)
            if args.decision_time
            else generated_at
        )
        dataset_hash = hashlib.sha256(b"no-live-input").hexdigest()
        missing = ("normalized_live_evidence:missing",)

    if decision_time.tzinfo is None or decision_time.utcoffset() is None:
        raise ValueError("decision time must be timezone-aware")

    run = pending_shadow_run(
        decision_time=decision_time,
        generated_at=generated_at,
        dataset_hash=dataset_hash,
        config_hash=args.config_hash,
        feature_set_version=args.feature_set_version,
        missing_requirements=missing,
    )
    (args.output_dir / "shadow.json").write_text(
        render_shadow_json(run),
        encoding="utf-8",
    )
    (args.output_dir / "shadow.md").write_text(
        render_shadow_markdown(run),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
