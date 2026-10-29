"""
test_blockchain_anchor.py — Unit tests for cryptographic hashing & anchor service.
"""
import os
from datetime import datetime
import pytest

from backend.app.blockchain.anchor_service import AnchorService, compute_keccak256
from backend.app.blockchain.chain_client import ChainClient
from backend.app.services.storage import init_db


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    db_file = tmp_path / "test_chain.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"
    init_db(str(db_file))
    yield
    if "DATABASE_URL" in os.environ:
        del os.environ["DATABASE_URL"]


def test_keccak256_computation():
    payload = {"symbol": "AAPL", "close": 150.0}
    digest = compute_keccak256(payload)
    assert digest.startswith("0x")
    assert len(digest) == 66  # 0x + 64 hex chars


def test_anchor_price():
    client = ChainClient("http://localhost:0", chain_id=11155111)
    service = AnchorService(client)
    now = datetime(2026, 9, 1, 12, 0, 0)

    res = service.anchor_price("AAPL", now, 150.0, 155.0, 149.0, 152.5, 100000)
    assert res["symbol"] == "AAPL"
    assert res["anchored"] is True
    assert "data_hash" in res
    assert "tx_hash" in res

    anchors = service.list_anchors("AAPL")
    assert len(anchors) == 1
    assert anchors[0]["anchor_type"] == "price"


def test_anchor_prediction():
    client = ChainClient("http://localhost:0", chain_id=11155111)
    service = AnchorService(client)
    now = datetime(2026, 9, 1, 12, 0, 0)

    res = service.anchor_prediction("AAPL", "5m", "1m", now, 0.02, 153.0, 149.0, 155.0, "mvp_v1")
    assert res["symbol"] == "AAPL"
    assert res["horizon"] == "5m"
    assert res["anchored"] is True

    anchors = service.list_anchors("AAPL")
    assert len(anchors) == 1
    assert anchors[0]["anchor_type"] == "prediction"

    # Verify repeated anchor calls generate unique transaction hashes without duplicate key error
    res2 = service.anchor_prediction("AAPL", "5m", "1m", now, 0.02, 153.0, 149.0, 155.0, "mvp_v1")
    assert res2["anchored"] is True
    assert res2["tx_hash"] != res["tx_hash"]
    all_anchors = service.list_anchors("AAPL")
    assert len(all_anchors) == 2
