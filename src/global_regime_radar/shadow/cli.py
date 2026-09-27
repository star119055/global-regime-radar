from __future__ import annotations

import argparse
import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import yaml

from global_regime_radar.live.evidence import load_document
from global_regime_radar.regime.baseline import estimate_regime
from global_regime_radar.regime.dynamics import Coupling
from global_regime_radar.shadow.engine import (
    ShadowStatus,
    canonical_config_hash,
    pending_shadow_run,
    readiness_gaps,
    run_shadow,
)
from global_regime_radar.shadow.reporting import (
    render_shadow_json,
    render_shadow_markdown,
)
from global_regime_radar.shadow.state import (
    ShadowPriorState,
    load_prior_state,
    write_prior_state,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Global Regime Radar shadow runner")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--decision-time")
    parser.add_argument("--feature-set-version", default="live-v3")
    parser.add_argument("--config-hash")
    parser.add_argument("--prior-state", type=Path)
    parser.add_argument(
        "--shadow-config",
        type=Path,
        default=Path("config/shadow_mode.yaml"),
    )
    parser.add_argument(
        "--dynamic-config",
        type=Path,
        default=Path("config/regime_dynamics.yaml"),
    )
    parser.add_argument(
        "--ukf-config",
        type=Path,
        default=Path("config/filter_ukf.yaml"),
    )
    return parser.parse_args()


def _load_yaml(path: Path) -> dict[str, object]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return payload


def _couplings(payload: dict[str, object]) -> list[Coupling]:
    return [
        Coupling(
            source=str(item["source"]),
            target=str(item["target"]),
            coefficient=float(item["coefficient"]),
        )
        for item in payload.get("couplings", [])
    ]


def _combined_config_hash(
    shadow: dict[str, object],
    dynamic: dict[str, object],
    ukf: dict[str, object],
) -> str:
    return canonical_config_hash(
        {
            "shadow": shadow,
            "dynamic": dynamic,
            "ukf": ukf,
        }
    )


def _diagnostic_run(
    *,
    document,
    decision_time: datetime,
    generated_at: datetime,
    config_hash: str,
    feature_set_version: str,
    strict_minimum_coverage: float,
    dynamic_config: dict[str, object],
    ukf_config: dict[str, object],
    prior: ShadowPriorState | None,
):
    estimates = estimate_regime(document.evidence)
    coverage_gaps = readiness_gaps(
        estimates,
        minimum_state_coverage=strict_minimum_coverage,
    )
    missing_requirements = tuple(
        dict.fromkeys((*document.gaps, *coverage_gaps))
    )

    dynamic_q = {
        key: float(value)
        for key, value in dynamic_config["process_variance_per_day"].items()
    }
    ukf_q = {
        key: float(value)
        for key, value in ukf_config["latent_process_variance_per_day"].items()
    }
    half_lives = {
        key: float(value)
        for key, value in dynamic_config["half_life_days"].items()
    }

    run, dynamic, ukf = run_shadow(
        decision_time=decision_time,
        generated_at=generated_at,
        dataset_hash=document.dataset_hash,
        config_hash=config_hash,
        feature_set_version=feature_set_version,
        evidence=document.evidence,
        prior_dynamic=prior.dynamic if prior else None,
        prior_ukf=prior.ukf if prior else None,
        prior_time=prior.prior_time if prior else None,
        half_life_days=half_lives,
        dynamic_process_variance_per_day=dynamic_q,
        ukf_process_variance_per_day=ukf_q,
        couplings=_couplings(dynamic_config),
        minimum_state_coverage=0.0,
        missing_variance_per_day=float(
            dynamic_config.get("missing_variance_per_day", 0.0)
        ),
    )

    if missing_requirements:
        run = replace(
            run,
            status=ShadowStatus.PENDING_DATA,
            missing_requirements=missing_requirements,
        )

    return run, ShadowPriorState(
        prior_time=decision_time,
        dynamic=dynamic,
        ukf=ukf,
    )


def main() -> int:
    args = _parse_args()
    generated_at = datetime.now(UTC)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.input is None or not args.input.exists():
        decision_time = (
            datetime.fromisoformat(args.decision_time)
            if args.decision_time
            else generated_at
        )
        if decision_time.tzinfo is None or decision_time.utcoffset() is None:
            raise ValueError("decision time must be timezone-aware")
        run = pending_shadow_run(
            decision_time=decision_time,
            generated_at=generated_at,
            dataset_hash=hashlib.sha256(b"no-live-input").hexdigest(),
            config_hash=args.config_hash or "unwired-live-config",
            feature_set_version=args.feature_set_version,
            missing_requirements=("normalized_live_evidence:missing",),
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

    document = load_document(args.input)
    decision_time = (
        datetime.fromisoformat(args.decision_time)
        if args.decision_time
        else document.as_of
    )
    if decision_time.tzinfo is None or decision_time.utcoffset() is None:
        raise ValueError("decision time must be timezone-aware")

    shadow_config = _load_yaml(args.shadow_config)
    dynamic_config = _load_yaml(args.dynamic_config)
    ukf_config = _load_yaml(args.ukf_config)
    config_hash = args.config_hash or _combined_config_hash(
        shadow_config,
        dynamic_config,
        ukf_config,
    )
    strict_minimum_coverage = float(
        shadow_config["readiness"]["minimum_state_coverage"]
    )

    prior = None
    if args.prior_state is not None and args.prior_state.exists():
        prior = load_prior_state(args.prior_state)
        if prior.prior_time > decision_time:
            raise ValueError("prior state cannot come from the future")

    run, next_prior = _diagnostic_run(
        document=document,
        decision_time=decision_time,
        generated_at=generated_at,
        config_hash=config_hash,
        feature_set_version=args.feature_set_version,
        strict_minimum_coverage=strict_minimum_coverage,
        dynamic_config=dynamic_config,
        ukf_config=ukf_config,
        prior=prior,
    )

    (args.output_dir / "shadow.json").write_text(
        render_shadow_json(run),
        encoding="utf-8",
    )
    (args.output_dir / "shadow.md").write_text(
        render_shadow_markdown(run),
        encoding="utf-8",
    )
    write_prior_state(next_prior, args.output_dir / "state.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
