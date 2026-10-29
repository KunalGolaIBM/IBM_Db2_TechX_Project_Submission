"""001_init_bars_predictions — Initial schema for bars and predictions.

Revision ID: 001_init_bars_predictions
Revises: 
Create Date: 2026-09-01 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '001_init_bars_predictions'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Table: bars ───────────────────────────────────────────────────────────
    op.create_table(
        'bars',
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('timeframe', sa.String(), nullable=False),
        sa.Column('ts_utc', sa.DateTime(), nullable=False),
        sa.Column('open', sa.Float(), nullable=False),
        sa.Column('high', sa.Float(), nullable=False),
        sa.Column('low', sa.Float(), nullable=False),
        sa.Column('close', sa.Float(), nullable=False),
        sa.Column('volume', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('symbol', 'timeframe', 'ts_utc'),
    )

    # ── Table: predictions ────────────────────────────────────────────────────
    op.create_table(
        'predictions',
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('timeframe', sa.String(), nullable=False),
        sa.Column('horizon', sa.String(), nullable=False),
        sa.Column('base_ts_utc', sa.DateTime(), nullable=False),
        sa.Column('created_ts_utc', sa.DateTime(), nullable=False),
        sa.Column('last_close', sa.Float(), nullable=False),
        sa.Column('expected_return', sa.Float(), nullable=False),
        sa.Column('expected_price', sa.Float(), nullable=False),
        sa.Column('p_up', sa.Float(), nullable=True),
        sa.Column('interval_low', sa.Float(), nullable=False),
        sa.Column('interval_high', sa.Float(), nullable=False),
        sa.Column('model_version', sa.String(), nullable=False),
        sa.Column('model_timestamp_utc', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('symbol', 'timeframe', 'horizon', 'base_ts_utc'),
    )


def downgrade() -> None:
    op.drop_table('predictions')
    op.drop_table('bars')
