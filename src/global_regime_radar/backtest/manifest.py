import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from global_regime_radar.backtest.folds import BacktestFold


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RunManifest:
    run_id: str
    model_version: str
    feature_set_version: str
    fold_id: str
    universe: str
    train_end: datetime
    test_start: datetime
    test_end: datetime
    dataset_hash: str
    code_commit: str
    parameters_json: str
    parameters_hash: str

    def stable_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("run_id")
        return payload


def build_manifest(
    *,
    model_version: str,
    feature_set_version: str,
    fold: BacktestFold,
    dataset_hash: str,
    code_commit: str,
    parameters: dict[str, Any],
) -> RunManifest:
    if not dataset_hash:
        raise ValueError("dataset_hash is required")
    if not code_commit:
        raise ValueError("code_commit is required")

    parameters_json = canonical_json(parameters)
    parameters_hash = sha256_text(parameters_json)

    stable = {
        "model_version": model_version,
        "feature_set_version": feature_set_version,
        "fold_id": fold.fold_id,
        "universe": fold.universe,
        "train_end": fold.train_end.isoformat(),
        "test_start": fold.test_start.isoformat(),
        "test_end": fold.test_end.isoformat(),
        "dataset_hash": dataset_hash,
        "code_commit": code_commit,
        "parameters_hash": parameters_hash,
    }
    run_id = sha256_text(canonical_json(stable))[:24]

    return RunManifest(
        run_id=run_id,
        model_version=model_version,
        feature_set_version=feature_set_version,
        fold_id=fold.fold_id,
        universe=fold.universe,
        train_end=fold.train_end,
        test_start=fold.test_start,
        test_end=fold.test_end,
        dataset_hash=dataset_hash,
        code_commit=code_commit,
        parameters_json=parameters_json,
        parameters_hash=parameters_hash,
    )
