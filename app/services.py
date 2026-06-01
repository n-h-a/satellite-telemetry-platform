
import operator
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alert, AlertRule, TelemetryReading


OPERATORS = {
    '>': operator.gt,
    '<': operator.lt,
    '>=': operator.ge,
    '<=': operator.le,
    '==': operator.eq,
    '!=': operator.ne
}

logger = logging.getLogger(__name__)

def check_for_alerts(reading: TelemetryReading, db: Session):
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
        .where(AlertRule.enabled == True)
    )

    alerts = []
    for r in db.scalars(matching_rules).all():
        comp_func = OPERATORS.get(r.operator)
        if comp_func is None:
            logger.warning(f"Rule {r.id} has invalid operator {r.operator}")
            continue

        if comp_func(reading.value, r.threshold_value):
            msg = f"{reading.metric} is {reading.value}, threshold: {r.operator} {r.threshold_value}"
            alerts.append(create_alert(r.id, msg, r.severity))
        
    return alerts

    

    