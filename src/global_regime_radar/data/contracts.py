from datetime import datetime

from pydantic import BaseModel, Field


class Observation(BaseModel):
    feature_id: str
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

    def is_available(self, decision_time: datetime) -> bool:
        return self.available_at <= decision_time
