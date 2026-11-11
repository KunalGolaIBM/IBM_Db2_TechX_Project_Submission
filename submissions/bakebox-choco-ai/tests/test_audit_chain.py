"""
Module: tests/test_audit_chain.py
Tests for Cryptographic SHA-256 Hash-Chained Audit Trail (BB_AUDIT_LOG).
Verifies genesis state, sequential hash continuity, mathematical integrity verification,
and forensic detection of malicious data tampering.
"""
import json
import os
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor

_pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)

from src.db import get_dbi_connection
from src.order_engine import (
    GENESIS_PREV_HASH,
    compute_block_hash,
    append_audit_log,
    verify_audit_chain
)

class TestAuditChain(unittest.TestCase):
    def setUp(self):
        self.conn = get_dbi_connection()
        if hasattr(self.conn, "reset_state"):
            self.conn.reset_state()

    def test_01_genesis_audit_block(self):
        """First record points to the 64-character zero genesis hash."""
        entry = append_audit_log(self.conn, "sess_1", "ORDER_CREATED", {"order_id": 2001, "amount": 649.0})
        self.assertEqual(entry["prev_hash"], GENESIS_PREV_HASH)
        self.assertEqual(len(entry["current_hash"]), 64)

    def test_02_sequential_hash_chaining(self):
        """Subsequent audit logs chain to the current_hash of their immediate predecessor."""
        block_1 = append_audit_log(self.conn, "sess_1", "ORDER_PLACED", {"order_id": 101})
        block_2 = append_audit_log(self.conn, "sess_1", "STOCK_LOCKED", {"cake_id": 1, "qty": 1})
        block_3 = append_audit_log(self.conn, "sess_2", "PAYMENT_CONFIRMED", {"order_id": 101})

        self.assertEqual(block_2["prev_hash"], block_1["current_hash"])
        self.assertEqual(block_3["prev_hash"], block_2["current_hash"])

    def test_03_verify_untampered_audit_chain(self):
        """Clean audit trail with 5 chained entries verifies 100% valid."""
        for i in range(5):
            append_audit_log(self.conn, f"sess_{i}", "ACTION_LOG", {"index": i, "status": "OK"})

        is_valid, bad_id, msg = verify_audit_chain(self.conn)
        self.assertTrue(is_valid)
        self.assertIsNone(bad_id)
        self.assertIsNone(msg)

    def test_04_tampering_payload_modification_detected(self):
        """Malicious admin tampering with payload inside Db2 is immediately caught."""
        append_audit_log(self.conn, "sess_1", "ORDER_CREATED", {"order_id": 501, "amount": 500.0})
        append_audit_log(self.conn, "sess_2", "ORDER_CREATED", {"order_id": 502, "amount": 900.0})

        # Inject malicious payload tamper in block 1: alter amount to 5.0
        row_to_hack = self.conn.tables["BB_AUDIT_LOG"][0]
        tampered_dict = {"amount": 5.0, "order_id": 501}
        row_to_hack["PAYLOAD"] = json.dumps(tampered_dict, sort_keys=True)

        is_valid, bad_id, msg = verify_audit_chain(self.conn)
        self.assertFalse(is_valid, "Audit chain must detect payload modification")
        self.assertEqual(bad_id, 1, "Must pinpoint exact tampered row ID 1")
        self.assertIn("Hash divergence", msg)

    def test_05_tampering_prev_hash_pointer_modification_detected(self):
        """Modifying pointer linkage triggers broken chain pointer alert."""
        append_audit_log(self.conn, "sess_1", "ORDER_CREATED", {"order_id": 701})
        append_audit_log(self.conn, "sess_2", "ORDER_CREATED", {"order_id": 702})

        # Corrupt prev_hash of block 2
        self.conn.tables["BB_AUDIT_LOG"][1]["PREV_HASH"] = "a" * 64

        is_valid, bad_id, msg = verify_audit_chain(self.conn)
        self.assertFalse(is_valid)
        self.assertEqual(bad_id, 2)
        self.assertIn("Broken chain pointer", msg)

    def test_06_tampering_row_deletion_detected(self):
        """Deleting an intermediate row breaks hash link to the successor."""
        append_audit_log(self.conn, "sess_1", "LOG_A", {"seq": 1})
        append_audit_log(self.conn, "sess_2", "LOG_B", {"seq": 2})
        append_audit_log(self.conn, "sess_3", "LOG_C", {"seq": 3})

        # Delete intermediate block (LOG_B)
        del self.conn.tables["BB_AUDIT_LOG"][1]

        is_valid, bad_id, msg = verify_audit_chain(self.conn)
        self.assertFalse(is_valid)
        self.assertIn("Broken chain pointer", msg)

    def test_07_canonical_payload_json_determinism(self):
        """Key order variations produce identical deterministic hash digests."""
        payload_a = json.dumps({"b": 2, "a": 1}, sort_keys=True)
        payload_b = json.dumps({"a": 1, "b": 2}, sort_keys=True)
        self.assertEqual(payload_a, payload_b)
        hash_a = compute_block_hash(GENESIS_PREV_HASH, "s1", "TEST", payload_a)
        hash_b = compute_block_hash(GENESIS_PREV_HASH, "s1", "TEST", payload_b)
        self.assertEqual(hash_a, hash_b)

    def test_08_empty_audit_trail_validity(self):
        """Empty audit log is valid by definition."""
        self.conn.tables["BB_AUDIT_LOG"] = []
        is_valid, bad_id, msg = verify_audit_chain(self.conn)
        self.assertTrue(is_valid)

    def test_09_concurrent_audit_chain_integrity(self):
        """16 concurrent threads appending audit blocks must never fork the SHA-256 chain."""
        def worker(idx: int):
            return append_audit_log(self.conn, f"sess_{idx}", "CONCURRENT_OP", {"seq": idx})

        with ThreadPoolExecutor(max_workers=8) as executor:
            for f in [executor.submit(worker, i) for i in range(16)]:
                f.result()

        self.assertEqual(len(self.conn.tables["BB_AUDIT_LOG"]), 16)
        is_valid, bad_id, msg = verify_audit_chain(self.conn)
        self.assertTrue(is_valid, f"Concurrent audit chain broken at {bad_id}: {msg}")


if __name__ == "__main__":
    unittest.main()
