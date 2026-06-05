from sqlalchemy import select
from sqlalchemy.orm import Session

from app import services
from app import models


def test_check_for_alerts_fires_on_breach(db: Session):
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

    alerts = services.check_for_alerts(reading, db)

    assert len(alerts) == 1
    assert alerts[0].rule_id == rule.id
    assert alerts[0].severity == "CRITICAL"


def test_check_for_alerts_no_alert_when_condition_not_breached(db: Session):
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
        value=25.0,
        unit="%",
    )
    db.add_all([rule, reading])
    db.flush()

    alerts = services.check_for_alerts(reading, db)

    assert len(alerts) == 0


def test_check_for_alerts_suppresses_duplicate(db: Session):
    rule = models.AlertRule(
        name="Low battery critical",
        metric="battery_soc_percent",
        operator="<",
        threshold_value=20.0,
        severity="CRITICAL",
        subsystem="Electrical Power System",
    )
    reading1 = models.TelemetryReading(
        source_id="SAT-1",
        metric="battery_soc_percent",
        value=15.0,
        unit="%",
    )
    reading2 = models.TelemetryReading(
        source_id="SAT-1",
        metric="battery_soc_percent",
        value=14.0,
        unit="%",
    )
    db.add_all([rule, reading1, reading2])
    db.flush()

    alerts1 = services.check_for_alerts(reading1, db)
    db.add_all(alerts1)
    db.flush()

    alerts2 = services.check_for_alerts(reading2, db)

    assert len(alerts1) == 1
    assert len(alerts2) == 0


def test_check_for_alerts_new_alert_after_previous_resolved(db: Session):
    rule = models.AlertRule(
        name="Low battery critical",
        metric="battery_soc_percent",
        operator="<",
        threshold_value=20.0,
        severity="CRITICAL",
        subsystem="Electrical Power System",
    )
    reading1 = models.TelemetryReading(
        source_id="SAT-1",
        metric="battery_soc_percent",
        value=15.0,
        unit="%",
    )
    reading2 = models.TelemetryReading(
        source_id="SAT-1",
        metric="battery_soc_percent",
        value=25.0,
        unit="%",
    )
    reading3 = models.TelemetryReading(
        source_id="SAT-1",
        metric="battery_soc_percent",
        value=14.0,
        unit="%",
    )
    db.add_all([rule, reading1])
    db.flush()

    alerts1 = services.check_for_alerts(reading1, db)
    db.add_all(alerts1)
    db.flush()

    assert len(alerts1) == 1

    db.add(reading2)
    db.flush()
    services.resolve_alerts(reading2, db)
    
    db.add(reading3)
    db.flush()
    alerts3 = services.check_for_alerts(reading3, db)

    assert len(alerts3) == 1


def test_check_for_alerts_disabled_rule_ignored(db: Session):
    rule = models.AlertRule(
        name="Low battery critical",
        metric="battery_soc_percent",
        operator="<",
        threshold_value=20.0,
        severity="CRITICAL",
        subsystem="Electrical Power System",
        enabled=False,
    )
    reading = models.TelemetryReading(
        source_id="SAT-1",
        metric="battery_soc_percent",
        value=15.0,
        unit="%",
    )
    db.add_all([rule, reading])
    db.flush()

    alerts = services.check_for_alerts(reading, db)

    assert len(alerts) == 0


def test_check_for_alerts_multiple_rules_for_same_metric(db: Session):
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
    reading = models.TelemetryReading(
        source_id="SAT-1",
        metric="battery_soc_percent",
        value=25.0,
        unit="%",
    )
    db.add_all([rule1, rule2, reading])
    db.flush()

    alerts = services.check_for_alerts(reading, db)

    assert len(alerts) == 1
    assert alerts[0].severity == "WARNING"


def test_resolve_alerts_resolves_open_alert_when_condition_clears(db: Session):
    rule = models.AlertRule(
        name="Low battery critical",
        metric="battery_soc_percent",
        operator="<",
        threshold_value=20.0,
        severity="CRITICAL",
        subsystem="Electrical Power System",
    )
    reading1 = models.TelemetryReading(
        source_id="SAT-1",
        metric="battery_soc_percent",
        value=15.0,
        unit="%",
    )
    reading2 = models.TelemetryReading(
        source_id="SAT-1",
        metric="battery_soc_percent",
        value=25.0,
        unit="%",
    )
    db.add_all([rule, reading1])
    db.flush()

    alerts = services.check_for_alerts(reading1, db)
    db.add_all(alerts)
    db.flush()

    assert len(alerts) == 1

    db.add(reading2)
    db.flush()
    services.resolve_alerts(reading2, db)

    alert1 = db.scalar(select(models.Alert).where(models.Alert.id==alerts[0].id))
    assert alert1 is not None
    assert alert1.resolved_at is not None


def test_resolve_alerts_does_not_resolve_when_condition_still_holds(db: Session):
    rule = models.AlertRule(
        name="Low battery critical",
        metric="battery_soc_percent",
        operator="<",
        threshold_value=20.0,
        severity="CRITICAL",
        subsystem="Electrical Power System",
    )
    reading1 = models.TelemetryReading(
        source_id="SAT-1",
        metric="battery_soc_percent",
        value=15.0,
        unit="%",
    )
    reading2 = models.TelemetryReading(
        source_id="SAT-1",
        metric="battery_soc_percent",
        value=15.0,
        unit="%",
    )
    db.add_all([rule, reading1])
    db.flush()

    alerts = services.check_for_alerts(reading1, db)
    db.add_all(alerts)
    db.flush()

    assert len(alerts) == 1

    db.add(reading2)
    db.flush()
    services.resolve_alerts(reading2, db)

    alert1 = db.scalar(select(models.Alert).where(models.Alert.id==alerts[0].id))
    assert alert1 is not None
    assert alert1.resolved_at is None


def test_resolve_alerts_does_not_touch_alerts_that_are_already_resolved(db: Session):
    rule = models.AlertRule(
        name="Low battery critical",
        metric="battery_soc_percent",
        operator="<",
        threshold_value=20.0,
        severity="CRITICAL",
        subsystem="Electrical Power System",
    )
    reading1 = models.TelemetryReading(
        source_id="SAT-1",
        metric="battery_soc_percent",
        value=15.0,
        unit="%",
    )
    reading2 = models.TelemetryReading(
        source_id="SAT-1",
        metric="battery_soc_percent",
        value=25.0,
        unit="%",
    )
    reading3 = models.TelemetryReading(
        source_id="SAT-1",
        metric="battery_soc_percent",
        value=30.0,
        unit="%",
    )
    db.add_all([rule, reading1])
    db.flush()

    alerts = services.check_for_alerts(reading1, db)
    db.add_all(alerts)
    db.flush()

    assert len(alerts) == 1

    db.add(reading2)
    db.flush()
    services.resolve_alerts(reading2, db)

    alert1 = db.scalar(select(models.Alert).where(models.Alert.id==alerts[0].id))
    assert alert1 is not None
    assert alert1.resolved_at is not None

    # SQLLite doesn't store timezone info natively, so when db.refresh reloads the value, 
    # it comes back as naive datetime. Strip timezone info so both come back as naive.
    original_resolved_at = alert1.resolved_at.replace(tzinfo=None)

    db.add(reading3)
    db.flush()
    services.resolve_alerts(reading3, db)

    db.refresh(alert1)
    assert alert1.resolved_at == original_resolved_at
