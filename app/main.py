import os
from typing import Optional

from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, delete, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.schemas import (
    PaginatedResponse,
    AlertRuleCreate,
    AlertRuleRead,
    AlertRuleUpdate,
    AlertRead,
    AlertUpdate,
    AlertParams,
    TelemetryCreate,
    TelemetryRead,
    TelemetryParams
)
from app.database import get_db
from app.models import AlertRule, Alert, TelemetryReading
from app.services import (
    check_for_alerts,
    resolve_alerts,
    get_paginated_telemetry,
    get_paginated_alerts
)


app = FastAPI()

_origins = os.getenv("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS = _origins.split(",") if _origins != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")


@app.post("/telemetry", response_model=TelemetryRead)
def process_readings(t: TelemetryCreate, db: Session = Depends(get_db)):
    reading = TelemetryReading(**t.model_dump())
    db.add(reading)
    db.flush()

    alerts = check_for_alerts(reading, db)
    db.add_all(alerts)

    resolve_alerts(reading, db)

    db.commit()
    db.refresh(reading)
    return reading


@app.get("/telemetry/recent", response_model=PaginatedResponse[TelemetryRead])
def get_readings(db: Session = Depends(get_db), params: TelemetryParams = Depends()):
    return get_paginated_telemetry(db, params)


@app.get("/sources", response_model=list[str])
def get_sources(db: Session = Depends(get_db)):
    sources = select(TelemetryReading.source_id).distinct()
    return db.scalars(sources).all()


@app.get("/alerts", response_model=PaginatedResponse[AlertRead])
def get_alerts(db: Session = Depends(get_db), params: AlertParams = Depends()):
    return get_paginated_alerts(db, params)


@app.patch("/alerts/{a_id}", response_model=AlertRead)
def acknowledge_alert(a_id: int, a: AlertUpdate, db: Session = Depends(get_db)):
    alert = db.scalar(select(Alert).where(Alert.id == a_id))
    if alert is None:
        raise HTTPException(
            status_code=404,
            detail=f"Alert {a_id} not found"
        )
    
    alert.acknowledged = a.acknowledged

    db.commit()
    db.refresh(alert)
    return alert
    

@app.post("/alert-rules", response_model=AlertRuleRead)
def create_alert_rule(r: AlertRuleCreate, db: Session = Depends(get_db)):
    rule = AlertRule(**r.model_dump())
    db.add(rule)
    
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Rule name {r.name} already exists"
        )
    
    db.refresh(rule)
    return rule


@app.get("/alert-rules", response_model=list[AlertRuleRead])
def get_alert_rules(db: Session = Depends(get_db), enabled: Optional[bool] = Query(default=None)):
    stmt = select(AlertRule)
    if enabled is not None:
        stmt = stmt.where(AlertRule.enabled == enabled)
    return db.scalars(stmt).all()


@app.patch("/alert-rules/{rule_id}", response_model=AlertRuleRead)
def update_alert_rule(rule_id: int, r: AlertRuleUpdate, db: Session = Depends(get_db)):
    rule = db.scalar(select(AlertRule).where(AlertRule.id == rule_id))
    if rule is None:
        raise HTTPException(
            status_code=404,
            detail=f"Alert rule {rule_id} not found"
        )
    
    new_rule = r.model_dump(exclude_unset=True)
    for key, value in new_rule.items():
        setattr(rule, key, value)

    db.commit()
    db.refresh(rule)
    return rule


@app.delete("/alert-rules/{rule_id}", status_code=204)
def delete_alert_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.scalar(select(AlertRule).where(AlertRule.id == rule_id))
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Alert rule {rule_id} not found")
    
    db.delete(rule)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Rule {rule_id} has associated alerts and cannot be deleted"
        )