from typing import Optional, Literal, Generic, TypeVar, Annotated
from decimal import Decimal
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator, AfterValidator


T = TypeVar('T')

def _require_timezone_aware(v: datetime):
    if v.tzinfo is None:
        raise ValueError("datetime must be timezone-aware (e.g. 2024-01-01T00:00:00Z)")
    return v

UTCDatetime = Annotated[datetime, AfterValidator(_require_timezone_aware)]

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int

    model_config = ConfigDict(from_attributes=True)

class AlertRuleCreate(BaseModel):
    name: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    operator: Literal["<", ">", "<=", ">=", "==", "!="]
    threshold_value: Decimal
    duration_seconds: Optional[int] = Field(default=None, description="Duration stored but not evaluated")
    severity: Literal["INFO", "WARNING", "CRITICAL"]
    subsystem: str = Field(min_length=1)
    enabled: bool = True

class AlertRuleRead(BaseModel):
    id: int
    name: str
    metric: str
    operator: Literal["<", ">", "<=", ">=", "==", "!="]
    threshold_value: Decimal
    duration_seconds: Optional[int] = Field(default=None, description="Duration stored but not evaluated")
    severity: Literal["INFO", "WARNING", "CRITICAL"]
    subsystem: str
    enabled: bool

    model_config = ConfigDict(from_attributes=True)

class AlertRuleUpdate(BaseModel):
    name: Optional[str] = Field(min_length=1, default=None)
    metric: Optional[str] = Field(min_length=1, default=None)
    operator: Optional[Literal["<", ">", "<=", ">=", "==", "!="]] = None
    threshold_value: Optional[Decimal] = None
    duration_seconds: Optional[int] = Field(default=None, description="Duration stored but not evaluated")
    severity: Optional[Literal["INFO", "WARNING", "CRITICAL"]] = None
    subsystem: Optional[str] = Field(min_length=1, default=None)
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

class AlertUpdate(BaseModel):
    acknowledged: bool

class AlertParams(BaseModel):
    limit: int = Field(default=100, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    source_id: Optional[str] = Field(default=None, description="Satellite source ID, e.g. SAT-1")
    severity: Optional[Literal["INFO", "WARNING", "CRITICAL"]] = Field(default=None, description="Filter by severity level")
    acknowledged: Optional[bool] = Field(default=None, description="Filter by acknowledgement status")

class TelemetryCreate(BaseModel):
    source_id: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    value: Decimal
    unit: str = Field(min_length=1)
    timestamp: Optional[UTCDatetime] = None

class TelemetryRead(BaseModel):
    id: int
    source_id: str
    metric: str
    value: Decimal
    unit: str
    timestamp: Optional[datetime] = None
    received_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TelemetryParams(BaseModel):
    limit: int = Field(default=100, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    source_id: Optional[str] = Field(default=None, description="Satellite source ID, e.g. SAT-1")
    metric: Optional[str] = Field(default=None, description="Metric name, e.g. battery_voltage_v")
    from_time: Optional[UTCDatetime] = Field(default=None, description="Return readings at or after this timestamp (UTC)")
    to_time: Optional[UTCDatetime] = Field(default=None, description="Return readings at or before this timestamp (UTC)")

    @model_validator(mode="after")
    def validate_time_range(self) -> "TelemetryParams":
        if self.from_time is not None and self.to_time is not None:
            if self.from_time > self.to_time:
                raise ValueError("from_time must not be after to_time")
        return self