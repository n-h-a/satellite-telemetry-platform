"""fix index column order, timestamp NULLS LAST, and add effective_ts index

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fix ix_alerts_open_dedup: swap to (source_id, rule_id) so the dedup
    # SELECT that filters on source_id can use the leading column.
    op.drop_index('ix_alerts_open_dedup', table_name='alerts')
    op.create_index(
        'ix_alerts_open_dedup',
        'alerts',
        ['source_id', 'rule_id'],
        unique=True,
        postgresql_where=sa.text('resolved_at IS NULL'),
    )

    # Fix ix_timestamp_desc: add NULLS LAST to match the ORDER BY in
    # get_paginated_telemetry, allowing PostgreSQL to use the index for sorting.
    op.drop_index('ix_timestamp_desc', table_name='telemetry_readings')
    op.create_index(
        'ix_timestamp_desc',
        'telemetry_readings',
        [sa.text('"timestamp" DESC NULLS LAST')],
    )

    # Add a functional index on COALESCE(timestamp, received_at) so the
    # effective_ts time-range filters in get_paginated_telemetry are sargable.
    op.create_index(
        'ix_readings_effective_ts',
        'telemetry_readings',
        [sa.text('COALESCE("timestamp", received_at) DESC')],
    )


def downgrade() -> None:
    op.drop_index('ix_readings_effective_ts', table_name='telemetry_readings')

    op.drop_index('ix_timestamp_desc', table_name='telemetry_readings')
    op.create_index(
        'ix_timestamp_desc',
        'telemetry_readings',
        [sa.text('"timestamp" DESC')],
    )

    op.drop_index('ix_alerts_open_dedup', table_name='alerts')
    op.create_index(
        'ix_alerts_open_dedup',
        'alerts',
        ['rule_id', 'source_id'],
        unique=True,
        postgresql_where=sa.text('resolved_at IS NULL'),
    )
