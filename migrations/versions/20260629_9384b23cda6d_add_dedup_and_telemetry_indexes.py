"""add dedup and telemetry indexes

Revision ID: 9384b23cda6d
Revises: a1b2c3d4e5f6
Create Date: 2026-06-29 04:09:29.430249

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9384b23cda6d'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint('uq_alert_rules_name', 'alert_rules', ['name'])
    op.alter_column('alerts', 'message',
               existing_type=sa.VARCHAR(length=300),
               type_=sa.String(length=500),
               existing_nullable=False)
    op.drop_constraint('alerts_reading_id_fkey', 'alerts', type_='foreignkey')
    op.drop_constraint('alerts_rule_id_fkey', 'alerts', type_='foreignkey')
    op.create_foreign_key('alerts_reading_id_fkey', 'alerts', 'telemetry_readings', ['reading_id'], ['id'], ondelete='RESTRICT')
    op.create_foreign_key('alerts_rule_id_fkey', 'alerts', 'alert_rules', ['rule_id'], ['id'], ondelete='RESTRICT')
    op.create_index('ix_alerts_dedup', 'alerts', ['rule_id', 'source_id', 'resolved_at'])
    op.create_index('ix_readings_source_metric', 'telemetry_readings', ['source_id', 'metric'])
    op.create_index('ix_readings_received_at', 'telemetry_readings', [sa.text('received_at DESC')])


def downgrade() -> None:
    op.drop_index('ix_readings_received_at', table_name='telemetry_readings')
    op.drop_index('ix_readings_source_metric', table_name='telemetry_readings')
    op.drop_index('ix_alerts_dedup', table_name='alerts')
    op.drop_constraint('alerts_reading_id_fkey', 'alerts', type_='foreignkey')
    op.drop_constraint('alerts_rule_id_fkey', 'alerts', type_='foreignkey')
    op.create_foreign_key('alerts_reading_id_fkey', 'alerts', 'telemetry_readings', ['reading_id'], ['id'])
    op.create_foreign_key('alerts_rule_id_fkey', 'alerts', 'alert_rules', ['rule_id'], ['id'])
    op.alter_column('alerts', 'message',
               existing_type=sa.String(length=500),
               type_=sa.VARCHAR(length=300),
               existing_nullable=False)
    op.drop_constraint('uq_alert_rules_name', 'alert_rules', type_='unique')
