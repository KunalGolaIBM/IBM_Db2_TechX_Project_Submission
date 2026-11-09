"""Unit and Db2 Integration tests for 3-way reconciliation and rule engine."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.reconciliation import (
    fetch_reconciliation_summary,
    fetch_line_invoices,
    fetch_line_receipts,
    get_db2_connection,
)
from core.rules import evaluate_rules


def test_six_deterministic_fixtures():
    """Verify all 6 core deterministic procurement fixtures from PASS-08 specification."""

    # FIX-A: Ordered 100; Receipts: 60, 30 (good); Invoice: 100 -> QTY-01 gap 10
    summary_a = {
        "ordered_qty": 100,
        "agreed_unit_price": Decimal("10.00"),
        "receipt_count": 2,
        "total_received_qty": 90,
        "acceptable_received_qty": 90,
        "non_good_received_qty": 0,
        "invoice_count": 1,
        "total_invoiced_qty": 100,
    }
    invoices_a = [{"invoice_no": "INV-A", "billed_unit_price": Decimal("10.00")}]
    receipts_a = [{"condition": "good", "received_qty": 60}, {"condition": "good", "received_qty": 30}]
    findings_a = {f["rule_id"]: f["status"] for f in evaluate_rules(summary_a, invoices_a, receipts_a)}
    assert findings_a["QTY-01"] == "FAIL"  # Invoiced 100 > acceptable 90 (gap 10)
    assert findings_a["QTY-02"] == "PASS"  # Invoiced 100 <= ordered 100
    assert findings_a["DOC-01"] == "PASS"
    assert findings_a["COND-01"] == "PASS"

    # FIX-B: Ordered 100; Receipts: 60, 30 (good); Invoices: 60, 60 -> QTY-01 gap 30, QTY-02 gap 20, MULTI-01
    summary_b = {
        "ordered_qty": 100,
        "agreed_unit_price": Decimal("10.00"),
        "receipt_count": 2,
        "total_received_qty": 90,
        "acceptable_received_qty": 90,
        "non_good_received_qty": 0,
        "invoice_count": 2,
        "total_invoiced_qty": 120,
    }
    invoices_b = [
        {"invoice_no": "INV-B1", "billed_unit_price": Decimal("10.00")},
        {"invoice_no": "INV-B2", "billed_unit_price": Decimal("10.00")},
    ]
    receipts_b = [{"condition": "good", "received_qty": 60}, {"condition": "good", "received_qty": 30}]
    findings_b = {f["rule_id"]: f["status"] for f in evaluate_rules(summary_b, invoices_b, receipts_b)}
    assert findings_b["QTY-01"] == "FAIL"  # 120 > 90 (gap 30)
    assert findings_b["QTY-02"] == "FAIL"  # 120 > 100 (gap 20)
    assert findings_b["MULTI-01"] == "FAIL"  # 2 invoices

    # FIX-C: Ordered 100; Receipts: 80 good, 20 damaged; Invoice: 100 -> QTY-01 gap 20, COND-01 FAIL
    summary_c = {
        "ordered_qty": 100,
        "agreed_unit_price": Decimal("10.00"),
        "receipt_count": 2,
        "total_received_qty": 100,
        "acceptable_received_qty": 80,
        "non_good_received_qty": 20,
        "invoice_count": 1,
        "total_invoiced_qty": 100,
    }
    invoices_c = [{"invoice_no": "INV-C", "billed_unit_price": Decimal("10.00")}]
    receipts_c = [{"condition": "good", "received_qty": 80}, {"condition": "damaged", "received_qty": 20}]
    findings_c = {f["rule_id"]: f["status"] for f in evaluate_rules(summary_c, invoices_c, receipts_c)}
    assert findings_c["QTY-01"] == "FAIL"  # 100 > 80 (gap 20)
    assert findings_c["COND-01"] == "FAIL"  # 20 damaged

    # FIX-D: Ordered 100; No receipts; Invoice: 30 -> DOC-01 FAIL, QTY-01 UNKNOWN
    summary_d = {
        "ordered_qty": 100,
        "agreed_unit_price": Decimal("10.00"),
        "receipt_count": 0,
        "total_received_qty": None,
        "acceptable_received_qty": None,
        "non_good_received_qty": 0,
        "invoice_count": 1,
        "total_invoiced_qty": 30,
    }
    invoices_d = [{"invoice_no": "INV-D", "billed_unit_price": Decimal("10.00")}]
    receipts_d = []
    findings_d = {f["rule_id"]: f["status"] for f in evaluate_rules(summary_d, invoices_d, receipts_d)}
    assert findings_d["DOC-01"] == "FAIL"
    assert findings_d["QTY-01"] == "UNKNOWN"  # Absence of receipts != 0 delivered

    # FIX-E: Ordered 100 at 10.00; Invoice billed at 10.50 (5% over agreed > 3% tolerance) -> PRICE-01 FAIL
    summary_e = {
        "ordered_qty": 100,
        "agreed_unit_price": Decimal("10.00"),
        "receipt_count": 1,
        "total_received_qty": 100,
        "acceptable_received_qty": 100,
        "non_good_received_qty": 0,
        "invoice_count": 1,
        "total_invoiced_qty": 100,
    }
    invoices_e = [{"invoice_no": "INV-E", "billed_unit_price": Decimal("10.50")}]
    receipts_e = [{"condition": "good", "received_qty": 100}]
    findings_e = {f["rule_id"]: f["status"] for f in evaluate_rules(summary_e, invoices_e, receipts_e, price_tolerance=Decimal("0.03"))}
    assert findings_e["PRICE-01"] == "FAIL"

    # FIX-F: Ordered 100 at 10.00; Received 100 good; Invoiced 100 at 10.00 -> All PASS
    summary_f = {
        "ordered_qty": 100,
        "agreed_unit_price": Decimal("10.00"),
        "receipt_count": 1,
        "total_received_qty": 100,
        "acceptable_received_qty": 100,
        "non_good_received_qty": 0,
        "invoice_count": 1,
        "total_invoiced_qty": 100,
    }
    invoices_f = [{"invoice_no": "INV-F", "billed_unit_price": Decimal("10.00")}]
    receipts_f = [{"condition": "good", "received_qty": 100}]
    findings_f = {f["rule_id"]: f["status"] for f in evaluate_rules(summary_f, invoices_f, receipts_f)}
    assert findings_f["DOC-01"] == "PASS"
    assert findings_f["QTY-01"] == "PASS"
    assert findings_f["QTY-02"] == "PASS"
    assert findings_f["QTY-03"] == "PASS"
    assert findings_f["PRICE-01"] == "PASS"
    assert findings_f["COND-01"] == "PASS"
    assert findings_f["MULTI-01"] == "PASS"


def test_2x2_join_trap_avoidance_on_live_db2():
    """Verify on genuine Db2 that CTE pre-aggregation does NOT multiply child rows."""
    conn = get_db2_connection()
    try:
        # Find a PO line in live Db2 that has both multiple receipts and/or multiple invoices
        summaries = fetch_reconciliation_summary(conn)
        assert len(summaries) == 91, f"Expected 91 PO lines, got {len(summaries)}"

        # Check total aggregated quantities across all 91 lines
        total_rec_qty = sum(s["total_received_qty"] for s in summaries if s["total_received_qty"] is not None)
        total_inv_qty = sum(s["total_invoiced_qty"] for s in summaries)

        import ibm_db
        # Direct sum from source tables
        r_stmt = ibm_db.exec_immediate(conn, "SELECT SUM(received_qty) FROM goods_receipts")
        expected_rec = ibm_db.fetch_tuple(r_stmt)[0]
        i_stmt = ibm_db.exec_immediate(conn, "SELECT SUM(invoiced_qty) FROM supplier_invoices")
        expected_inv = ibm_db.fetch_tuple(i_stmt)[0]

        # The aggregated query sum MUST match the table sum exactly
        assert total_rec_qty == expected_rec, f"Aggregated {total_rec_qty} != Table {expected_rec} (Join Multiplication!)"
        assert total_inv_qty == expected_inv, f"Aggregated {total_inv_qty} != Table {expected_inv} (Join Multiplication!)"

    finally:
        import ibm_db
        ibm_db.close(conn)


def test_live_db2_full_reconciliation_rules():
    """Run full reconciliation query and rules on all 91 real Db2 PO lines."""
    conn = get_db2_connection()
    try:
        summaries = fetch_reconciliation_summary(conn)
        assert len(summaries) == 91

        rule_counts = {"PASS": 0, "FAIL": 0, "UNKNOWN": 0}
        total_evaluated = 0

        for s in summaries:
            invoices = fetch_line_invoices(conn, s["po_line_id"])
            receipts = fetch_line_receipts(conn, s["po_line_id"])
            findings = evaluate_rules(s, invoices, receipts)
            assert len(findings) == 7, "Every PO line must evaluate exactly 7 rules"

            for f in findings:
                total_evaluated += 1
                rule_counts[f["status"]] += 1

        print(f"\nLive Db2 Rule Evaluation Stats: {rule_counts} across {total_evaluated} evaluations.")
        assert rule_counts["FAIL"] > 0, "Expected anomalies to be flagged in live dataset"
        assert rule_counts["PASS"] > 0, "Expected compliant cases in live dataset"

    finally:
        import ibm_db
        ibm_db.close(conn)

