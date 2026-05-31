from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Query
from sqlalchemy import select, case
from sqlalchemy.orm import Session

from app.schemas import AlertRead, TelemetryCreate, TelemetryRead
from app.database import get_db, Base, engine
from app.models import TelemetryReading, Alert
from app.services import check_for_alerts

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/")
def root():
    return {"message": "Welcome."}

@app.post("/telemetry", response_model=TelemetryRead)
def process_readings(t: TelemetryCreate, db: Session = Depends(get_db)):
    reading = TelemetryReading(
        source_id=t.source_id, 
        timestamp=t.timestamp,
        metric=t.metric,
        value=t.value,
        unit=t.unit
    )

    db.add(reading)
    db.commit()
    db.refresh(reading)

    check_for_alerts(reading, db)

    return reading

@app.get("/telemetry/recent", response_model=list[TelemetryRead])
def get_readings(db: Session = Depends(get_db), limit: int = Query(default=100, ge=1, le=100)):
    readings = (
        select(TelemetryReading)
        .order_by(TelemetryReading.timestamp.desc().nulls_last())
        .limit(limit)
    )
    return db.scalars(readings).all()
    
@app.get("/sources", response_model=list[str])
def get_sources(db: Session = Depends(get_db)):
    sources = select(TelemetryReading.source_id).distinct()
    return db.scalars(sources).all()

@app.get("/alerts", response_model=list[AlertRead])
def get_alerts(db: Session = Depends(get_db), limit: int = Query(default=100, ge=1, le=100)):
    alerts = (
        select(Alert)
        .order_by(
            case(
                (Alert.severity == "CRITICAL", 1),
                (Alert.severity == "WARNING", 2),
                (Alert.severity == "INFO", 3)
            ), 
            Alert.triggered_at.desc()
        ).limit(limit)
    )
    return db.scalars(alerts).all()