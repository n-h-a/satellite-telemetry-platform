from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AlertRead(BaseModel):
    id: int
    rule_id: int
    reading_id: int
    source_id: str
    metric: str
    observed_value: float
    message: str
    severity: str
    acknowledged: bool
    triggered_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class TelemetryCreate(BaseModel):
    source_id: str
    metric: str
    value: float
    unit: str
    timestamp: Optional[datetime] = None

class TelemetryRead(BaseModel):
    id: int
    source_id: str
    metric: str
    value: float
    unit: str
    timestamp: Optional[datetime] = None
    received_at: datetime

    model_config = ConfigDict(from_attributes=True)