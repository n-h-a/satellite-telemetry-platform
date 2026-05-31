from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class Telemetry(BaseModel):
    source_id: str
    timestamp: Optional[datetime] = None
    metric: str
    value: float
    unit: str

    model_config = ConfigDict(from_attributes=True)