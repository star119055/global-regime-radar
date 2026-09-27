from datetime import UTC, datetime

from global_regime_radar.data.contracts import Observation
from global_regime_radar.etl.common import (
    ParsedBatch,
    build_vintage,
    snapshot_only_observation,
    stable_observation_id,
)

SOURCE_ID = "noaa_psl_oni"
ONI_URL = "https://psl.noaa.gov/data/correlation/oni.data"


def parse_oni_text(
    raw_payload: bytes,
    retrieved_at: datetime,
    revision_number: int = 0,
) -> ParsedBatch:
    vintage = build_vintage(SOURCE_ID, raw_payload, retrieved_at, revision_number)
    observations: list[Observation] = []

    for line in raw_payload.decode("utf-8").splitlines():
        parts = line.split()
        if len(parts) != 13:
            continue
        try:
            year = int(parts[0])
            values = [float(value) for value in parts[1:]]
        except ValueError:
            continue

        if year < 1900:
            continue

        for month, value in enumerate(values, start=1):
            if value <= -90:
                continue
            observed = datetime(year, month, 1, tzinfo=UTC)
            observations.append(
                snapshot_only_observation(
                    observation_id=stable_observation_id(
                        SOURCE_ID,
                        "enso_oni",
                        year,
                        month,
                        vintage.vintage_id,
                    ),
                    feature_id="enso_oni",
                    source_id=SOURCE_ID,
                    entity_id="ONI",
                    value=value,
                    unit="degC_anomaly",
                    observation_start=observed,
                    observation_end=observed,
                    ingested_at=retrieved_at,
                    vintage_id=vintage.vintage_id,
                    quality_flag="pit:current-vintage-snapshot-only",
                )
            )

    return ParsedBatch(vintage=vintage, observations=tuple(observations))
