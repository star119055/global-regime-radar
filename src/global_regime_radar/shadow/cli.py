from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

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
    decision_time = (
        datetime.fromisoformat(args.decision_time)
        if args.decision_time
        else datetime.now(UTC)
    )
    if decision_time.tzinfo is None or decision_time.utcoffset() is None:
        raise ValueError("decision time must be timezone-aware")

    generated_at = datetime.now(UTC)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.input is None or not args.input.exists():
        dataset_hash = hashlib.sha256(b"no-live-input").hexdigest()
        run = pending_shadow_run(
            decision_time=decision_time,
            generated_at=generated_at,
            dataset_hash=dataset_hash,
            config_hash=args.config_hash,
            feature_set_version=args.feature_set_version,
            missing_requirements=("normalized_live_evidence:missing",),
        )
    else:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        dataset_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        run = pending_shadow_run(
            decision_time=decision_time,
            generated_at=generated_at,
            dataset_hash=dataset_hash,
            config_hash=args.config_hash,
            feature_set_version=args.feature_set_version,
            missing_requirements=("normalized_live_evidence_adapter:not_implemented",),
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
