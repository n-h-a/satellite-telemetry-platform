import os
import secrets
import logging
from contextlib import asynccontextmanager
from typing import Optional

from redis import Redis, RedisError
from fastapi import FastAPI, Request, HTTPException, Depends, Header, Query
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
from app.constants import LOS_METRIC
from app.database import get_db, get_redis, reset_redis_client
from app.logging_config import configure_logging
from app.models import AlertRule, Alert, TelemetryReading
from app.services import (
    check_for_alerts,
    resolve_alerts,
    resolve_open_alerts_for_rule,
    get_paginated_telemetry,
    get_paginated_alerts
)

@asynccontextmanager
async def _lifespan(_: FastAPI):
    configure_logging()
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uv = logging.getLogger(name)
        uv.handlers = []
        uv.propagate = True
    yield

app = FastAPI(lifespan=_lifespan)
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
        content={"detail": "Validation error", "errors": _format_validation_errors(list(exc.errors()))}
    )

@app.exception_handler(PydanticValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: PydanticValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation error", "errors": _format_validation_errors(exc.errors())}
    )

def _parse_allowed_origins(value: str) -> list[str]:
    if value.strip() == "*":
        return ["*"]
    origins = [origin.strip() for origin in value.split(",") if origin.strip()]
    if not origins:
        raise RuntimeError("ALLOWED_ORIGINS is set but contains no origins")
    return origins

ALLOWED_ORIGINS = _parse_allowed_origins(os.getenv("ALLOWED_ORIGINS", "*"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# When API_KEY is set, mutating endpoints require a matching X-API-Key header;
# read endpoints stay open. When unset (local dev, tests), auth is disabled —
# the deployed instance must set it, since the API is reachable publicly.
API_KEY = os.getenv("API_KEY") or None

def require_api_key(x_api_key: Optional[str] = Header(default=None)):
    if API_KEY is None:
        return
    if x_api_key is None or not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


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


@app.post("/telemetry", response_model=TelemetryRead, status_code=201, dependencies=[Depends(require_api_key)])
def process_readings(t: TelemetryCreate, db: Session = Depends(get_db)):
    if t.metric == LOS_METRIC:
        raise HTTPException(
            status_code=422,
            detail=f"{LOS_METRIC} is derived by the LOS worker and cannot be ingested directly"
        )

    reading = TelemetryReading(**t.model_dump())
    db.add(reading)
    db.commit()

    # The reading is committed before evaluation: neither a dedup conflict with
    # a concurrent request nor a broken alert engine may roll back ingested
    # telemetry, so evaluation failures return 201 rather than 500.
    for _ in range(2):
        try:
            db.add_all(check_for_alerts(reading, db))
            resolve_alerts(reading, db)
            db.commit()
            break
        except IntegrityError:
            # The open alert already exists; the retry re-reads and skips it.
            db.rollback()
        except Exception:
            db.rollback()
            logger.exception(f"Alert evaluation failed for reading {reading.id}; reading is committed, evaluation skipped")
            break
    else:
        logger.warning(f"Alert evaluation conflicted twice for reading {reading.id}; evaluation skipped")

    db.refresh(reading)
    return reading


@app.get("/telemetry/recent", response_model=PaginatedResponse[TelemetryRead])
def get_readings(db: Session = Depends(get_db), params: TelemetryParams = Depends(), r: Redis = Depends(get_redis)):
    key = _telemetry_cache_key(params)

    redis_ok = True

    try:
        cached = r.get(key)
        if cached is not None:
            return PaginatedResponse[TelemetryRead].model_validate_json(cached)
    except RedisError as e:
        reset_redis_client()
        logger.warning(f"Redis get failed: {e}")
        redis_ok = False

    raw = get_paginated_telemetry(db, params)
    result = PaginatedResponse[TelemetryRead](
        items=[TelemetryRead.model_validate(item, from_attributes=True) for item in raw.items],
        total=raw.total,
        limit=raw.limit,
        offset=raw.offset,
    )

    if redis_ok:
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


@app.patch("/alerts/{a_id}", response_model=AlertRead, dependencies=[Depends(require_api_key)])
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
    

@app.post("/alert-rules", response_model=AlertRuleRead, status_code=201, dependencies=[Depends(require_api_key)])
def create_alert_rule(r: AlertRuleCreate, db: Session = Depends(get_db)):
    rule = AlertRule(**r.model_dump())
    db.add(rule)
    
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"A rule with that name already exists"
        )
    
    db.refresh(rule)
    return rule


@app.get("/alert-rules", response_model=list[AlertRuleRead])
def get_alert_rules(db: Session = Depends(get_db), enabled: Optional[bool] = Query(default=None)):
    stmt = select(AlertRule)
    if enabled is not None:
        stmt = stmt.where(AlertRule.enabled == enabled)
    return db.scalars(stmt).all()


@app.patch("/alert-rules/{rule_id}", response_model=AlertRuleRead, dependencies=[Depends(require_api_key)])
def update_alert_rule(rule_id: int, r: AlertRuleUpdate, db: Session = Depends(get_db)):
    rule = db.scalar(select(AlertRule).where(AlertRule.id == rule_id))
    if rule is None:
        raise HTTPException(
            status_code=404,
            detail=f"Alert rule {rule_id} not found"
        )
    
    new_rule = r.model_dump(exclude_unset=True)

    # Open alerts were raised under the rule's previous meaning, so changing
    # what the rule evaluates resolves them rather than leaving them stranded.
    # Disabling does the same: nothing evaluates a disabled rule (the LOS
    # worker skips it entirely), so its open alerts would never auto-resolve.
    semantics_changed = any(
        field in new_rule and getattr(rule, field) != new_rule[field]
        for field in ("metric", "operator", "threshold_value")
    )
    newly_disabled = new_rule.get("enabled") is False and rule.enabled

    for key, value in new_rule.items():
        setattr(rule, key, value)

    if semantics_changed or newly_disabled:
        resolved_count = resolve_open_alerts_for_rule(rule.id, db)
        if resolved_count:
            reason = "disabled" if newly_disabled else "semantics changed"
            logger.info(f"Rule {rule.id} {reason}; resolved {resolved_count} open alert(s)")

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"A rule with that name already exists"
        )
    
    db.refresh(rule)
    return rule


@app.delete("/alert-rules/{rule_id}", status_code=204, dependencies=[Depends(require_api_key)])
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