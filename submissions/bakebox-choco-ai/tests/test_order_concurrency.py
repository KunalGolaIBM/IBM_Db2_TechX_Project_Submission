"""
Module: tests/test_order_concurrency.py
Tests for IBM Db2 Concurrency, Atomic Row Locks (SELECT FOR UPDATE WITH RS),
Single-UOW ACID Rollback Integrity, End-to-End Atomic Order Placement,
and Multi-Level Recursive Bill-of-Materials (BOM) CTE Queries.
"""
import os
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

_pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)

from src.db import get_dbi_connection
from src.order_engine import (
    call_sp_reserve_cake_stock,
    check_recipe_bom_availability,
    evaluate_refund_request,
    is_cake_bakeable,
    place_verified_order_atomic,
    reserve_cake_stock_atomic,
    verify_audit_chain,
)
from src.security import order_auth_limiter


class TestOrderConcurrencyAndBOM(unittest.TestCase):
    def setUp(self):
        self.conn = get_dbi_connection()
        if hasattr(self.conn, "reset_state"):
            self.conn.reset_state()
        order_auth_limiter.reset()

    def test_01_successful_atomic_stock_reservation(self):
        """Single thread reserving available stock succeeds and decrements count."""
        success = reserve_cake_stock_atomic(self.conn, cake_id=1, quantity=2)
        self.assertTrue(success)
        self.assertEqual(self.conn.tables["BB_CAKES"][1]["STOCK_QTY"], 3)

    def test_02_insufficient_stock_rejection(self):
        """Requesting more stock than available is rejected atomically with no state change."""
        success = reserve_cake_stock_atomic(self.conn, cake_id=2, quantity=10)
        self.assertFalse(success)
        self.assertEqual(self.conn.tables["BB_CAKES"][2]["STOCK_QTY"], 1)

    def test_03_zero_or_negative_quantity_rejection(self):
        """Negative or zero quantity requests are rejected safely."""
        self.assertFalse(reserve_cake_stock_atomic(self.conn, cake_id=1, quantity=0))
        self.assertFalse(reserve_cake_stock_atomic(self.conn, cake_id=1, quantity=-2))

    def test_04_nonexistent_cake_reservation(self):
        """Attempting to reserve nonexistent cake ID fails safely."""
        self.assertFalse(reserve_cake_stock_atomic(self.conn, cake_id=9999, quantity=1))

    def test_05_concurrent_race_condition_stock_collision(self):
        """Two concurrent threads targeting the last Cake #2: EXACTLY ONE succeeds."""
        cake_id = 2
        self.assertEqual(self.conn.tables["BB_CAKES"][cake_id]["STOCK_QTY"], 1)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(reserve_cake_stock_atomic, self.conn, cake_id, 1) for _ in range(2)]
            results = [f.result() for f in futures]

        self.assertEqual(results.count(True), 1, "Exactly one order must succeed")
        self.assertEqual(results.count(False), 1, "Exactly one order must be rejected")
        self.assertEqual(self.conn.tables["BB_CAKES"][cake_id]["STOCK_QTY"], 0)

    def test_06_high_concurrency_multi_buyer_exhaustion(self):
        """5 simultaneous threads competing for 5 units of Cake 1 - all 5 succeed, stock reaches 0."""
        cake_id = 1
        self.conn.tables["BB_CAKES"][cake_id]["STOCK_QTY"] = 5

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(reserve_cake_stock_atomic, self.conn, cake_id, 1) for _ in range(5)]
            results = [f.result() for f in futures]

        self.assertEqual(results.count(True), 5)
        self.assertEqual(self.conn.tables["BB_CAKES"][cake_id]["STOCK_QTY"], 0)
        self.assertFalse(reserve_cake_stock_atomic(self.conn, cake_id, 1))

    def test_07_recursive_bom_sufficient_ingredients(self):
        """Cake 1 ingredients (Khoaa + Cream Cheese + sub-assemblies) are in stock."""
        bom = check_recipe_bom_availability(self.conn, cake_id=1)
        self.assertGreater(len(bom), 0)
        for item in bom:
            self.assertEqual(item["AVAILABILITY"], "IN_STOCK")

        bakeable, missing = is_cake_bakeable(self.conn, cake_id=1)
        self.assertTrue(bakeable)
        self.assertEqual(len(missing), 0)

    def test_08_recursive_bom_depleted_ingredient_detection(self):
        """Cake 2 requires Maraschino Cherries (0.5) while stock is 0.2 -> OUT_OF_STOCK."""
        bom = check_recipe_bom_availability(self.conn, cake_id=2)
        cherry_item = next((it for it in bom if "Cherries" in it["INGREDIENT_NAME"]), None)
        self.assertIsNotNone(cherry_item)
        self.assertEqual(cherry_item["AVAILABILITY"], "OUT_OF_STOCK")

        bakeable, missing = is_cake_bakeable(self.conn, cake_id=2)
        self.assertFalse(bakeable)
        self.assertIn("Maraschino Cherries", missing)

    def test_09_happiness_guarantee_baking_order_refund(self):
        """Order in 'BAKING' state gets 100% refund approved under Happiness Guarantee."""
        res = evaluate_refund_request(self.conn, order_id=1002, reason="Delayed delivery")
        self.assertTrue(res["eligible"])
        self.assertEqual(res["status"], "REFUNDED")
        self.assertEqual(res["amount_refunded"], 649.00)

    def test_10_refund_already_refunded_order_rejection(self):
        """Order already refunded cannot be refunded a second time."""
        evaluate_refund_request(self.conn, order_id=1002, reason="First claim")
        res2 = evaluate_refund_request(self.conn, order_id=1002, reason="Duplicate claim")
        self.assertFalse(res2["eligible"])
        self.assertEqual(res2["status"], "ALREADY_REFUNDED")

    def test_11_stored_procedure_reservation_caller(self):
        """Verify IBM Db2 Stored Procedure caller SP_RESERVE_CAKE_STOCK executes cleanly."""
        self.assertTrue(call_sp_reserve_cake_stock(self.conn, cake_id=1, quantity=1))
        self.assertEqual(self.conn.tables["BB_CAKES"][1]["STOCK_QTY"], 4)

    def test_12_multilevel_recursive_bom_subcomponents(self):
        """Verify multi-level UNION ALL recursive BOM traverses sub-assemblies into raw ingredients."""
        bom = check_recipe_bom_availability(self.conn, cake_id=1)
        names = [item["INGREDIENT_NAME"] for item in bom]
        self.assertIn("Khoaa Base (Eggless)", names)
        self.assertIn("Fresh Milk Solids (Mawa)", names)
        self.assertIn("Whipped Dairy Cream", names)
        mawa = next(it for it in bom if it["INGREDIENT_NAME"] == "Fresh Milk Solids (Mawa)")
        self.assertAlmostEqual(mawa["REQUIRED_QTY"], 0.325, places=3)

    def test_13_end_to_end_atomic_order_bom_and_audit(self):
        """Full ACID order checks BOM, locks stock, creates BB_ORDERS+ITEMS, and writes audit hash."""
        # Cake 2 blocked by BOM shortage even though stock=1
        blocked = place_verified_order_atomic(
            self.conn, cake_id=2, customer_name="Ravi", customer_phone="9876543210", quantity=1
        )
        self.assertFalse(blocked["success"])
        self.assertEqual(blocked["status"], "BOM_INGREDIENT_SHORTAGE")

        # Cake 1 succeeds end-to-end
        ok = place_verified_order_atomic(
            self.conn, cake_id=1, customer_name="Meera Ji", customer_phone="+91 9812345678", quantity=2
        )
        self.assertTrue(ok["success"])
        self.assertEqual(self.conn.tables["BB_CAKES"][1]["STOCK_QTY"], 3)
        self.assertIn(ok["order_id"], self.conn.tables["BB_ORDERS"])
        is_valid, _, _ = verify_audit_chain(self.conn)
        self.assertTrue(is_valid)

    def test_14_acid_rollback_on_mid_transaction_failure(self):
        """If audit write fails mid-refund/order, Db2 ROLLBACK reverts ALL mutations atomically."""
        initial_stock = self.conn.tables["BB_CAKES"][1]["STOCK_QTY"]
        initial_order_count = len(self.conn.tables["BB_ORDERS"])

        with patch("src.order_engine.append_audit_log", side_effect=RuntimeError("Simulated audit failure")):
            with self.assertRaises(RuntimeError):
                place_verified_order_atomic(
                    self.conn, cake_id=1, customer_name="Rollback User", customer_phone="9876512345", quantity=1
                )

        self.assertEqual(self.conn.tables["BB_CAKES"][1]["STOCK_QTY"], initial_stock)
        self.assertEqual(len(self.conn.tables["BB_ORDERS"]), initial_order_count)

    def test_15_bom_quantity_scaling_rejects_excess_qty(self):
        """BOM availability must scale with quantity and block impossible multi-unit orders."""
        bom_large = check_recipe_bom_availability(self.conn, cake_id=1, quantity=30)
        khoaa = next(it for it in bom_large if "Khoaa" in it["INGREDIENT_NAME"])
        self.assertEqual(khoaa["AVAILABILITY"], "OUT_OF_STOCK")

        res = place_verified_order_atomic(
            self.conn, cake_id=1, customer_name="Bulk Buyer", customer_phone="9876543210", quantity=30
        )
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "BOM_INGREDIENT_SHORTAGE")

    def test_16_sequence_order_id_uniqueness_and_weight(self):
        """Concurrent orders allocate unique IDs via SEQ_BB_ORDER_ID and record accurate item weight."""
        def place_cake(cid: int):
            c = get_dbi_connection()
            return place_verified_order_atomic(
                c, cake_id=cid, customer_name=f"Buyer {cid}", customer_phone="+91 9811100022", quantity=1
            )

        with ThreadPoolExecutor(max_workers=3) as executor:
            f1 = executor.submit(place_cake, 1)
            f4 = executor.submit(place_cake, 4)
            f5 = executor.submit(place_cake, 5)
            r1, r4, r5 = f1.result(), f4.result(), f5.result()

        self.assertTrue(r1["success"] and r4["success"] and r5["success"])
        self.assertEqual(len({r1["order_id"], r4["order_id"], r5["order_id"]}), 3)
        self.assertEqual(r1["cake_weight"], "1.0kg")
        self.assertEqual(r5["cake_weight"], "0.15kg")


if __name__ == "__main__":
    unittest.main()
