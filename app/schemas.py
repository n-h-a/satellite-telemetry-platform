from datetime import datetime
from typing import Optional

from pydantic import BaseModel

class Telemetry(BaseModel):
    source_id: str
    timestamp: Optional[datetime] = None
    metric: str
    value: float
    unit: str