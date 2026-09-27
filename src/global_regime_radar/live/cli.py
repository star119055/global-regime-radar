from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from global_regime_radar.live.collector import collect_public_core
from global_regime_radar.live.evidence import build_live_evidence, write_document


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect live public evidence")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--retrieved-at")
    parser.add_argument("--lookback-days", type=int, default=180)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    retrieved_at = (
        datetime.fromisoformat(args.retrieved_at)
        if args.retrieved_at
        else datetime.now(UTC)
    )
    if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
        raise ValueError("retrieved_at must be timezone-aware")

    bundle = collect_public_core(
        retrieved_at,
        lookback_days=args.lookback_days,
    )
    document = build_live_evidence(bundle)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_document(document, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
