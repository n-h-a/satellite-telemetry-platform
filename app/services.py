
import operator
import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, case, func, update
from sqlalchemy.orm import Session

from app.constants import LOS_METRIC
from app.models import Alert, AlertRule, TelemetryReading
from app.schemas import (
    PaginatedResponse,
    AlertRead,
    AlertParams,
    TelemetryRead,
    TelemetryParams
)


OPERATORS = {
    '>': operator.gt,
    '<': operator.lt,
    '>=': operator.ge,
    '<=': operator.le,
    '==': operator.eq,
    '!=': operator.ne
}

logger = logging.getLogger(__name__)


def check_for_alerts(reading: TelemetryReading, db: Session) -> list[Alert]:
    def create_alert(r_id: int, msg: str, severity: str) -> Alert:
        alert = Alert(
            rule_id=r_id,
            reading_id=reading.id,
            source_id=reading.source_id,
            metric=reading.metric,
            observed_value=reading.value,
            message=msg,
            severity=severity
        )
        return alert

    matching_rules = (
        select(AlertRule)
        .where(AlertRule.metric == reading.metric)
        .where(AlertRule.enabled)
    )

    rules = db.scalars(matching_rules).all()
    open_alerts_map = None

    alerts = []
    for rule in rules:
        comp_func = OPERATORS.get(rule.operator)
        if comp_func is None:
            logger.warning(f"Rule {rule.id} has invalid operator {rule.operator}")
            continue

        if comp_func(reading.value, rule.threshold_value):
            if open_alerts_map is None:
                open_alerts_map = {
                    a.rule_id: a
                    for a in db.scalars(
                        select(Alert).where(
                            Alert.source_id == reading.source_id,
                            Alert.rule_id.in_([r.id for r in rules]),
                            Alert.resolved_at.is_(None)
                        )
                    ).all()
                }
            existing_alert = open_alerts_map.get(rule.id)
            if existing_alert is not None:
                continue

            msg = f"{reading.metric} is {reading.value}, threshold: {rule.operator} {rule.threshold_value}"
            alerts.append(create_alert(rule.id, msg, rule.severity))
            logger.info(f"Alert fired: rule_id={rule.id} source={reading.source_id} metric={reading.metric} value={reading.value} severity={rule.severity}")

    return alerts


def _total_from_rows(rows: list, offset: int, db: Session, model, filters: list) -> int:
    if rows:
        return rows[0].total
    # An empty page with a nonzero offset may just mean the offset overshot
    # the result set; the window count can't tell, so count explicitly.
    if offset:
        return db.scalar(select(func.count()).select_from(model).where(*filters)) or 0
    return 0


def get_paginated_telemetry(db: Session, params: TelemetryParams) -> PaginatedResponse[TelemetryRead]:
    filters = []
    if params.source_id is not None:
        filters.append(TelemetryReading.source_id == params.source_id)
    if params.metric is not None:
        filters.append(TelemetryReading.metric == params.metric)

    effective_ts = func.coalesce(TelemetryReading.timestamp, TelemetryReading.received_at)
    if params.from_time is not None:
        filters.append(effective_ts >= params.from_time)
    if params.to_time is not None:
        filters.append(effective_ts <= params.to_time)

    stmt = (
        select(TelemetryReading, func.count().over().label("total"))
        .where(*filters)
        .order_by(effective_ts.desc())
        .offset(params.offset)
        .limit(params.limit)
    )

    rows = db.execute(stmt).all()
    total = _total_from_rows(rows, params.offset, db, TelemetryReading, filters)
    items = [row[0] for row in rows]

    return PaginatedResponse(
        items = items,
        total = total,
        limit = params.limit,
        offset = params.offset
    )


def get_paginated_alerts(db: Session, params: AlertParams) -> PaginatedResponse[AlertRead]:
    filters = []
    if params.source_id is not None:
        filters.append(Alert.source_id==params.source_id)
    if params.severity is not None:
        filters.append(Alert.severity==params.severity)
    if params.acknowledged is not None:
        filters.append(Alert.acknowledged==params.acknowledged)

    stmt = (
        select(Alert, func.count().over().label("total"))
        .where(*filters)
        .order_by(
            case(
                (Alert.severity == "CRITICAL", 1),
                (Alert.severity == "WARNING", 2),
                (Alert.severity == "INFO", 3)
            ),
            Alert.triggered_at.desc()
        )
        .offset(params.offset)
        .limit(params.limit)
    )

    rows = db.execute(stmt).all()
    total = _total_from_rows(rows, params.offset, db, Alert, filters)
    items = [row[0] for row in rows]

    return PaginatedResponse(
        items = items,
        total = total,
        limit = params.limit,
        offset = params.offset
    )


def run_los_check(db: Session) -> list[Alert]:
    los_rules = db.scalars(
        select(AlertRule)
        .where(AlertRule.metric == LOS_METRIC)
        .where(AlertRule.enabled)
    ).all()

    if not los_rules:
        return []

    latest_per_source = (
        select(
            TelemetryReading.source_id,
            func.max(TelemetryReading.received_at).label("received_at"),
        )
        .group_by(TelemetryReading.source_id)
        .subquery()
    )

    # Ties on received_at break toward the highest id.
    latest_ids = (
        select(func.max(TelemetryReading.id))
        .join(
            latest_per_source,
            (TelemetryReading.source_id == latest_per_source.c.source_id)
            & (TelemetryReading.received_at == latest_per_source.c.received_at),
        )
        .group_by(TelemetryReading.source_id)
    )

    latest_readings = {
        r.source_id: r
        for r in db.scalars(select(TelemetryReading).where(TelemetryReading.id.in_(latest_ids))).all()
    }

    source_ids = latest_readings.keys()

    open_alerts_map = {
        (a.source_id, a.rule_id): a
        for a in db.scalars(
            select(Alert).where(
                Alert.source_id.in_(list(source_ids)),
                Alert.rule_id.in_([r.id for r in los_rules]),
                Alert.resolved_at.is_(None)
            )
        ).all()
    }

    now = datetime.now(timezone.utc)
    alerts = []

    for source_id in source_ids:
        last_reading = latest_readings[source_id]

        received_at = last_reading.received_at
        if received_at.tzinfo is None:
            received_at = received_at.replace(tzinfo=timezone.utc)

        age_min = (now - received_at).total_seconds() / 60

        for rule in los_rules:
            comp_func = OPERATORS.get(rule.operator)
            if comp_func is None:
                logger.warning(f"Rule {rule.id} has invalid operator {rule.operator}")
                continue

            existing_alert = open_alerts_map.get((source_id, rule.id))

            if comp_func(age_min, float(rule.threshold_value)):
                if existing_alert is None:
                    msg = f"{LOS_METRIC} is {age_min:.1f}, threshold: {rule.operator} {rule.threshold_value}"
                    alerts.append(Alert(
                        rule_id=rule.id,
                        reading_id=last_reading.id,
                        source_id=source_id,
                        metric=LOS_METRIC,
                        observed_value=Decimal(str(round(age_min, 4))),
                        message=msg,
                        severity=rule.severity,
                    ))
                    logger.info(f"LOS alert fired: rule_id={rule.id} source={source_id} age_min={age_min:.1f} severity={rule.severity}")
            else:
                if existing_alert is not None:
                    existing_alert.resolved_at = now
                    logger.info(f"LOS alert resolved: alert_id={existing_alert.id} source={source_id}")

    return alerts


def resolve_open_alerts_for_rule(rule_id: int, db: Session) -> int:
    result = db.execute(
        update(Alert)
        .where(Alert.rule_id == rule_id, Alert.resolved_at.is_(None))
        .values(resolved_at=datetime.now(timezone.utc))
    )
    return result.rowcount


def resolve_alerts(reading: TelemetryReading, db: Session) -> None:
    stmt = (
        select(Alert, AlertRule)
        .join(AlertRule, Alert.rule_id == AlertRule.id)
        .where(
            Alert.source_id == reading.source_id,
            Alert.metric == reading.metric,
            Alert.resolved_at.is_(None)
        )
    )

    for alert, rule in db.execute(stmt).all():
        comp_func = OPERATORS.get(rule.operator)
        if comp_func is None:
            logger.warning(f"Rule {rule.id} has invalid operator {rule.operator}")
            continue

        if not comp_func(reading.value, rule.threshold_value):
            alert.resolved_at = datetime.now(timezone.utc)
            logger.info(f"Alert resolved: alert_id={alert.id} source={alert.source_id} metric={alert.metric}")
