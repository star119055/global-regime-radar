from __future__ import annotations

import html
import json
import re
from datetime import UTC, datetime

import yaml

from global_regime_radar.data.contracts import Observation
from global_regime_radar.etl.common import (
    ParsedBatch,
    build_vintage,
    snapshot_only_observation,
    stable_observation_id,
)

SOURCE_ID = "lbnl_queued_up"
QUEUED_UP_URL = "https://emp.lbl.gov/queues"

_NUMBER = r"([0-9][0-9,]*(?:\.[0-9]+)?)"


def _plain_text(raw_payload: bytes) -> str:
    decoded = raw_payload.decode("utf-8", errors="replace")
    without_tags = re.sub(r"<[^>]+>", " ", decoded)
    return re.sub(r"\s+", " ", html.unescape(without_tags)).strip()


def _number(value: str) -> float:
    return float(value.replace(",", ""))


def _aware(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("LBNL snapshot available_at must be timezone-aware")
    return parsed


def parse_queued_up_html(
    raw_payload: bytes,
    retrieved_at: datetime,
    revision_number: int = 0,
) -> ParsedBatch:
    """Manual curation helper; not used by the daily live collector."""
    text = _plain_text(raw_payload)
    years = [
        int(value)
        for value in re.findall(
            r"(?:end of|through(?: the end of)?)\s+(20\d{2})",
            text,
            flags=re.IGNORECASE,
        )
    ]
    if not years:
        raise ValueError("LBNL Queued Up snapshot year not found")
    snapshot_year = max(years)

    generation_match = re.search(
        rf"representing\s+{_NUMBER}\s*GW\s+of\s+generation"
        rf"\s+and\s+(?:approximately\s+)?{_NUMBER}\s*GW\s+of\s+storage",
        text,
        flags=re.IGNORECASE,
    )
    if generation_match is None:
        raise ValueError("LBNL active generation/storage capacity not found")

    ia_match = re.search(
        rf"{_NUMBER}\s*GW\s+of\s+capacity\s+already\s+has\s+"
        r"a\s+draft\s+or\s+executed\s+interconnection\s+agreement",
        text,
        flags=re.IGNORECASE,
    )
    if ia_match is None:
        raise ValueError("LBNL draft/executed IA capacity not found")

    values = {
        "lbnl_active_generation_gw": _number(generation_match.group(1)),
        "lbnl_active_storage_gw": _number(generation_match.group(2)),
        "lbnl_draft_executed_ia_gw": _number(ia_match.group(1)),
    }

    vintage = build_vintage(SOURCE_ID, raw_payload, retrieved_at, revision_number)
    observed = datetime(snapshot_year, 12, 31, tzinfo=UTC)
    quality = (
        "pit:current-vintage-snapshot-only;"
        "frequency:annual;"
        "ia_not_cod;"
        "generation_interconnection_only"
    )
    observations = tuple(
        snapshot_only_observation(
            observation_id=stable_observation_id(
                SOURCE_ID,
                feature_id,
                snapshot_year,
                vintage.vintage_id,
            ),
            feature_id=feature_id,
            source_id=SOURCE_ID,
            entity_id="US",
            value=value,
            unit="GW",
            observation_start=observed,
            observation_end=observed,
            ingested_at=retrieved_at,
            vintage_id=vintage.vintage_id,
            quality_flag=quality,
        )
        for feature_id, value in values.items()
    )
    return ParsedBatch(vintage=vintage, observations=observations)


def parse_curated_snapshots(
    raw_payload: bytes,
    retrieved_at: datetime,
    revision_number: int = 0,
) -> ParsedBatch:
    payload = yaml.safe_load(raw_payload.decode("utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("snapshots"), list):
        raise TypeError("LBNL snapshot registry must contain a snapshots list")

    eligible: list[tuple[datetime, dict[str, object]]] = []
    for row in payload["snapshots"]:
        if not isinstance(row, dict):
            raise TypeError("LBNL snapshot entry must be a mapping")
        available_at = _aware(str(row["available_at"]))
        if available_at <= retrieved_at:
            eligible.append((available_at, row))

    if not eligible:
        raise ValueError("no LBNL snapshot was available at retrieval time")

    available_at, selected = max(eligible, key=lambda item: item[0])
    observed = datetime.strptime(
        str(selected["observation_end"]),
        "%Y-%m-%d",
    ).replace(tzinfo=UTC)

    canonical = json.dumps(
        selected,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    vintage = build_vintage(SOURCE_ID, canonical, retrieved_at, revision_number)
    snapshot_id = str(selected["snapshot_id"])
    quality = (
        "pit:curated-official-annual-snapshot;"
        "frequency:annual;"
        "ia_not_cod;"
        "generation_interconnection_only;"
        f"snapshot_id:{snapshot_id}"
    )
    values = {
        "lbnl_active_generation_gw": float(selected["active_generation_gw"]),
        "lbnl_active_storage_gw": float(selected["active_storage_gw"]),
        "lbnl_draft_executed_ia_gw": float(selected["draft_executed_ia_gw"]),
    }
    observations = tuple(
        Observation(
            observation_id=stable_observation_id(
                SOURCE_ID,
                snapshot_id,
                feature_id,
                vintage.vintage_id,
            ),
            feature_id=feature_id,
            source_id=SOURCE_ID,
            entity_id="US",
            value=value,
            unit="GW",
            observation_start=observed,
            observation_end=observed,
            published_at=None,
            available_at=available_at,
            ingested_at=retrieved_at,
            vintage_id=vintage.vintage_id,
            quality_flag=quality,
        )
        for feature_id, value in values.items()
    )
    return ParsedBatch(vintage=vintage, observations=observations)
