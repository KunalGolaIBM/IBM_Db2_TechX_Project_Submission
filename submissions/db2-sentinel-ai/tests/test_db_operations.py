"""
Unit and integration tests for IBM Db2 database operations in Db2 Sentinel AI.
"""

import pytest
from src.db.connection import get_db_manager
from src.db.schema import initialize_schema
from src.db.seed_data import seed_database
from src.db.queries import (
    get_all_accounts,
    get_all_transactions,
    get_transaction_by_id,
    detect_velocity_and_structuring,
    detect_circular_routing_paths,
    append_audit_trail,
    get_recent_audit_trail,
)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    initialize_schema()
    seed_database(force=True)


def test_schema_and_accounts_seeded():
    accounts = get_all_accounts()
    assert len(accounts) >= 8
    account_ids = [a["ACCOUNT_ID"] for a in accounts]
    assert "ACC-1001" in account_ids
    assert "ACC-1004" in account_ids


def test_transactions_seeded():
    txs = get_all_transactions()
    assert len(txs) >= 8
    tx_ids = [t["TX_ID"] for t in txs]
    assert "TX-STRUCT-01" in tx_ids
    assert "TX-LOOP-01" in tx_ids
    assert "TX-SANCT-01" in tx_ids


def test_get_transaction_by_id():
    tx = get_transaction_by_id("TX-STRUCT-01")
    assert tx is not None
    assert tx["SENDER_ID"] == "ACC-1008"
    assert tx["RECEIVER_ID"] == "ACC-1003"
    assert float(tx["AMOUNT"]) == 9850.00


def test_structuring_detection():
    # ACC-1003 is the beneficiary of multiple sub-threshold wires
    res = detect_velocity_and_structuring("ACC-1003")
    assert res["is_structuring_suspect"] is True
    assert res["sub_threshold_count"] >= 2


def test_circular_routing_detection():
    # ACC-1004 starts the circular loop: ACC-1004 -> ACC-1005 -> ACC-1006 -> ACC-1004
    cycles = detect_circular_routing_paths("ACC-1004", max_depth=4)
    assert len(cycles) > 0
    assert cycles[0]["cycle_detected"] is True
    assert "ACC-1004" in cycles[0]["full_loop"]


def test_audit_trail_integrity():
    sig = append_audit_trail("TestActor", "TEST_ACTION", {"key": "value"})
    assert sig is not None
    assert len(sig) == 64  # SHA-256 hash length

    recent = get_recent_audit_trail(limit=5)
    assert len(recent) > 0
    assert recent[0]["SIGNATURE_HASH"] == sig
