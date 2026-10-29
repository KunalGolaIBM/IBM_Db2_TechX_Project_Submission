"""
test_storage_postgres.py — Unit tests for DB CRUD (bars, predictions, blockchain anchors, oracle prices).
"""
import os
from datetime import datetime, timezone
import pandas as pd
import pytest

from backend.app.services.storage import (
    BarORM,
    BlockchainAnchorORM,
    OraclePriceORM,
    PredictionORM,
    fetch_anchors_for_symbol,
    fetch_bars,
    fetch_latest_oracle_price,
    fetch_latest_prediction,
    init_db,
    insert_blockchain_anchor,
    upsert_bars,
    upsert_oracle_price,
    upsert_prediction,
)


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    db_file = tmp_path / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"
    init_db(str(db_file))
    yield
    if "DATABASE_URL" in os.environ:
        del os.environ["DATABASE_URL"]


def test_upsert_and_fetch_bars():
    ts = datetime(2026, 9, 1, 12, 0, 0)
    df = pd.DataFrame([
        {"open": 100.0, "high": 105.0, "low": 99.0, "close": 103.5, "volume": 1500}
    ], index=[ts])

    count = upsert_bars("dummy", "AAPL", "1m", df)
    assert count == 1

    fetched_df = fetch_bars("dummy", "AAPL", "1m")
    assert not fetched_df.empty
    assert len(fetched_df) == 1
    assert fetched_df.iloc[0]["close"] == 103.5


def test_upsert_and_fetch_prediction():
    now = datetime(2026, 9, 1, 12, 0, 0)
    upsert_prediction(
        "dummy",
        symbol="AAPL",
        timeframe="1m",
        horizon="5m",
        base_ts_utc=now,
        created_ts_utc=now,
        last_close=150.0,
        expected_return=0.02,
        expected_price=153.0,
        p_up=0.65,
        interval_low=149.0,
        interval_high=155.0,
        model_version="mvp_v1",
        model_timestamp_utc=now,
    )

    pred = fetch_latest_prediction("dummy", "AAPL", "1m", "5m")
    assert pred is not None
    assert pred.symbol == "AAPL"
    assert pred.expected_price == 153.0
    assert pred.p_up == 0.65


def test_blockchain_anchors_storage():
    now = datetime(2026, 9, 1, 12, 0, 0)
    insert_blockchain_anchor(
        anchor_type="prediction",
        ref_symbol="AAPL",
        ref_horizon="5m",
        ref_ts_utc=now,
        data_hash="0x123456789abcdef",
        tx_hash="0xtx123456789",
        block_number=18900000,
        chain_id=11155111,
        gas_used=21000,
    )

    anchors = fetch_anchors_for_symbol("AAPL")
    assert len(anchors) == 1
    assert anchors[0].tx_hash == "0xtx123456789"
    assert anchors[0].chain_id == 11155111


def test_oracle_prices_storage():
    now = datetime(2026, 9, 1, 12, 0, 0)
    upsert_oracle_price(
        symbol="ETH",
        oracle_addr="0x694AA1769357215DE4FAC081bf1f309aDC325306",
        price_usd=3450.75,
        round_id=1001,
        block_ts=now,
    )

    record = fetch_latest_oracle_price("ETH")
    assert record is not None
    assert float(record.price_usd) == 3450.75
    assert record.round_id == 1001
