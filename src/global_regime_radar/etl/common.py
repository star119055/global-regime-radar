from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib

from global_regime_radar.data.contracts import DataVintage, Observation
from global_regime_radar.data.hashing import make_vintage_id, sha256_bytes


@dataclass(frozen=True)
class ParsedBatch:
    vintage: DataVintage
    observations: tuple[Observation, ...]


def build_vintage(
    source_id: str,
    raw_payload: bytes,
    retrieved_at: datetime,
    revision_number: int = 0,
) -> DataVintage:
    source_hash = sha256_bytes(raw_payload)
    return DataVintage(
        vintage_id=make_vintage_id(source_id, source_hash, revision_number),
        source_id=source_id,
        retrieved_at=retrieved_at,
        source_hash=source_hash,
        revision_number=revision_number,
    )


def stable_observation_id(*parts: object) -> str:
    material = "|".join("" if part is None else str(part) for part in parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def parse_date_utc(value: str) -> datetime:
    parsed = datetime.strptime(value, "%Y-%m-%d")
    return parsed.replace(tzinfo=UTC)


def optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def snapshot_only_observation(
    *,
    observation_id: str,
    feature_id: str,
    source_id: str,
    entity_id: str | None,
    value: float | None,
    unit: str | None,
    observation_start: datetime | None,
    observation_end: datetime | None,
    ingested_at: datetime,
    vintage_id: str,
    quality_flag: str = "pit:snapshot-only",
) -> Observation:
    return Observation(
        observation_id=observation_id,
        feature_id=feature_id,
        source_id=source_id,
        entity_id=entity_id,
        value=value,
        unit=unit,
        observation_start=observation_start,
        observation_end=observation_end,
        available_at=ingested_at,
        ingested_at=ingested_at,
        vintage_id=vintage_id,
        quality_flag=quality_flag,
    )
