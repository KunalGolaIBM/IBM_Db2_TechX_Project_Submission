"""
Module: tests/test_session_memory.py
Tests for Session Isolation, Conversation Buffer Memory, and PII Masking.
Validates that multi-tenant conversations are isolated and context windows are maintained cleanly.
"""
import os
import sys
import unittest
import time

_pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)

from src.query_engine import (
    SessionBufferMemory,
    ChocoQueryEngine,
    mask_customer_name,
    mask_phone_number,
    mask_delivery_address
)

class TestSessionMemoryAndIsolation(unittest.TestCase):
    def setUp(self):
        self.engine = ChocoQueryEngine(use_llm=False)

    def test_01_multi_tenant_session_isolation(self):
        """Conversations in Session A do NOT bleed into Session B."""
        sess_a = self.engine.get_or_create_session("tenant_alpha")
        sess_b = self.engine.get_or_create_session("tenant_beta")

        sess_a.add_turn("Looking for anniversary cake", "Found Red Velvet Heart Love Affair", "CAKE_RECOMMENDATION")
        
        self.assertEqual(len(sess_a.turns), 1)
        self.assertEqual(len(sess_b.turns), 0, "Session B memory must remain empty")

    def test_02_conversation_buffer_retention_across_turns(self):
        """Buffer retains conversational history across multiple turns."""
        sess = self.engine.get_or_create_session("user_history_test")
        sess.add_turn("Hi", "Radhe Radhe! Swagat hai.", "GREETING")
        sess.add_turn("Need eggless cake", "Recommending Eggless Red Velvet and Pineapple", "CAKE_RECOMMENDATION")
        sess.add_turn("What is the price?", "Prices start at Rs 249 for 0.5kg", "PRICE_QUERY")

        self.assertEqual(len(sess.turns), 3)
        summary = sess.get_context_summary()
        self.assertIn("Need eggless cake", summary)
        self.assertIn("What is the price?", summary)

    def test_03_automatic_sliding_window_context_trimming(self):
        """When turns exceed max_turns (5), oldest turns are evicted (FIFO)."""
        sess = SessionBufferMemory(session_id="trim_test", max_turns=5)
        for i in range(1, 8):
            sess.add_turn(f"Query {i}", f"Response {i}", "INTENT")

        self.assertEqual(len(sess.turns), 5)
        # Oldest turns (Query 1 and 2) should have been popped
        queries = [t.user_query for t in sess.turns]
        self.assertNotIn("Query 1", queries)
        self.assertNotIn("Query 2", queries)
        self.assertIn("Query 7", queries)

    def test_04_session_ttl_expiration_detection(self):
        """Session memory detects TTL expiration correctly."""
        sess = SessionBufferMemory(session_id="ttl_test", ttl_seconds=60)
        now = time.time()
        self.assertFalse(sess.is_expired(now))
        # 61 seconds later
        self.assertTrue(sess.is_expired(now + 61))

    def test_05_session_clear(self):
        """Clearing session memory wipes all turns."""
        sess = SessionBufferMemory(session_id="clear_test")
        sess.add_turn("Q1", "A1", "INTENT")
        sess.clear()
        self.assertEqual(len(sess.turns), 0)
        self.assertEqual(sess.get_context_summary(), "")

    def test_06_customer_pii_name_and_phone_masking(self):
        """Customer full name and mobile numbers are strictly masked for privacy."""
        masked_name = mask_customer_name("Rahul Sharma")
        self.assertTrue(masked_name.startswith("R*"))
        self.assertTrue(masked_name.endswith("S*****"))
        self.assertNotIn("Rahul", masked_name)

        masked_phone = mask_phone_number("+91 9876543210")
        self.assertEqual(masked_phone, "+91 ******3210")

    def test_07_customer_pii_address_masking(self):
        """Street level address details are masked while retaining state/locality."""
        addr = "Flat 402, Krishna Heights, Mathura, UP"
        masked = mask_delivery_address(addr)
        self.assertNotIn("Flat 402", masked)
        self.assertIn("Confidential", masked)

    def test_08_concurrent_session_query_isolation(self):
        """Concurrent threads executing queries on separate sessions never cross-contaminate results."""
        from concurrent.futures import ThreadPoolExecutor

        def run_a():
            return self.engine.query("Show me red velvet cake", session_id="concurrent_user_A")

        def run_b():
            return self.engine.query("Check status of order #1002 phone +91 9876543210", session_id="concurrent_user_B")

        with ThreadPoolExecutor(max_workers=2) as pool:
            fa = pool.submit(run_a)
            fb = pool.submit(run_b)
            res_a = fa.result()
            res_b = fb.result()

        self.assertEqual(res_a["intent"], "CAKE_RECOMMENDATION")
        self.assertEqual(res_a["session_id"], "concurrent_user_A")
        self.assertTrue(len(res_a["ui_cards"]) > 0)

        self.assertEqual(res_b["intent"], "ORDER_TRACKING")
        self.assertEqual(res_b["session_id"], "concurrent_user_B")
        self.assertEqual(res_b["ui_cards"], [])


if __name__ == "__main__":
    unittest.main()
