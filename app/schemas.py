from datetime import datetime
from typing import Optional, Literal
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class AlertRuleCreate(BaseModel):
    name: str
    metric: str
    operator: Literal["<", ">", "<=", ">=", "==", "!="]
    threshold_value: Decimal
    duration_seconds: Optional[int] = None
    severity: Literal["INFO", "WARNING", "CRITICAL"]
    subsystem: str
    enabled: bool = True

class AlertRuleRead(BaseModel):
    id: int
    name: str
    metric: str
    operator: Literal["<", ">", "<=", ">=", "==", "!="]
    threshold_value: Decimal
    duration_seconds: Optional[int] = None
    severity: Literal["INFO", "WARNING", "CRITICAL"]
    subsystem: str
    enabled: bool 

    model_config = ConfigDict(from_attributes=True)

class AlertRuleUpdate(BaseModel):
    metric: Optional[str] = None
    operator: Optional[Literal["<", ">", "<=", ">=", "==", "!="]] = None
    threshold_value: Optional[Decimal] = None
    duration_seconds: Optional[int] = None
    severity: Optional[Literal["INFO", "WARNING", "CRITICAL"]] = None
    subsystem: Optional[str] = None
    enabled: Optional[bool] = None

class AlertRead(BaseModel):
    id: int
    rule_id: int
    reading_id: int
    source_id: str
    metric: str
    observed_value: Decimal
    message: str
    severity: Literal["INFO", "WARNING", "CRITICAL"]
    acknowledged: bool
    triggered_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class TelemetryCreate(BaseModel):
    source_id: str
    metric: str
    value: Decimal
    unit: str
    timestamp: Optional[datetime] = None

class TelemetryRead(BaseModel):
    id: int
    source_id: str
    metric: str
    value: Decimal
    unit: str
    timestamp: Optional[datetime] = None
    received_at: datetime

    model_config = ConfigDict(from_attributes=True)