import hashlib
import json
from collections.abc import Iterable
from typing import Any

from global_regime_radar.data.contracts import DataVintage, Observation


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def make_vintage_id(source_id: str, source_hash: str, revision_number: int) -> str:
    if revision_number < 0:
        raise ValueError("revision_number must be non-negative")
    return f"{source_id}:{revision_number}:{source_hash[:16]}"


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def dataset_snapshot_hash(
    observations: Iterable[Observation],
    vintages: Iterable[DataVintage],
) -> str:
    vintage_map = {v.vintage_id: v for v in vintages}

    rows: list[dict[str, Any]] = []
    for obs in observations:
        vintage = vintage_map.get(obs.vintage_id)
        if vintage is None:
            raise ValueError(f"missing vintage metadata for {obs.vintage_id}")
        rows.append(
            {
                "observation": obs.model_dump(mode="json"),
                "vintage": vintage.model_dump(mode="json"),
            }
        )

    rows.sort(
        key=lambda row: (
            row["observation"]["feature_id"],
            row["observation"]["entity_id"] or "",
            row["observation"]["observation_start"] or "",
            row["observation"]["observation_end"] or "",
            row["observation"]["available_at"],
            row["vintage"]["revision_number"],
            row["observation"]["observation_id"],
        )
    )
    return sha256_bytes(_canonical_json(rows).encode("utf-8"))
