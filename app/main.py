from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.schemas import Telemetry
from app.database import get_db, Base, engine
from app.models import TelemetryReading

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/")
def root():
    return {"message": "Welcome."}

@app.post("/telemetry", response_model=TelemetryReading)
def process_readings(t : Telemetry, db : Session = Depends(get_db)):
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

    return reading

@app.get("/telemetry/recent", response_model=list[Telemetry])
def get_readings(db : Session = Depends(get_db), limit : int = Query(default=100, ge=1, le=100)):
    readings = (
        select(TelemetryReading)
        .order_by(TelemetryReading.timestamp.desc())
        .limit(limit)
    )

    return db.scalars(readings).all()
    
@app.get("/sources")
def get_sources(db : Session = Depends(get_db)):
    sources = select(TelemetryReading.source_id).distinct()
    return db.scalars(sources).all()

@app.get("/alerts")
def get_alerts(db : Session = Depends(get_db)):
    # List generated alerts
    ...