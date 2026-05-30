from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
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

@app.post("/telemetry")
def process_readings(t : Telemetry, db : Session = Depends(get_db)):
    # Accept telemetry from satellites
    # Validate it
    # Store it in database
    # Create alert if needed
    ...

@app.get("/telemetry/recent")
def get_readings(db : Session = Depends(get_db)):
    # List recent readings
    ...

@app.get("/sources")
def get_sources(db : Session = Depends(get_db)):
    # List satellites or sensors
    ...

@app.get("/alerts")
def get_alerts(db : Session = Depends(get_db)):
    # List generated alerts
    ...