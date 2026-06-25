from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, services


def _los_rule(name="Missed contact warning", threshold=120.0, severity="WARNING"):
    return models.AlertRule(
        name=name,
        metric="last_contact_age_min",
        operator=">",
        threshold_value=threshold,
        severity=severity,
        subsystem="Communications",
    )


def _reading(source_id="SAT-1", age_minutes=10):
    return models.TelemetryReading(
        source_id=source_id,
        metric="battery_soc_percent",
        value=50.0,
        unit="%",
        received_at=datetime.now(timezone.utc) - timedelta(minutes=age_minutes),
    )


def test_los_fires_when_age_exceeds_threshold(db: Session):
    rule = _los_rule(threshold=120.0)
    reading = _reading(age_minutes=150)
    db.add_all([rule, reading])
    db.flush()

    services.run_los_check(db)
    db.flush()

    alert = db.scalar(select(models.Alert).where(models.Alert.source_id == "SAT-1"))
    assert alert is not None
    assert alert.severity == "WARNING"
    assert alert.metric == "last_contact_age_min"
    assert alert.reading_id == reading.id


def test_los_does_not_fire_when_contact_is_recent(db: Session):
    rule = _los_rule(threshold=120.0)
    reading = _reading(age_minutes=10)
    db.add_all([rule, reading])
    db.flush()

    services.run_los_check(db)
    db.flush()

    alert = db.scalar(select(models.Alert).where(models.Alert.source_id == "SAT-1"))
    assert alert is None


def test_los_suppresses_duplicate_alert(db: Session):
    rule = _los_rule(threshold=120.0)
    reading = _reading(age_minutes=150)
    db.add_all([rule, reading])
    db.flush()

    services.run_los_check(db)
    db.flush()
    services.run_los_check(db)
    db.flush()

    alerts = db.scalars(select(models.Alert).where(models.Alert.source_id == "SAT-1")).all()
    assert len(alerts) == 1


def test_los_resolves_when_contact_resumes(db: Session):
    rule = _los_rule(threshold=120.0)
    old_reading = _reading(age_minutes=150)
    db.add_all([rule, old_reading])
    db.flush()

    services.run_los_check(db)
    db.flush()

    alert = db.scalar(select(models.Alert).where(models.Alert.source_id == "SAT-1"))
    assert alert is not None
    assert alert.resolved_at is None

    new_reading = _reading(age_minutes=5)
    db.add(new_reading)
    db.flush()

    services.run_los_check(db)
    db.flush()

    db.refresh(alert)
    assert alert.resolved_at is not None


def test_los_fires_warning_and_critical_independently(db: Session):
    rule_warning = _los_rule(name="Missed contact warning", threshold=120.0, severity="WARNING")
    rule_critical = _los_rule(name="Missed contact critical", threshold=240.0, severity="CRITICAL")
    reading = _reading(age_minutes=300)
    db.add_all([rule_warning, rule_critical, reading])
    db.flush()

    services.run_los_check(db)
    db.flush()

    alerts = db.scalars(select(models.Alert).where(models.Alert.source_id == "SAT-1")).all()
    assert len(alerts) == 2
    assert {a.severity for a in alerts} == {"WARNING", "CRITICAL"}


def test_los_skips_when_no_los_rules_exist(db: Session):
    reading = _reading(age_minutes=300)
    db.add(reading)
    db.flush()

    services.run_los_check(db)
    db.flush()

    alerts = db.scalars(select(models.Alert)).all()
    assert len(alerts) == 0


def test_los_skips_when_no_sources_exist(db: Session):
    rule = _los_rule()
    db.add(rule)
    db.flush()

    services.run_los_check(db)
    db.flush()

    alerts = db.scalars(select(models.Alert)).all()
    assert len(alerts) == 0


def test_los_monitors_multiple_sources_independently(db: Session):
    rule = _los_rule(threshold=120.0)
    sat1_reading = _reading(source_id="SAT-1", age_minutes=150)
    sat2_reading = _reading(source_id="SAT-2", age_minutes=10)
    db.add_all([rule, sat1_reading, sat2_reading])
    db.flush()

    services.run_los_check(db)
    db.flush()

    sat1_alert = db.scalar(select(models.Alert).where(models.Alert.source_id == "SAT-1"))
    sat2_alert = db.scalar(select(models.Alert).where(models.Alert.source_id == "SAT-2"))
    assert sat1_alert is not None
    assert sat2_alert is None
