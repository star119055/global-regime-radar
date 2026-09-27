from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Observation(BaseModel):
    feature_id: str
    value: Optional[float] = None
    unit: Optional[str] = None
    observation_start: Optional[datetime] = None
    observation_end: Optional[datetime] = None
    published_at: Optional[datetime] = None
    available_at: datetime
    ingested_at: datetime
    revised_at: Optional[datetime] = None
    vintage_id: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    quality_flag: Optional[str] = None

    def is_available(self, decision_time: datetime) -> bool:
        return self.available_at <= decision_time
