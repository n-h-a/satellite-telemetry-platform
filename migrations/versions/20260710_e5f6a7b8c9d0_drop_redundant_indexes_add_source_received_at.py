"""drop redundant indexes, rename ix_metric, add (source_id, received_at) index

- ix_alerts_dedup is superseded by the partial unique ix_alerts_open_dedup:
  every query that used it also filters resolved_at IS NULL.
- uq_alert_rules_name duplicates the unique constraint created with the
  alert_rules table (alert_rules_name_key).
- ix_timestamp_desc is unused: sorting and time filters both go through
  COALESCE(timestamp, received_at), served by ix_readings_effective_ts.
- ix_metric renamed to follow the ix_<table>_<cols> convention.
- ix_readings_source_received_at supports the latest-reading-per-source
  join in run_los_check.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index('ix_alerts_dedup', table_name='alerts')
    op.drop_constraint('uq_alert_rules_name', 'alert_rules', type_='unique')
    op.drop_index('ix_timestamp_desc', table_name='telemetry_readings')
    op.execute('ALTER INDEX ix_metric RENAME TO ix_alert_rules_metric')
    op.create_index(
        'ix_readings_source_received_at',
        'telemetry_readings',
        ['source_id', sa.text('received_at DESC')],
    )


def downgrade() -> None:
    op.drop_index('ix_readings_source_received_at', table_name='telemetry_readings')
    op.execute('ALTER INDEX ix_alert_rules_metric RENAME TO ix_metric')
    op.create_index(
        'ix_timestamp_desc',
        'telemetry_readings',
        [sa.text('"timestamp" DESC NULLS LAST')],
    )
    op.create_unique_constraint('uq_alert_rules_name', 'alert_rules', ['name'])
    op.create_index('ix_alerts_dedup', 'alerts', ['rule_id', 'source_id', 'resolved_at'])
