"""
Unit and Integration Tests for BAKEBOX Choco AI Retrieval, Metadata Pushdown,
Db2 Conversation Buffer Persistence, and Tool Logic.
"""
import json
import os
import sys
import unittest

_pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)

from src.db import get_dbi_connection, get_masked_connection_string
from src.query_engine import (
    ChocoQueryEngine,
    SessionBufferMemory,
    mask_customer_name,
    mask_delivery_address,
    mask_phone_number,
)
from src.retriever import Db2HybridRRFRetriever, SimpleBM25, TextNode, compute_rrf_score
from src.security import order_auth_limiter


class TestBakeboxProduction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = ChocoQueryEngine(use_llm=False)

    def setUp(self):
        conn = get_dbi_connection()
        if hasattr(conn, "reset_state"):
            conn.reset_state()
        order_auth_limiter.reset()

    def test_3way_rrf_scoring_formula(self):
        """Verify 3-way reciprocal rank fusion formula calculation (Dense + BM25 + TF-IDF)."""
        score_top = compute_rrf_score([0, 0, 0], k=60)
        self.assertAlmostEqual(score_top, 3.0 / 61.0, places=4)
        score_dense_only = compute_rrf_score([0, None, None], k=60)
        self.assertAlmostEqual(score_dense_only, 1.0 / 61.0, places=4)
        self.assertGreater(compute_rrf_score([1, 2, 0], k=60), score_dense_only)

    def test_bm25_lexical_scoring(self):
        """Verify Okapi BM25 correctly matches relevant domain tokens."""
        corpus = [
            "Red Velvet Crimson Crumb Crown with vanilla cream cheese",
            "Black Forest Classic Cherry Gateau with chocolate curls",
            "Pineapple Classic Spiral Mirror with fresh fruit chunks",
        ]
        bm25 = SimpleBM25(corpus)
        scores = bm25.score("red velvet")
        self.assertGreater(scores[0], scores[1])
        self.assertGreater(scores[0], scores[2])

    def test_real_engine_intent_routing_cake_purchase(self):
        """Verify real ChocoQueryEngine routes purchase queries to CAKE_RECOMMENDATION."""
        res1 = self.engine.query("I want to order a red velvet cake for anniversary celebration", session_id="test_rec_1")
        self.assertEqual(res1["intent"], "CAKE_RECOMMENDATION")
        self.assertTrue(len(res1["ui_cards"]) > 0)

        res2 = self.engine.query("bina ande wala red velvet cake dikhao", session_id="test_rec_2")
        self.assertEqual(res2["intent"], "CAKE_RECOMMENDATION")
        self.assertTrue(any("Red Velvet" in c["name"] for c in res2["ui_cards"]))

    def test_real_engine_intent_routing_order_tracking(self):
        """Verify real ChocoQueryEngine routes tracking queries to ORDER_TRACKING intents."""
        res1 = self.engine.query("Where is my order? Status please", session_id="test_track_1")
        self.assertEqual(res1["intent"], "ORDER_TRACKING_PROMPT")

        res2 = self.engine.query("Track order #1002", session_id="test_track_2")
        self.assertEqual(res2["intent"], "ORDER_AUTH_REQUIRED")

    def test_real_engine_intent_routing_policy(self):
        """Verify real ChocoQueryEngine routes operational queries to store policy or inquiry."""
        res = self.engine.query("Patties ko reheat kaise karna chahiye?", session_id="test_pol_1")
        self.assertIn(res["intent"], ["GENERAL_INQUIRY", "POLICY_ADVISORY"])
        self.assertIn("tawa", res["reply"].lower())

    def test_real_tool_recommend_cakes_dynamic_and_budget_filter(self):
        """Verify engine.tool_recommend_cakes returns <= 3 cards and honors max_price filter."""
        cards = self.engine.tool_recommend_cakes("red velvet", limit=3)
        self.assertLessEqual(len(cards), 3)
        self.assertGreaterEqual(len(cards), 1)
        budget_cards = self.engine.tool_recommend_cakes("chocolate cake", max_price=300.0, limit=3)
        for c in budget_cards:
            self.assertLessEqual(c["price"], 300.0)

    def test_real_tool_track_live_order_security_and_masking(self):
        """Verify real engine.tool_track_live_order enforces 2FA auth and PII masking."""
        res_no_phone = self.engine.tool_track_live_order(order_id=1002, phone_number=None)
        self.assertEqual(res_no_phone.get("auth_error"), "VERIFICATION_REQUIRED")

        res_wrong_phone = self.engine.tool_track_live_order(order_id=1002, phone_number="9999999999")
        self.assertEqual(res_wrong_phone.get("auth_error"), "PHONE_MISMATCH")

        res_verified = self.engine.tool_track_live_order(order_id=1002, phone_number="+91 9876543210")
        self.assertEqual(res_verified["ORDER_ID"], 1002)
        self.assertIn("*", res_verified["CUSTOMER_NAME"])
        self.assertTrue(res_verified["CUSTOMER_PHONE"].endswith("3210"))
        self.assertIn("Confidential", res_verified["DELIVERY_ADDRESS"])

        # Verify phone-only indexed lookup works cleanly too
        res_phone_only = self.engine.tool_track_live_order(phone_number="98765 43210")
        self.assertIsNotNone(res_phone_only)
        self.assertEqual(res_phone_only["ORDER_ID"], 1002)

    def test_real_tool_track_live_order_like_wildcard_defense(self):
        """Wildcard characters (% or _) in phone cannot bypass parameterized sargable lookup."""
        self.assertEqual(self.engine.tool_track_live_order(order_id=1002, phone_number="%").get("auth_error"), "VERIFICATION_REQUIRED")
        self.assertEqual(self.engine.tool_track_live_order(order_id=1002, phone_number="98%65432_0").get("auth_error"), "VERIFICATION_REQUIRED")
        self.assertEqual(self.engine.tool_track_live_order(order_id=1002, phone_number="9111111111").get("auth_error"), "PHONE_MISMATCH")

    def test_multi_order_offline_support_and_db2_buffer_persistence(self):
        """Verify Order #1104 tracking and BB_USER_CONVERSATION_BUFFER persistence."""
        res_1104 = self.engine.tool_track_live_order(order_id=1104, phone_number="+91 9811223344")
        self.assertEqual(res_1104["ORDER_ID"], 1104)
        self.assertTrue(res_1104["CUSTOMER_PHONE"].endswith("3344"))

        self.engine.query("Show me pineapple cake", session_id="persist_sess_1")
        persisted = self.engine.get_persisted_history("persist_sess_1")
        self.assertEqual(len(persisted), 2)
        self.assertEqual(persisted[0]["ROLE"], "user")
        self.assertEqual(persisted[1]["ROLE"], "assistant")

    def test_session_isolation_and_buffer_memory(self):
        """Verify real SessionBufferMemory maintains strict session isolation."""
        session_a = SessionBufferMemory(session_id="user_alice")
        session_b = SessionBufferMemory(session_id="user_bob")
        session_a.add_turn("I want a red velvet cake", "Here are recommendations", "CAKE_REC")
        session_b.add_turn("Where is my order #1002?", "Order #1002 is baking", "ORDER_TRACKING")
        self.assertIn("red velvet", session_a.get_context_summary())
        self.assertNotIn("1002", session_a.get_context_summary())
        self.assertIn("1002", session_b.get_context_summary())
        self.assertNotIn("red velvet", session_b.get_context_summary())

    def test_session_memory_ttl_expiration(self):
        """Verify inactive sessions expire cleanly after TTL."""
        session = SessionBufferMemory(session_id="test_expiring_session", ttl_seconds=10)
        session.add_turn("Hello", "Hi there", "GREETING")
        self.assertFalse(session.is_expired(current_time=session.last_active + 5))
        self.assertTrue(session.is_expired(current_time=session.last_active + 11))

    def test_real_retriever_dynamic_index_synchronization(self):
        """Verify Db2HybridRRFRetriever.refresh_index synchronizes all 3 channels."""
        nodes = list(self.engine.retriever.corpus_nodes)
        new_node = TextNode(
            text="Special Mathura Peda Delight Cake with saffron pistachios",
            id_="CAKE_PEDA_01",
            metadata={"type": "cake", "sku_id": "BB-PEDA-01", "name": "Mathura Peda Delight", "price": 599.0},
        )
        self.engine.retriever.refresh_index(nodes + [new_node])
        hits = self.engine.retriever.hybrid_retrieve("mathura peda delight", top_k=1)
        self.assertEqual(hits[0].node.id_, "CAKE_PEDA_01")
        # Restore original corpus cleanly
        self.engine.retriever.refresh_index(nodes)

    def test_policy_metadata_filtering_strictness(self):
        """Verify tool_get_store_policy_or_advisory pushes metadata filter & never returns cake SKUs."""
        policy_texts = self.engine.tool_get_store_policy_or_advisory("reheat patties")
        self.assertTrue(len(policy_texts) > 0)
        for p in policy_texts:
            self.assertNotIn("SKU: BB-", p)

    def test_data_directory_and_masked_connection(self):
        """Verify expanded sample catalog (15+ SKUs), sample orders, and connection password masking."""
        cat_path = os.path.join(_pkg_root, "data", "sample_catalog.json")
        ord_path = os.path.join(_pkg_root, "data", "sample_orders.json")
        with open(cat_path, "r", encoding="utf-8") as f:
            cat_data = json.load(f)
        with open(ord_path, "r", encoding="utf-8") as f:
            ord_data = json.load(f)
        self.assertGreaterEqual(len(cat_data), 15)
        self.assertGreaterEqual(len(ord_data), 2)
        self.assertIn("PWD=********", get_masked_connection_string())

    def test_session_hydration_and_deterministic_bom_intent(self):
        """Verify Db2 BB_USER_CONVERSATION_BUFFER hydrates cleared sessions & BOM queries route cleanly offline."""
        self.engine.query("Show me chocolate truffle cake", session_id="hydrate_sess_1")
        self.engine.sessions.clear()
        restored = self.engine.get_or_create_session("hydrate_sess_1")
        self.assertGreaterEqual(len(restored.turns), 1)
        self.assertIn("chocolate truffle", restored.get_context_summary().lower())

        bom_res = self.engine.query("Check BOM ingredients for 2 cakes #1", session_id="bom_chat_sess")
        self.assertEqual(bom_res["intent"], "BOM_AVAILABILITY")
        self.assertEqual(bom_res["bom_details"]["quantity"], 2)
        self.assertTrue(bom_res["bom_details"]["bakeable"])


if __name__ == "__main__":
    unittest.main()
