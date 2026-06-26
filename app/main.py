import os
import json
import logging
from typing import Optional
from datetime import datetime, timezone

from redis import Redis, RedisError
from fastapi import FastAPI, Request, HTTPException, Depends, Query
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as PydanticValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
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
from app.database import get_db, get_redis
from app.models import AlertRule, Alert, TelemetryReading
from app.services import (
    check_for_alerts,
    resolve_alerts,
    get_paginated_telemetry,
    get_paginated_alerts
)

class Formatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        formatted_record = {
            "level": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        if record.exc_info is not None:
            formatted_record["exc"] = self.formatException(record.exc_info)
        return json.dumps(formatted_record)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(Formatter())

    root = logging.getLogger()
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    root.handlers = [handler]

    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uv = logging.getLogger(name)
        uv.handlers = []
        uv.propagate = True


app = FastAPI()
configure_logging()

logger = logging.getLogger(__name__)

@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    logger.exception(exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

def _format_validation_errors(errors: list) -> list[dict]:
    return [{"field": error["loc"][-1] if error["loc"] else "body", "message": error["msg"]} for error in errors]

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation error", "errors": _format_validation_errors(exc.errors())}
    )

@app.exception_handler(PydanticValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: PydanticValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation error", "errors": _format_validation_errors(exc.errors())}
    )

def _parse_allowed_origins(value: str) -> list[str]:
    return [origin.strip() for origin in value.split(",")] if value != "*" else ["*"]

ALLOWED_ORIGINS = _parse_allowed_origins(os.getenv("ALLOWED_ORIGINS", "*"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


CACHE_TTL = 30

def _telemetry_cache_key(params: TelemetryParams) -> str:
    return (
        f"telemetry:"
        f"source_id={params.source_id}:"
        f"metric={params.metric}:"
        f"from_time={params.from_time}:"
        f"to_time={params.to_time}:"
        f"limit={params.limit}:"
        f"offset={params.offset}"
    )


@app.get("/")
def root(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")


@app.post("/telemetry", response_model=TelemetryRead, status_code=201)
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
def get_readings(db: Session = Depends(get_db), params: TelemetryParams = Depends(), r: Redis = Depends(get_redis)):
    key = _telemetry_cache_key(params)

    try:
        cached = r.get(key)
        if cached is not None:
            return PaginatedResponse[TelemetryRead].model_validate_json(cached)
    except RedisError as e:
        logger.warning(f"Redis get failed: {e}")

    raw = get_paginated_telemetry(db, params)
    result = PaginatedResponse[TelemetryRead](
        items=[TelemetryRead.model_validate(item, from_attributes=True) for item in raw.items],
        total=raw.total,
        limit=raw.limit,
        offset=raw.offset,
    )

    try:
        r.set(key, result.model_dump_json(), ex=CACHE_TTL)
    except RedisError as e:
        logger.warning(f"Redis set failed: {e}")

    return result


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