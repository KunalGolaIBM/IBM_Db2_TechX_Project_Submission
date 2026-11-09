"""Deterministic procurement anomaly detection rules for PACT."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Literal

RuleStatus = Literal["PASS", "FAIL", "UNKNOWN"]


def evaluate_rules(
    summary: Dict[str, Any],
    invoices: List[Dict[str, Any]],
    receipts: List[Dict[str, Any]],
    price_tolerance: Decimal = Decimal("0.03"),
) -> List[Dict[str, Any]]:
    """Evaluate 7 deterministic audit rules for a reconciled PO line."""
    findings = []

    ordered_qty = summary["ordered_qty"]
    agreed_price = summary["agreed_unit_price"]
    receipt_count = summary["receipt_count"]
    total_received_qty = summary["total_received_qty"]
    acceptable_received_qty = summary["acceptable_received_qty"]
    non_good_received_qty = summary["non_good_received_qty"]
    invoice_count = summary["invoice_count"]
    total_invoiced_qty = summary["total_invoiced_qty"]

    # Rule 1: DOC-01 (Missing receipt documentation when invoice exists)
    if invoice_count > 0 and receipt_count == 0:
        findings.append({
            "rule_id": "DOC-01",
            "name": "Missing Goods Receipt Documentation",
            "status": "FAIL",
            "severity": "HIGH",
            "details": f"Invoices received ({invoice_count}) but zero goods receipt records exist on file.",
        })
    else:
        findings.append({
            "rule_id": "DOC-01",
            "name": "Missing Goods Receipt Documentation",
            "status": "PASS",
            "severity": "INFO",
            "details": f"Receipt documentation present ({receipt_count} receipts recorded).",
        })

    # Rule 2: QTY-01 (Billed quantity exceeds acceptable received quantity)
    if receipt_count == 0:
        findings.append({
            "rule_id": "QTY-01",
            "name": "Billed Exceeds Acceptable Delivered",
            "status": "UNKNOWN",
            "severity": "HIGH",
            "details": "Cannot verify delivered quantity because no receipt records exist. Distinct from zero delivered.",
        })
    else:
        gap = total_invoiced_qty - acceptable_received_qty
        if gap > 0:
            findings.append({
                "rule_id": "QTY-01",
                "name": "Billed Exceeds Acceptable Delivered",
                "status": "FAIL",
                "severity": "CRITICAL",
                "details": f"Total invoiced quantity ({total_invoiced_qty}) exceeds acceptable received quantity ({acceptable_received_qty}) by {gap} units.",
            })
        else:
            findings.append({
                "rule_id": "QTY-01",
                "name": "Billed Exceeds Acceptable Delivered",
                "status": "PASS",
                "severity": "INFO",
                "details": f"Invoiced quantity ({total_invoiced_qty}) does not exceed acceptable received quantity ({acceptable_received_qty}).",
            })

    # Rule 3: QTY-02 (Cumulative billed quantity exceeds ordered quantity)
    over_order = total_invoiced_qty - ordered_qty
    if over_order > 0:
        findings.append({
            "rule_id": "QTY-02",
            "name": "Cumulative Billed Exceeds Ordered",
            "status": "FAIL",
            "severity": "HIGH",
            "details": f"Cumulative invoiced quantity ({total_invoiced_qty}) exceeds ordered quantity ({ordered_qty}) by {over_order} units.",
        })
    else:
        findings.append({
            "rule_id": "QTY-02",
            "name": "Cumulative Billed Exceeds Ordered",
            "status": "PASS",
            "severity": "INFO",
            "details": f"Cumulative invoiced quantity ({total_invoiced_qty}) within ordered quantity ({ordered_qty}).",
        })

    # Rule 4: QTY-03 (Total received quantity exceeds ordered quantity)
    if receipt_count == 0:
        findings.append({
            "rule_id": "QTY-03",
            "name": "Over-Delivery Beyond Ordered",
            "status": "UNKNOWN",
            "severity": "INFO",
            "details": "No receipt records on file.",
        })
    else:
        over_recv = total_received_qty - ordered_qty
        if over_recv > 0:
            findings.append({
                "rule_id": "QTY-03",
                "name": "Over-Delivery Beyond Ordered",
                "status": "FAIL",
                "severity": "MEDIUM",
                "details": f"Recorded received quantity ({total_received_qty}) exceeds ordered quantity ({ordered_qty}) by {over_recv} units.",
            })
        else:
            findings.append({
                "rule_id": "QTY-03",
                "name": "Over-Delivery Beyond Ordered",
                "status": "PASS",
                "severity": "INFO",
                "details": f"Received quantity ({total_received_qty}) within ordered quantity ({ordered_qty}).",
            })

    # Rule 5: PRICE-01 (Billed unit price exceeds agreed unit price + tolerance)
    max_allowed_price = agreed_price * (Decimal("1.0") + price_tolerance)
    price_violations = [
        inv for inv in invoices if inv["billed_unit_price"] > max_allowed_price
    ]
    if price_violations:
        violating_nos = ", ".join(v["invoice_no"] for v in price_violations)
        max_billed = max(v["billed_unit_price"] for v in price_violations)
        findings.append({
            "rule_id": "PRICE-01",
            "name": "Unit Price Variance Beyond Tolerance",
            "status": "FAIL",
            "severity": "MEDIUM",
            "details": f"Invoices [{violating_nos}] billed up to {max_billed:.2f}, exceeding agreed price {agreed_price:.2f} + {price_tolerance*100:.1f}% tolerance (max allowed: {max_allowed_price:.2f}).",
        })
    else:
        findings.append({
            "rule_id": "PRICE-01",
            "name": "Unit Price Variance Beyond Tolerance",
            "status": "PASS",
            "severity": "INFO",
            "details": f"All billed prices within agreed price {agreed_price:.2f} + {price_tolerance*100:.1f}% tolerance.",
        })

    # Rule 6: COND-01 (Non-good condition received items)
    if receipt_count == 0:
        findings.append({
            "rule_id": "COND-01",
            "name": "Damaged or Non-Conforming Goods",
            "status": "UNKNOWN",
            "severity": "INFO",
            "details": "No receipt records on file.",
        })
    else:
        damaged_receipts = [r for r in receipts if r["condition"] != "good"]
        if damaged_receipts:
            conds = ", ".join(f"{r['received_qty']} units ({r['condition']})" for r in damaged_receipts)
            findings.append({
                "rule_id": "COND-01",
                "name": "Damaged or Non-Conforming Goods",
                "status": "FAIL",
                "severity": "HIGH",
                "details": f"Non-conforming items delivered: {conds}.",
            })
        else:
            findings.append({
                "rule_id": "COND-01",
                "name": "Damaged or Non-Conforming Goods",
                "status": "PASS",
                "severity": "INFO",
                "details": "All delivered items logged with 'good' condition.",
            })

    # Rule 7: MULTI-01 (Multiple invoices against single PO line)
    if invoice_count > 1:
        findings.append({
            "rule_id": "MULTI-01",
            "name": "Split or Multiple Invoices Flag",
            "status": "FAIL",
            "severity": "LOW",
            "details": f"Multiple invoices ({invoice_count}) billed against this single PO line; requires cumulative review.",
        })
    else:
        findings.append({
            "rule_id": "MULTI-01",
            "name": "Split or Multiple Invoices Flag",
            "status": "PASS",
            "severity": "INFO",
            "details": f"Single invoice recorded ({invoice_count}).",
        })

    return findings

