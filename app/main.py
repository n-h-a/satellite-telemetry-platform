from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Telemetry(BaseModel):
    source_id: str
    timestamp: str
    metric: str
    value: float
    unit: str

@app.get("/")
def root():
    return {"message": "Welcome."}

@app.post("/telemetry")
def process_readings(t : Telemetry):
    ...

@app.get("/telemetry/recent")
def get_readings():
    ...

@app.get("/sources")
def get_sources():
    ...

@app.get("/alerts")
def get_alerts():
    ...