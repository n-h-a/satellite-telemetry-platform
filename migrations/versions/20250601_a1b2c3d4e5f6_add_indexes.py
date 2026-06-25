"""add indexes

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2025-06-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "0000000000000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_metric",
        "alert_rules",
        ["metric"],
        postgresql_where=sa.text("enabled = TRUE"),
    )
    op.create_index(
        "ix_triggered_at_desc",
        "alerts",
        [sa.text("triggered_at DESC")],
    )
    op.create_index(
        "ix_timestamp_desc",
        "telemetry_readings",
        [sa.text("timestamp DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_metric", table_name="alert_rules")
    op.drop_index("ix_triggered_at_desc", table_name="alerts")
    op.drop_index("ix_timestamp_desc", table_name="telemetry_readings")
