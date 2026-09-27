from __future__ import annotations

import html
import re
from datetime import UTC, datetime

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


def parse_queued_up_html(
    raw_payload: bytes,
    retrieved_at: datetime,
    revision_number: int = 0,
) -> ParsedBatch:
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
