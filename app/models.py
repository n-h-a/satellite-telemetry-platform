from typing import Optional
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, Integer, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    metric: Mapped[str] = mapped_column(String(100))
    operator: Mapped[str] = mapped_column(String(3))
    threshold_value: Mapped[float] = mapped_column(Numeric(precision=12, scale=4))
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    severity: Mapped[str] = mapped_column(String(10))
    subsystem: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(Integer, ForeignKey("alert_rules.id"))
    reading_id: Mapped[int] = mapped_column(Integer, ForeignKey("telemetry_readings.id"))
    source_id: Mapped[str] = mapped_column(String(100))
    metric: Mapped[str] = mapped_column(String(100))
    observed_value: Mapped[float] = mapped_column(Numeric(precision=12, scale=4))
    message: Mapped[str] = mapped_column(String(300))
    severity: Mapped[str] = mapped_column(String(10))
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)

class TelemetryReading(Base):
    __tablename__ = "telemetry_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(100))
    metric: Mapped[str] = mapped_column(String(100))
    value: Mapped[float] = mapped_column(Numeric(precision=12, scale=4))
    unit: Mapped[str] = mapped_column(String(50))
    timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    received_at: Mapped[datetime]= mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"<TelemetryReading id={self.id} source={self.source_id!r} metric={self.metric!r} value={self.value}>"