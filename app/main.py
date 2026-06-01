from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Query, HTTPException
from sqlalchemy import select, case
from sqlalchemy.orm import Session

from app.schemas import AlertRuleCreate, AlertRuleRead, AlertRuleUpdate, AlertRead, TelemetryCreate, TelemetryRead
from app.database import get_db, Base, engine
from app.models import AlertRule, Alert, TelemetryReading
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

@app.post("/alert-rules", response_model=AlertRuleRead)
def create_alert_rule(r: AlertRuleCreate, db: Session = Depends(get_db)):
    rule = AlertRule(**r.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule

@app.get("/alert-rules", response_model=list[AlertRuleRead])
def get_alert_rules(db: Session = Depends(get_db), enabled: Optional[bool] = Query(default=None)):
    rules = select(AlertRule).where(AlertRule.enabled==enabled) if enabled is not None else select(AlertRule)
    return db.scalars(rules).all()

@app.patch("/alert-rules/{id}", response_model=AlertRuleRead)
def update_alert_rule(id: int, r: AlertRuleUpdate, db: Session = Depends(get_db)):
    stmt = select(AlertRule).where(AlertRule.id==id)
    rule = db.scalar(stmt)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Alert rule {id} not found")
    
    new_rule = r.model_dump(exclude_none=True)
    for key, value in new_rule.items():
        setattr(rule, key, value)

    db.commit()
    db.refresh(rule)
    return rule
        

    



