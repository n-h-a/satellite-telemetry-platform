from unittest.mock import MagicMock

import fakeredis
import pytest
from redis import RedisError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.constants import LOS_METRIC
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
    resp = client.post("/telemetry", json=payload)
    
    assert resp.status_code == 201
    assert resp.json()["source_id"] == "SAT-1"
    assert resp.json()["metric"] == "battery_soc_percent"
    assert resp.json()["value"] == "15.0000"
    assert resp.json()["unit"] == "%"


def test_post_telemetry_rejects_empty_string_fields(client):
    payload = {
        "source_id": "",
        "metric": "",
        "value": 15.0,
        "unit": "",
    }
    resp = client.post("/telemetry", json=payload)
    assert resp.status_code == 422


def test_post_telemetry_rejects_derived_los_metric(client, db: Session):
    payload = {
        "source_id": "SAT-1",
        "metric": LOS_METRIC,
        "value": 10.0,
        "unit": "min",
    }
    resp = client.post("/telemetry", json=payload)

    assert resp.status_code == 422
    assert db.scalars(select(models.TelemetryReading)).all() == []


def test_post_telemetry_returns_201_when_alert_evaluation_fails(client, db: Session, monkeypatch):
    def broken_evaluation(reading, session):
        raise RuntimeError("alert engine exploded")

    monkeypatch.setattr("app.main.check_for_alerts", broken_evaluation)

    resp = client.post("/telemetry", json={
        "source_id": "SAT-1",
        "metric": "battery_soc_percent",
        "value": 15.0,
        "unit": "%",
    })

    assert resp.status_code == 201
    readings = db.scalars(select(models.TelemetryReading)).all()
    assert len(readings) == 1


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

    resp = client.post("/telemetry", json=payload)

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


def test_get_telemetry_recent_allows_equal_time_bounds(client):
    resp = client.get("/telemetry/recent", params={"from_time": "2024-01-01T00:00:00Z", "to_time": "2024-01-01T00:00:00Z"})
    assert resp.status_code == 200


def test_get_telemetry_recent_returns_422_when_from_time_after_to_time(client):
    resp = client.get("/telemetry/recent", params={"from_time": "2024-01-02T00:00:00Z", "to_time": "2024-01-01T00:00:00Z"})
    assert resp.status_code == 422


def test_get_telemetry_recent_total_correct_when_offset_past_end(client, db: Session):
    db.add_all([
        models.TelemetryReading(source_id="SAT-1", metric="battery_soc_percent", value=15.0, unit="%"),
        models.TelemetryReading(source_id="SAT-1", metric="battery_soc_percent", value=16.0, unit="%"),
        models.TelemetryReading(source_id="SAT-1", metric="battery_soc_percent", value=17.0, unit="%"),
    ])
    db.flush()

    resp = client.get("/telemetry/recent", params={"offset": 100})
    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert resp.json()["total"] == 3


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
    first = client.post("/alert-rules", json=payload)
    assert first.status_code == 201

    resp = client.post("/alert-rules", json=payload)
    assert resp.status_code == 409


def test_post_alert_rule_rejects_empty_string_fields(client):
    payload = {
        "name": "",
        "metric": "",
        "operator": "<",
        "threshold_value": 20.0,
        "severity": "CRITICAL",
        "subsystem": "",
    }
    resp = client.post("/alert-rules", json=payload)
    assert resp.status_code == 422


def test_patch_alert_rules_returns_409_on_duplicate_name(client, db: Session):
    rule1 = models.AlertRule(
        name="Low battery critical",
        metric="battery_soc_percent",
        operator="<",
        threshold_value=20.0,
        severity="CRITICAL",
        subsystem="Electrical Power System",
    )
    rule2 = models.AlertRule(
        name="Low battery warning",
        metric="battery_soc_percent",
        operator="<",
        threshold_value=30.0,
        severity="WARNING",
        subsystem="Electrical Power System",
    )
    db.add_all([rule1, rule2])
    db.flush()

    resp = client.patch(f"/alert-rules/{rule2.id}", json={"name": "Low battery critical"})
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

def test_allowed_origins_parsing_strips_whitespace():
    from app.main import _parse_allowed_origins

    assert _parse_allowed_origins("*") == ["*"]
    assert _parse_allowed_origins("https://app.example.com") == ["https://app.example.com"]
    assert _parse_allowed_origins("https://app.example.com, https://admin.example.com") == [
        "https://app.example.com",
        "https://admin.example.com",
    ]


def test_allowed_origins_parsing_drops_empty_entries():
    from app.main import _parse_allowed_origins

    assert _parse_allowed_origins("https://app.example.com,") == ["https://app.example.com"]
    assert _parse_allowed_origins("https://app.example.com,,https://admin.example.com") == [
        "https://app.example.com",
        "https://admin.example.com",
    ]


def test_allowed_origins_parsing_raises_when_no_origins_remain():
    from app.main import _parse_allowed_origins

    for value in ["", " ", ",", ", ,"]:
        with pytest.raises(RuntimeError):
            _parse_allowed_origins(value)


def test_post_telemetry_survives_alert_dedup_conflict(client, db: Session, monkeypatch):
    rule = models.AlertRule(
        name="Low battery critical",
        metric="battery_soc_percent",
        operator="<",
        threshold_value=20.0,
        severity="CRITICAL",
        subsystem="Electrical Power System",
    )
    existing_reading = models.TelemetryReading(
        source_id="SAT-1", metric="battery_soc_percent", value=15.0, unit="%",
    )
    db.add_all([rule, existing_reading])
    db.flush()

    db.add(models.Alert(
        rule_id=rule.id, reading_id=existing_reading.id, source_id="SAT-1",
        metric="battery_soc_percent", observed_value=15.0,
        message="already open", severity="CRITICAL",
    ))
    db.flush()

    # Simulate the race: alert evaluation doesn't see the open alert and
    # returns a duplicate, so both commit attempts hit the unique index.
    def duplicate_check(reading, session):
        return [models.Alert(
            rule_id=rule.id, reading_id=reading.id, source_id=reading.source_id,
            metric=reading.metric, observed_value=reading.value,
            message="duplicate", severity="CRITICAL",
        )]

    monkeypatch.setattr("app.main.check_for_alerts", duplicate_check)

    resp = client.post("/telemetry", json={
        "source_id": "SAT-1",
        "metric": "battery_soc_percent",
        "value": 14.0,
        "unit": "%",
    })

    assert resp.status_code == 201

    readings = db.scalars(select(models.TelemetryReading)).all()
    assert len(readings) == 2

    open_alerts = db.scalars(select(models.Alert).where(models.Alert.resolved_at.is_(None))).all()
    assert len(open_alerts) == 1


def test_get_alerts_total_correct_when_offset_past_end(client, db: Session):
    rule = models.AlertRule(
        name="Low battery critical",
        metric="battery_soc_percent",
        operator="<",
        threshold_value=20.0,
        severity="CRITICAL",
        subsystem="Electrical Power System",
    )
    reading = models.TelemetryReading(
        source_id="SAT-1", metric="battery_soc_percent", value=15.0, unit="%",
    )
    db.add_all([rule, reading])
    db.flush()

    db.add(models.Alert(
        rule_id=rule.id, reading_id=reading.id, source_id="SAT-1",
        metric="battery_soc_percent", observed_value=15.0,
        message="test", severity="CRITICAL",
    ))
    db.flush()

    resp = client.get("/alerts", params={"offset": 100})
    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert resp.json()["total"] == 1


def _rule_with_open_alert(db: Session):
    rule = models.AlertRule(
        name="Low battery critical",
        metric="battery_soc_percent",
        operator="<",
        threshold_value=20.0,
        severity="CRITICAL",
        subsystem="Electrical Power System",
    )
    reading = models.TelemetryReading(
        source_id="SAT-1", metric="battery_soc_percent", value=15.0, unit="%",
    )
    db.add_all([rule, reading])
    db.flush()

    alert = models.Alert(
        rule_id=rule.id, reading_id=reading.id, source_id="SAT-1",
        metric="battery_soc_percent", observed_value=15.0,
        message="test", severity="CRITICAL",
    )
    db.add(alert)
    db.flush()
    return rule, alert


def test_patch_alert_rule_semantic_change_resolves_open_alerts(client, db: Session):
    rule, alert = _rule_with_open_alert(db)

    resp = client.patch(f"/alert-rules/{rule.id}", json={"threshold_value": 10.0})
    assert resp.status_code == 200

    db.refresh(alert)
    assert alert.resolved_at is not None


def test_patch_alert_rule_cosmetic_change_keeps_open_alerts(client, db: Session):
    rule, alert = _rule_with_open_alert(db)

    # Renaming and re-sending the same threshold are not semantic changes.
    resp = client.patch(f"/alert-rules/{rule.id}", json={"name": "Renamed rule", "threshold_value": 20.0})
    assert resp.status_code == 200

    db.refresh(alert)
    assert alert.resolved_at is None


def test_patch_alert_rule_disable_resolves_open_alerts(client, db: Session):
    rule, alert = _rule_with_open_alert(db)

    # Nothing evaluates a disabled rule, so leaving its alerts open would
    # strand them forever.
    resp = client.patch(f"/alert-rules/{rule.id}", json={"enabled": False})
    assert resp.status_code == 200

    db.refresh(alert)
    assert alert.resolved_at is not None


def test_patch_alert_rule_resending_enabled_true_keeps_open_alerts(client, db: Session):
    rule, alert = _rule_with_open_alert(db)

    resp = client.patch(f"/alert-rules/{rule.id}", json={"enabled": True})
    assert resp.status_code == 200

    db.refresh(alert)
    assert alert.resolved_at is None


def test_get_sources_returns_distinct_source_ids(client, db: Session):
    db.add_all([
        models.TelemetryReading(source_id="SAT-1", metric="battery_soc_percent", value=15.0, unit="%"),
        models.TelemetryReading(source_id="SAT-1", metric="battery_voltage_v",   value=24.0, unit="V"),
        models.TelemetryReading(source_id="SAT-2", metric="battery_soc_percent", value=16.0, unit="%"),
    ])
    db.flush()

    resp = client.get("/sources")
    assert resp.status_code == 200
    assert sorted(resp.json()) == ["SAT-1", "SAT-2"]


def test_post_telemetry_rejects_fields_exceeding_column_limits(client):
    base = {"source_id": "SAT-1", "metric": "battery_soc_percent", "value": 15.0, "unit": "%"}

    resp = client.post("/telemetry", json={**base, "source_id": "S" * 101})
    assert resp.status_code == 422

    resp = client.post("/telemetry", json={**base, "unit": "u" * 51})
    assert resp.status_code == 422

    # Numeric(12, 4) holds at most 8 integer digits.
    resp = client.post("/telemetry", json={**base, "value": 123456789.0})
    assert resp.status_code == 422


def test_post_alert_rule_rejects_fields_exceeding_column_limits(client):
    payload = {
        "name": "N" * 101,
        "metric": "battery_soc_percent",
        "operator": "<",
        "threshold_value": 20.0,
        "severity": "CRITICAL",
        "subsystem": "Electrical Power System",
    }
    resp = client.post("/alert-rules", json=payload)
    assert resp.status_code == 422


def test_mutating_endpoints_require_api_key_when_configured(client, monkeypatch):
    monkeypatch.setattr("app.main.API_KEY", "topsecret")
    telemetry = {"source_id": "SAT-1", "metric": "battery_soc_percent", "value": 15.0, "unit": "%"}
    rule = {
        "name": "Low battery critical",
        "metric": "battery_soc_percent",
        "operator": "<",
        "threshold_value": 20.0,
        "severity": "CRITICAL",
        "subsystem": "Electrical Power System",
    }

    assert client.post("/telemetry", json=telemetry).status_code == 401
    assert client.post("/telemetry", json=telemetry, headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.post("/alert-rules", json=rule).status_code == 401
    assert client.patch("/alert-rules/1", json={"enabled": False}).status_code == 401
    assert client.delete("/alert-rules/1").status_code == 401
    assert client.patch("/alerts/1", json={"acknowledged": True}).status_code == 401


def test_correct_api_key_allows_writes_and_reads_stay_open(client, monkeypatch):
    monkeypatch.setattr("app.main.API_KEY", "topsecret")
    telemetry = {"source_id": "SAT-1", "metric": "battery_soc_percent", "value": 15.0, "unit": "%"}

    resp = client.post("/telemetry", json=telemetry, headers={"X-API-Key": "topsecret"})
    assert resp.status_code == 201

    assert client.get("/telemetry/recent").status_code == 200
    assert client.get("/alerts").status_code == 200
    assert client.get("/alert-rules").status_code == 200
    assert client.get("/sources").status_code == 200



