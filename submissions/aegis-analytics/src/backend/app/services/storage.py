"""
storage.py — Database access layer for Aegis Analytics AI.

Supports both:
  - SQLite  (default, dev/fallback): sqlite:///data/app.db
  - PostgreSQL (production):          postgresql+psycopg2://user:pass@host:5432/aegis

The active database is selected via the DATABASE_URL environment variable.
SQLite-specific `sqlite_insert` is replaced with dialect-agnostic SQLAlchemy
`insert(...).on_conflict_do_update(...)` via `postgresql` dialect for Postgres
and fallback prefix detection for SQLite.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


import pandas as pd
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    select,
    text,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

Base = declarative_base()

# ── ORM Models ────────────────────────────────────────────────────────────────

class BarORM(Base):
    __tablename__ = "bars"

    symbol    = Column(String, primary_key=True)
    timeframe = Column(String, primary_key=True)   # '1m' or '1d'
    ts_utc    = Column(DateTime, primary_key=True)

    open   = Column(Float, nullable=False)
    high   = Column(Float, nullable=False)
    low    = Column(Float, nullable=False)
    close  = Column(Float, nullable=False)
    volume = Column(Integer, nullable=True)


class PredictionORM(Base):
    __tablename__ = "predictions"

    symbol    = Column(String,   primary_key=True)
    timeframe = Column(String,   primary_key=True)
    horizon   = Column(String,   primary_key=True)   # '5m', '15m', '60m', '1d'
    base_ts_utc = Column(DateTime, primary_key=True)

    created_ts_utc    = Column(DateTime, nullable=False)
    last_close        = Column(Float,    nullable=False)
    expected_return   = Column(Float,    nullable=False)
    expected_price    = Column(Float,    nullable=False)
    p_up              = Column(Float,    nullable=True)
    interval_low      = Column(Float,    nullable=False)
    interval_high     = Column(Float,    nullable=False)
    model_version     = Column(String,   nullable=False)
    model_timestamp_utc = Column(DateTime, nullable=False)


class BlockchainAnchorORM(Base):
    """Stores on-chain anchoring records for prices and predictions."""
    __tablename__ = "blockchain_anchors"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    anchor_type = Column(String,  nullable=False)       # 'price' or 'prediction'
    ref_symbol  = Column(String,  nullable=True)
    ref_horizon = Column(String,  nullable=True)
    ref_ts_utc  = Column(DateTime, nullable=True)
    data_hash   = Column(String,  nullable=False)       # hex keccak256 hash
    tx_hash     = Column(String,  nullable=False, unique=True)  # Ethereum tx hash
    block_number = Column(BigInteger, nullable=False)
    chain_id    = Column(Integer, nullable=False)        # 137=Polygon, 11155111=Sepolia
    gas_used    = Column(BigInteger, nullable=True)
    created_at  = Column(DateTime, nullable=False, default=_utc_now)


class OraclePriceORM(Base):
    """Stores Chainlink on-chain oracle price snapshots."""
    __tablename__ = "oracle_prices"
    __table_args__ = (UniqueConstraint("symbol", "block_ts", name="uq_oracle_symbol_block_ts"),)

    id          = Column(Integer, primary_key=True, autoincrement=True)
    symbol      = Column(String,  nullable=False)
    oracle_addr = Column(String,  nullable=False)       # Chainlink feed contract address
    price_usd   = Column(Numeric(20, 8), nullable=False)
    round_id    = Column(BigInteger, nullable=True)
    block_ts    = Column(DateTime, nullable=False)
    fetched_at  = Column(DateTime, nullable=False, default=_utc_now)


# ── Engine Factory ─────────────────────────────────────────────────────────────

def _get_database_url() -> str:
    """Return DATABASE_URL from env, defaulting to SQLite."""
    db_path = os.getenv("DATA_DB_PATH", "data/app.db")
    return os.getenv("DATABASE_URL", f"sqlite:///{db_path}")


def _make_engine(database_url: Optional[str] = None):
    """Create a SQLAlchemy engine with dialect-appropriate settings."""
    url = database_url or _get_database_url()
    if url.startswith("sqlite"):
        # SQLite: single-file, check_same_thread=False for multi-threaded FastAPI
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
        )
    else:
        # PostgreSQL / TimescaleDB: connection pooling for production
        return create_engine(
            url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,   # Reconnect on stale connections
        )


def _ensure_parent_dir(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


# ── Database Initialization ────────────────────────────────────────────────────

def init_db(db_path: Optional[str] = None) -> None:
    """
    Create all tables if they do not exist.
    `db_path` is kept for backward compatibility (SQLite path).
    When DATABASE_URL is set, it takes precedence.
    """
    url = _get_database_url()
    if url.startswith("sqlite") and db_path:
        _ensure_parent_dir(db_path)

    engine = _make_engine(url)
    Base.metadata.create_all(engine)
    engine.dispose()


# ── Dialect-agnostic Upsert Helper ───────────────────────────────────────────

def _upsert_stmt(table_cls, records: list[dict], conflict_cols: list[str], update_cols: list[str]):
    """
    Build a dialect-appropriate upsert statement.
    Uses PostgreSQL INSERT ... ON CONFLICT DO UPDATE or SQLite equivalent.
    """
    url = _get_database_url()
    if url.startswith("sqlite"):
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        stmt = sqlite_insert(table_cls).values(records)
        update_dict = {c: getattr(stmt.excluded, c) for c in update_cols}
        return stmt.on_conflict_do_update(
            index_elements=conflict_cols,
            set_=update_dict,
        )
    else:
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = pg_insert(table_cls).values(records)
        update_dict = {c: getattr(stmt.excluded, c) for c in update_cols}
        return stmt.on_conflict_do_update(
            index_elements=conflict_cols,
            set_=update_dict,
        )


# ── Timestamp Normalization ────────────────────────────────────────────────────

def _to_utc_naive(dt: pd.Timestamp) -> datetime:
    ts = pd.Timestamp(dt)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts.to_pydatetime()


# ── Bars CRUD ─────────────────────────────────────────────────────────────────

def upsert_bars(db_path: str, symbol: str, timeframe: str, df: pd.DataFrame) -> int:
    """
    Upsert OHLCV bars into the configured database (SQLite or PostgreSQL).
    `db_path` is accepted for backward compatibility but DATABASE_URL takes priority.
    """
    if df.empty:
        return 0

    engine = _make_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        records = []
        for ts, row in df.iterrows():
            records.append({
                "symbol":    symbol,
                "timeframe": timeframe,
                "ts_utc":    _to_utc_naive(pd.Timestamp(ts)),
                "open":  float(row["Open"]) if "Open" in row else float(row["open"]),
                "high":  float(row["High"]) if "High" in row else float(row["high"]),
                "low":   float(row["Low"])  if "Low"  in row else float(row["low"]),
                "close": float(row["Close"]) if "Close" in row else float(row["close"]),
                "volume": None if pd.isna(row.get("Volume", row.get("volume")))
                          else int(row.get("Volume", row.get("volume"))),
            })

        update_cols = ["open", "high", "low", "close", "volume"]
        stmt = _upsert_stmt(BarORM, records, ["symbol", "timeframe", "ts_utc"], update_cols)
        session.execute(stmt)
        session.commit()
        return len(records)
    finally:
        session.close()
        engine.dispose()


def fetch_bars(
    db_path: str,
    symbol: str,
    timeframe: str,
    start_utc: Optional[datetime] = None,
    end_utc: Optional[datetime] = None,
) -> pd.DataFrame:
    """Fetch OHLCV bars from the configured database."""
    engine = _make_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        q = select(BarORM).where(BarORM.symbol == symbol, BarORM.timeframe == timeframe)
        if start_utc is not None:
            q = q.where(BarORM.ts_utc >= start_utc)
        if end_utc is not None:
            q = q.where(BarORM.ts_utc <= end_utc)
        q = q.order_by(BarORM.ts_utc.asc())
        rows = session.execute(q).scalars().all()

        if not rows:
            return pd.DataFrame()

        data = {
            "open":   [r.open   for r in rows],
            "high":   [r.high   for r in rows],
            "low":    [r.low    for r in rows],
            "close":  [r.close  for r in rows],
            "volume": [r.volume for r in rows],
        }
        index = [r.ts_utc for r in rows]
        return pd.DataFrame(data, index=pd.to_datetime(index))
    finally:
        session.close()
        engine.dispose()


# ── Predictions CRUD ───────────────────────────────────────────────────────────

def upsert_prediction(
    db_path: str,
    *,
    symbol: str,
    timeframe: str,
    horizon: str,
    base_ts_utc: datetime,
    created_ts_utc: datetime,
    last_close: float,
    expected_return: float,
    expected_price: float,
    p_up: Optional[float],
    interval_low: float,
    interval_high: float,
    model_version: str,
    model_timestamp_utc: datetime,
) -> None:
    """Upsert a prediction snapshot into the configured database."""
    engine = _make_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        records = [{
            "symbol":              symbol,
            "timeframe":           timeframe,
            "horizon":             horizon,
            "base_ts_utc":         base_ts_utc,
            "created_ts_utc":      created_ts_utc,
            "last_close":          last_close,
            "expected_return":     expected_return,
            "expected_price":      expected_price,
            "p_up":                p_up,
            "interval_low":        interval_low,
            "interval_high":       interval_high,
            "model_version":       model_version,
            "model_timestamp_utc": model_timestamp_utc,
        }]
        update_cols = [
            "created_ts_utc", "last_close", "expected_return", "expected_price",
            "p_up", "interval_low", "interval_high", "model_version", "model_timestamp_utc",
        ]
        stmt = _upsert_stmt(
            PredictionORM, records,
            ["symbol", "timeframe", "horizon", "base_ts_utc"],
            update_cols,
        )
        session.execute(stmt)
        session.commit()
    finally:
        session.close()
        engine.dispose()


def fetch_latest_prediction(
    db_path: str, symbol: str, timeframe: str, horizon: str
) -> Optional[PredictionORM]:
    """Fetch the most recent prediction snapshot from the database."""
    engine = _make_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        q = (
            select(PredictionORM)
            .where(
                PredictionORM.symbol    == symbol,
                PredictionORM.timeframe == timeframe,
                PredictionORM.horizon   == horizon,
            )
            .order_by(PredictionORM.base_ts_utc.desc())
            .limit(1)
        )
        return session.execute(q).scalars().first()
    finally:
        session.close()
        engine.dispose()


# ── Blockchain Anchors CRUD ───────────────────────────────────────────────────

def insert_blockchain_anchor(
    *,
    anchor_type: str,
    ref_symbol: Optional[str],
    ref_horizon: Optional[str],
    ref_ts_utc: Optional[datetime],
    data_hash: str,
    tx_hash: str,
    block_number: int,
    chain_id: int,
    gas_used: Optional[int] = None,
) -> BlockchainAnchorORM:
    """Persist an on-chain anchoring record to the database, ensuring idempotence."""
    engine = _make_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Check if record with tx_hash already exists to prevent duplicate key errors
        existing = session.execute(
            select(BlockchainAnchorORM).where(BlockchainAnchorORM.tx_hash == tx_hash)
        ).scalar_one_or_none()
        if existing:
            return existing

        record = BlockchainAnchorORM(
            anchor_type=anchor_type,
            ref_symbol=ref_symbol,
            ref_horizon=ref_horizon,
            ref_ts_utc=ref_ts_utc,
            data_hash=data_hash,
            tx_hash=tx_hash,
            block_number=block_number,
            chain_id=chain_id,
            gas_used=gas_used,
            created_at=_utc_now(),
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record
    except Exception as exc:
        session.rollback()
        existing = session.execute(
            select(BlockchainAnchorORM).where(BlockchainAnchorORM.tx_hash == tx_hash)
        ).scalar_one_or_none()
        if existing:
            return existing
        raise exc
    finally:
        session.close()
        engine.dispose()


def fetch_anchors_for_symbol(symbol: str, limit: int = 50) -> list[BlockchainAnchorORM]:
    """Return recent blockchain anchor records for a given symbol."""
    engine = _make_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        q = (
            select(BlockchainAnchorORM)
            .where(BlockchainAnchorORM.ref_symbol == symbol)
            .order_by(BlockchainAnchorORM.created_at.desc())
            .limit(limit)
        )
        return list(session.execute(q).scalars().all())
    finally:
        session.close()
        engine.dispose()


# ── Oracle Prices CRUD ────────────────────────────────────────────────────────

def upsert_oracle_price(
    *,
    symbol: str,
    oracle_addr: str,
    price_usd: float,
    round_id: Optional[int],
    block_ts: datetime,
) -> None:
    """Persist a Chainlink oracle price snapshot."""
    engine = _make_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        records = [{
            "symbol":      symbol,
            "oracle_addr": oracle_addr,
            "price_usd":   price_usd,
            "round_id":    round_id,
            "block_ts":    block_ts,
            "fetched_at":  _utc_now(),
        }]
        update_cols = ["oracle_addr", "price_usd", "round_id", "fetched_at"]
        stmt = _upsert_stmt(OraclePriceORM, records, ["symbol", "block_ts"], update_cols)
        session.execute(stmt)
        session.commit()
    finally:
        session.close()
        engine.dispose()


def fetch_latest_oracle_price(symbol: str) -> Optional[OraclePriceORM]:
    """Return the most recent on-chain oracle price for a symbol."""
    engine = _make_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        q = (
            select(OraclePriceORM)
            .where(OraclePriceORM.symbol == symbol)
            .order_by(OraclePriceORM.block_ts.desc())
            .limit(1)
        )
        return session.execute(q).scalars().first()
    finally:
        session.close()
        engine.dispose()
