"""initial schema

Revision ID: 0000000000000
Revises:
Create Date: 2025-06-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0000000000000"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "alert_rules",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("metric", sa.String(100), nullable=False),
        sa.Column("operator", sa.String(3), nullable=False),
        sa.Column("threshold_value", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("duration_seconds", sa.Integer),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("subsystem", sa.String(100), nullable=False),
        sa.Column("enabled", sa.Boolean, default=True, server_default=sa.true(), nullable=False),
        sa.CheckConstraint("operator IN ('<', '>', '<=', '>=', '==', '!=')", name="ck_alert_rules_operator"),
        sa.CheckConstraint("severity IN ('INFO', 'WARNING', 'CRITICAL')",    name="ck_alert_rules_severity")
        )
    op.create_table(
        "telemetry_readings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.String(100), nullable=False),
        sa.Column("metric", sa.String(100), nullable=False),
        sa.Column("value", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True)),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
    )
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("rule_id", sa.Integer, sa.ForeignKey("alert_rules.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reading_id", sa.Integer, sa.ForeignKey("telemetry_readings.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_id", sa.String(100), nullable=False),
        sa.Column("metric", sa.String(100), nullable=False),
        sa.Column("observed_value", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("acknowledged", sa.Boolean, default=False, server_default=sa.false(), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("severity IN ('INFO', 'WARNING', 'CRITICAL')", name="ck_alerts_severity")
    )


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_table("telemetry_readings")
    op.drop_table("alert_rules")
