"""002_add_blockchain_tables — Tables for blockchain anchors and oracle prices.

Revision ID: 002_add_blockchain_tables
Revises: 001_init_bars_predictions
Create Date: 2026-09-01 12:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '002_add_blockchain_tables'
down_revision: Union[str, None] = '001_init_bars_predictions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Table: blockchain_anchors ─────────────────────────────────────────────
    op.create_table(
        'blockchain_anchors',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('anchor_type', sa.String(), nullable=False),
        sa.Column('ref_symbol', sa.String(), nullable=True),
        sa.Column('ref_horizon', sa.String(), nullable=True),
        sa.Column('ref_ts_utc', sa.DateTime(), nullable=True),
        sa.Column('data_hash', sa.String(), nullable=False),
        sa.Column('tx_hash', sa.String(), nullable=False),
        sa.Column('block_number', sa.BigInteger(), nullable=False),
        sa.Column('chain_id', sa.Integer(), nullable=False),
        sa.Column('gas_used', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tx_hash'),
    )
    op.create_index('idx_anchors_symbol', 'blockchain_anchors', ['ref_symbol', 'ref_ts_utc'], unique=False)

    # ── Table: oracle_prices ──────────────────────────────────────────────────
    op.create_table(
        'oracle_prices',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('oracle_addr', sa.String(), nullable=False),
        sa.Column('price_usd', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('round_id', sa.BigInteger(), nullable=True),
        sa.Column('block_ts', sa.DateTime(), nullable=False),
        sa.Column('fetched_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('symbol', 'block_ts', name='uq_oracle_symbol_block_ts'),
    )


def downgrade() -> None:
    op.drop_index('idx_anchors_symbol', table_name='blockchain_anchors')
    op.drop_table('oracle_prices')
    op.drop_table('blockchain_anchors')
