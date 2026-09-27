from datetime import datetime

from pydantic import BaseModel, Field, model_validator


def _require_aware(value: datetime | None, field_name: str) -> None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError(f"{field_name} must be timezone-aware")


class SourceRegistryEntry(BaseModel):
    source_id: str
    name: str
    publisher: str
    canonical_url: str | None = None
    license: str | None = None
    frequency: str | None = None
    typical_publication_lag_hours: float | None = Field(default=None, ge=0)
    revision_policy: str | None = None
    point_in_time_capable: bool = False
    notes: str | None = None


class FeatureDefinition(BaseModel):
    feature_id: str
    indicator_id: int
    name: str
    unit: str | None = None
    transform: str | None = None
    expected_frequency: str | None = None
    default_half_life_days: float | None = Field(default=None, gt=0)
    source_id: str | None = None


class DataVintage(BaseModel):
    vintage_id: str
    source_id: str
    retrieved_at: datetime
    source_hash: str
    revision_number: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_times(self) -> "DataVintage":
        _require_aware(self.retrieved_at, "retrieved_at")
        return self


class Observation(BaseModel):
    observation_id: str
    feature_id: str
    source_id: str
    entity_id: str | None = None
    value: float | None = None
    unit: str | None = None
    observation_start: datetime | None = None
    observation_end: datetime | None = None
    published_at: datetime | None = None
    available_at: datetime
    ingested_at: datetime
    revised_at: datetime | None = None
    vintage_id: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    quality_flag: str | None = None

    @model_validator(mode="after")
    def validate_time_contract(self) -> "Observation":
        for field_name in (
            "observation_start",
            "observation_end",
            "published_at",
            "available_at",
            "ingested_at",
            "revised_at",
        ):
            _require_aware(getattr(self, field_name), field_name)

        if (
            self.observation_start is not None
            and self.observation_end is not None
            and self.observation_end < self.observation_start
        ):
            raise ValueError("observation_end must be >= observation_start")

        if self.published_at is not None and self.available_at < self.published_at:
            raise ValueError("available_at must be >= published_at")

        if self.ingested_at < self.available_at:
            raise ValueError("ingested_at must be >= available_at")

        if self.revised_at is not None and self.revised_at > self.available_at:
            raise ValueError("revised_at must be <= available_at")

        return self

    @property
    def is_missing(self) -> bool:
        return self.value is None

    @property
    def natural_key(self) -> tuple[str, str | None, datetime | None, datetime | None]:
        return (
            self.feature_id,
            self.entity_id,
            self.observation_start,
            self.observation_end,
        )

    def is_available(self, decision_time: datetime) -> bool:
        _require_aware(decision_time, "decision_time")
        return self.available_at <= decision_time


class FeatureDependency(BaseModel):
    parent_feature_id: str
    child_indicator_id: int
    target_state: str
    attribution_group: str
