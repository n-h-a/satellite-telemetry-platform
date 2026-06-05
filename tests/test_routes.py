from unittest.mock import MagicMock

import fakeredis
import pytest
from redis import RedisError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.database import get_db, get_redis
from app.main import app as fastapi_app, _telemetry_cache_key, CACHE_TTL
from app.schemas import PaginatedResponse, TelemetryParams, TelemetryRead
from fastapi.testclient import TestClient


def test_post_telemetry_returns_created_reading(client):
    payload = {
        "source_id": "SAT-1",
        "metric": "battery_soc_percent",
        "value": 15.0,
        "unit": "%",
    }
    response = client.post("/telemetry", json=payload)
    
    assert response.status_code == 200
    assert response.json()["source_id"] == "SAT-1"
    assert response.json()["metric"] == "battery_soc_percent"
    assert response.json()["value"] == "15.0000"
    assert response.json()["unit"] == "%"

def test_post_telemetry_fires_end_to_end_when_rule_breached(client, db: Session):
    rule = models.AlertRule(
        name="Low battery critical",
        metric="battery_soc_percent",
        operator="<",
        threshold_value=20.0,
        severity="CRITICAL",
        subsystem="Electrical Power System",
    )

    payload = {
        "source_id": "SAT-1",
        "metric": "battery_soc_percent",
        "value": 15.0,
        "unit": "%",
    }
    db.add(rule)
    db.flush()

    response = client.post("/telemetry", json=payload)

    alert = db.scalar(select(models.Alert).where(models.Alert.severity == "CRITICAL"))
    assert alert is not None
    assert alert.severity == "CRITICAL"

def test_get_telemetry_recent_respects_source_id_and_metric_filters(client, db: Session):
    db.add_all([
        models.TelemetryReading(source_id="SAT-1", metric="battery_soc_percent", value=15.0, unit="%"),
        models.TelemetryReading(source_id="SAT-2", metric="battery_soc_percent", value=15.0, unit="%"),
        models.TelemetryReading(source_id="SAT-2", metric="battery_voltage_v",   value=24.0, unit="V"),
    ])
    db.flush()

    # source_id filter
    resp = client.get("/telemetry/recent", params={"source_id": "SAT-1"})
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["source_id"] == "SAT-1"

    resp = client.get("/telemetry/recent", params={"source_id": "SAT-2"})
    assert resp.json()["total"] == 2
    assert all(item["source_id"] == "SAT-2" for item in resp.json()["items"])

    # metric filter
    resp = client.get("/telemetry/recent", params={"metric": "battery_soc_percent"})
    assert resp.json()["total"] == 2
    assert all(item["metric"] == "battery_soc_percent" for item in resp.json()["items"])

    resp = client.get("/telemetry/recent", params={"metric": "battery_voltage_v"})
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["metric"] == "battery_voltage_v"

    # combined filters
    resp = client.get("/telemetry/recent", params={"source_id": "SAT-2", "metric": "battery_soc_percent"})
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["source_id"] == "SAT-2"
    assert resp.json()["items"][0]["metric"] == "battery_soc_percent"

    resp = client.get("/telemetry/recent", params={"source_id": "SAT-2", "metric": "battery_voltage_v"})
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["source_id"] == "SAT-2"
    assert resp.json()["items"][0]["metric"] == "battery_voltage_v"


def test_get_alerts_respects_severity_and_acknowledged_filters(client, db: Session):
    rule_warning = models.AlertRule(
        name="Low battery warning",
        metric="battery_soc_percent",
        operator="<",
        threshold_value=30.0,
        severity="WARNING",
        subsystem="Electrical Power System",
    )
    rule_critical = models.AlertRule(
        name="Low battery critical",
        metric="battery_soc_percent",
        operator="<",
        threshold_value=20.0,
        severity="CRITICAL",
        subsystem="Electrical Power System",
    )
    reading = models.TelemetryReading(
        source_id="SAT-1",
        metric="battery_soc_percent",
        value=15.0,
        unit="%",
    )
    db.add_all([rule_warning, rule_critical, reading])
    db.flush()

    db.add_all([
        models.Alert(
            rule_id=rule_warning.id, reading_id=reading.id, source_id="SAT-1",
            metric="battery_soc_percent", observed_value=15.0,
            message="test", severity="WARNING", acknowledged=True,
        ),
        models.Alert(
            rule_id=rule_critical.id, reading_id=reading.id, source_id="SAT-1",
            metric="battery_soc_percent", observed_value=15.0,
            message="test", severity="CRITICAL", acknowledged=False,
        ),
    ])
    db.flush()

    # severity filter
    resp = client.get("/alerts", params={"severity": "WARNING"})
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["severity"] == "WARNING"

    resp = client.get("/alerts", params={"severity": "CRITICAL"})
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["severity"] == "CRITICAL"

    # acknowledged filter
    resp = client.get("/alerts", params={"acknowledged": True})
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["acknowledged"] == True

    resp = client.get("/alerts", params={"acknowledged": False})
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["acknowledged"] == False


def test_patch_alert_returns_404_for_missing_alert(client):
    resp = client.patch("/alerts/9999", json={"acknowledged": True})
    assert resp.status_code == 404


def test_post_alert_rule_returns_409_on_duplicate_name(client):
    payload = {
        "name": "Low battery critical",
        "metric": "battery_soc_percent",
        "operator": "<",
        "threshold_value": 20.0,
        "severity": "CRITICAL",
        "subsystem": "Electrical Power System",
    }
    client.post("/alert-rules", json=payload)
    resp = client.post("/alert-rules", json=payload)
    assert resp.status_code == 409


def test_delete_alert_rule_returns_409_when_alerts_reference_it(client, db: Session):
    rule = models.AlertRule(
        name="Low battery critical",
        metric="battery_soc_percent",
        operator="<",
        threshold_value=20.0,
        severity="CRITICAL",
        subsystem="Electrical Power System",
    )
    reading = models.TelemetryReading(
        source_id="SAT-1",
        metric="battery_soc_percent",
        value=15.0,
        unit="%",
    )
    db.add_all([rule, reading])
    db.flush()

    db.add(models.Alert(
        rule_id=rule.id, reading_id=reading.id, source_id="SAT-1",
        metric="battery_soc_percent", observed_value=15.0,
        message="test", severity="CRITICAL",
    ))
    db.flush()

    resp = client.delete(f"/alert-rules/{rule.id}")
    assert resp.status_code == 409


def test_cache_miss_queries_db_and_stores_result(client, db: Session, redis_client):
    db.add(models.TelemetryReading(source_id="SAT-1", metric="battery_soc_percent", value=15.0, unit="%"))
    db.flush()

    resp = client.get("/telemetry/recent")

    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert len(redis_client.keys("telemetry:*")) == 1


def test_cache_hit_returns_cached_data_without_hitting_db(client, db: Session, redis_client):
    params = TelemetryParams()
    key = _telemetry_cache_key(params)
    fabricated = PaginatedResponse[TelemetryRead](items=[], total=999, limit=100, offset=0)
    redis_client.set(key, fabricated.model_dump_json(), ex=CACHE_TTL)

    resp = client.get("/telemetry/recent")

    assert resp.status_code == 200
    assert resp.json()["total"] == 999


def test_cache_falls_back_to_db_when_redis_fails(db: Session):
    broken = MagicMock()
    broken.get.side_effect = RedisError("unavailable")
    broken.set.side_effect = RedisError("unavailable")

    fastapi_app.dependency_overrides[get_db] = lambda: db
    fastapi_app.dependency_overrides[get_redis] = lambda: broken
    c = TestClient(fastapi_app)

    db.add(models.TelemetryReading(source_id="SAT-1", metric="battery_soc_percent", value=15.0, unit="%"))
    db.flush()

    try:
        resp = c.get("/telemetry/recent")
    finally:
        fastapi_app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["total"] == 1



