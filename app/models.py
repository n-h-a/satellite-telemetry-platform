from typing import Optional
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, Boolean, Integer, Numeric, DateTime, ForeignKey, CheckConstraint, Index, false, true, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    metric: Mapped[str] = mapped_column(String(100))
    operator: Mapped[str] = mapped_column(String(3))
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(precision=12, scale=4))
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    severity: Mapped[str] = mapped_column(String(10))
    subsystem: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())

    __table_args__ = (
        CheckConstraint("operator IN ('<', '>', '<=', '>=', '==', '!=')", name="ck_alert_rules_operator"),
        CheckConstraint("severity IN ('INFO', 'WARNING', 'CRITICAL')",    name="ck_alert_rules_severity"),
        Index("ix_alert_rules_metric", metric, postgresql_where=enabled.is_(True)),
    )

class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(Integer, ForeignKey("alert_rules.id", ondelete="RESTRICT"))
    reading_id: Mapped[int] = mapped_column(Integer, ForeignKey("telemetry_readings.id", ondelete="RESTRICT"))
    source_id: Mapped[str] = mapped_column(String(100))
    metric: Mapped[str] = mapped_column(String(100))
    observed_value: Mapped[Decimal] = mapped_column(Numeric(precision=12, scale=4))
    message: Mapped[str] = mapped_column(String(500))
    severity: Mapped[str] = mapped_column(String(10))
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("severity IN ('INFO', 'WARNING', 'CRITICAL')", name="ck_alerts_severity"),
        Index("ix_triggered_at_desc", triggered_at.desc()),
        Index(
            "ix_alerts_open_dedup",
            source_id,
            rule_id,
            unique=True,
            postgresql_where=resolved_at.is_(None),
            sqlite_where=resolved_at.is_(None),
        ),
    )

class TelemetryReading(Base):
    __tablename__ = "telemetry_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(100))
    metric: Mapped[str] = mapped_column(String(100))
    value: Mapped[Decimal] = mapped_column(Numeric(precision=12, scale=4))
    unit: Mapped[str] = mapped_column(String(50))
    timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime]= mapped_column(DateTime(timezone=True), server_default=text("now()"))

    __table_args__ = (
        Index("ix_readings_source_metric", source_id, metric),
        Index("ix_readings_received_at", received_at.desc()),
        Index("ix_readings_source_received_at", source_id, received_at.desc()),
    )

    def __repr__(self) -> str:
        return f"<TelemetryReading id={self.id} source={self.source_id!r} metric={self.metric!r} value={self.value}>"