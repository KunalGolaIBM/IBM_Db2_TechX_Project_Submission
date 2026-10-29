"""
test_oracle_service.py — Unit tests for Oracle price service.
"""
import os
from datetime import datetime
import pytest

from backend.app.blockchain.chain_client import ChainClient
from backend.app.blockchain.oracle_service import OracleService
from backend.app.services.storage import init_db, upsert_oracle_price


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    db_file = tmp_path / "test_oracle.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"
    init_db(str(db_file))
    yield
    if "DATABASE_URL" in os.environ:
        del os.environ["DATABASE_URL"]


def test_oracle_service_fallback():
    now = datetime(2026, 9, 1, 12, 0, 0)
    upsert_oracle_price(
        symbol="BTC",
        oracle_addr="0x1b44F3514812d835EB1BDB0acB33d3fA3351Ee43",
        price_usd=65000.0,
        round_id=500,
        block_ts=now,
    )

    client = ChainClient("http://localhost:0", chain_id=11155111)
    service = OracleService(client)

    result = service.get_latest_price("BTC")
    assert result["symbol"] == "BTC"
    assert result["price_usd"] == 65000.0
    assert result["source"] == "database_cached"
