"""add unique partial index on open alerts

Revision ID: b2c3d4e5f6a7
Revises: 9384b23cda6d
Create Date: 2026-06-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = '9384b23cda6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'ix_alerts_open_dedup',
        'alerts',
        ['rule_id', 'source_id'],
        unique=True,
        postgresql_where=sa.text('resolved_at IS NULL'),
    )


def downgrade() -> None:
    op.drop_index('ix_alerts_open_dedup', table_name='alerts')
