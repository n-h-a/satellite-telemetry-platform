from datetime import datetime, timezone

from sqlalchemy import String, Integer, Numeric, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TelemetryReading(Base):
    __tablename__ = "telemetry_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(100))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    metric: Mapped[str] = mapped_column(String(100))
    value: Mapped[float] = mapped_column(Numeric(precision=12, scale=4))
    unit: Mapped[str] = mapped_column(String(50))

    def __repr__(self) -> str:
        return f"<TelemetryReading id={self.id} source={self.source_id!r} metric={self.metric!r} value={self.value}>"