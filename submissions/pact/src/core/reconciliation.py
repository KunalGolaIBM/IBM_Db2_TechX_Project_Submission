"""Deterministic 3-way reconciliation query logic backed by genuine IBM Db2."""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Any, Dict, List, Optional
import ibm_db

RECONCILIATION_QUERY = """
WITH rcpt_agg AS (
    SELECT 
        po_line_id,
        COUNT(id) AS receipt_count,
        COALESCE(SUM(received_qty), 0) AS total_received_qty,
        COALESCE(SUM(CASE WHEN condition = 'good' THEN received_qty ELSE 0 END), 0) AS acceptable_received_qty,
        COALESCE(SUM(CASE WHEN condition <> 'good' THEN received_qty ELSE 0 END), 0) AS non_good_received_qty,
        MIN(received_on) AS first_received_on,
        MAX(received_on) AS last_received_on
    FROM goods_receipts
    GROUP BY po_line_id
),
inv_agg AS (
    SELECT 
        po_line_id,
        COUNT(id) AS invoice_count,
        COALESCE(SUM(invoiced_qty), 0) AS total_invoiced_qty,
        MIN(invoice_date) AS first_invoice_date,
        MAX(invoice_date) AS last_invoice_date,
        MAX(billed_unit_price) AS max_billed_unit_price,
        MIN(billed_unit_price) AS min_billed_unit_price
    FROM supplier_invoices
    GROUP BY po_line_id
)
SELECT 
    l.id AS po_line_id,
    l.purchase_order_id,
    p.po_number,
    p.supplier_id,
    s.supplier_name,
    p.buyer_id,
    b.first_name || ' ' || b.last_name AS buyer_name,
    l.item_id,
    it.sku,
    it.item_label,
    l.quantity AS ordered_qty,
    l.unit_price AS agreed_unit_price,
    l.ordered_on,
    COALESCE(r.receipt_count, 0) AS receipt_count,
    r.total_received_qty,
    r.acceptable_received_qty,
    r.non_good_received_qty,
    COALESCE(i.invoice_count, 0) AS invoice_count,
    COALESCE(i.total_invoiced_qty, 0) AS total_invoiced_qty,
    i.max_billed_unit_price,
    i.min_billed_unit_price,
    r.first_received_on,
    r.last_received_on,
    i.first_invoice_date,
    i.last_invoice_date
FROM po_lines l
JOIN purchase_orders p ON p.id = l.purchase_order_id
JOIN suppliers s ON s.id = p.supplier_id
JOIN buyers b ON b.id = p.buyer_id
JOIN items it ON it.id = l.item_id
LEFT JOIN rcpt_agg r ON r.po_line_id = l.id
LEFT JOIN inv_agg i ON i.po_line_id = l.id
"""


def get_db2_connection():
    from db.apply_schema import load_env
    load_env()
    dsn = (
        f"DATABASE={os.environ['DB2_DATABASE']};"
        f"HOSTNAME={os.environ['DB2_HOST']};"
        f"PORT={os.environ['DB2_PORT']};"
        "PROTOCOL=TCPIP;"
        f"UID={os.environ['DB2_USER']};"
        f"PWD={os.environ['DB2_PASSWORD']};"
    )
    return ibm_db.connect(dsn, "", "")


def fetch_reconciliation_summary(conn, po_line_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Execute pre-aggregated reconciliation query for all PO lines or a specific line."""
    sql = RECONCILIATION_QUERY
    params = ()
    if po_line_id is not None:
        sql += " WHERE l.id = ?"
        params = (po_line_id,)
    sql += " ORDER BY l.id"

    stmt = ibm_db.prepare(conn, sql)
    ibm_db.execute(stmt, params)

    results = []
    row = ibm_db.fetch_assoc(stmt)
    while row:
        # Convert dictionary keys to lowercase and types to Decimal/int/str
        clean_row = {
            "po_line_id": int(row["PO_LINE_ID"]),
            "purchase_order_id": int(row["PURCHASE_ORDER_ID"]),
            "po_number": row["PO_NUMBER"].strip(),
            "supplier_id": int(row["SUPPLIER_ID"]),
            "supplier_name": row["SUPPLIER_NAME"].strip(),
            "buyer_id": int(row["BUYER_ID"]),
            "buyer_name": row["BUYER_NAME"].strip(),
            "item_id": int(row["ITEM_ID"]),
            "sku": row["SKU"].strip(),
            "item_label": row["ITEM_LABEL"].strip(),
            "ordered_qty": int(row["ORDERED_QTY"]),
            "agreed_unit_price": Decimal(str(row["AGREED_UNIT_PRICE"])),
            "ordered_on": str(row["ORDERED_ON"]),
            "receipt_count": int(row["RECEIPT_COUNT"]),
            "total_received_qty": int(row["TOTAL_RECEIVED_QTY"]) if row["TOTAL_RECEIVED_QTY"] is not None else None,
            "acceptable_received_qty": int(row["ACCEPTABLE_RECEIVED_QTY"]) if row["ACCEPTABLE_RECEIVED_QTY"] is not None else None,
            "non_good_received_qty": int(row["NON_GOOD_RECEIVED_QTY"]) if row["NON_GOOD_RECEIVED_QTY"] is not None else 0,
            "invoice_count": int(row["INVOICE_COUNT"]),
            "total_invoiced_qty": int(row["TOTAL_INVOICED_QTY"]),
            "max_billed_unit_price": Decimal(str(row["MAX_BILLED_UNIT_PRICE"])) if row["MAX_BILLED_UNIT_PRICE"] is not None else None,
            "min_billed_unit_price": Decimal(str(row["MIN_BILLED_UNIT_PRICE"])) if row["MIN_BILLED_UNIT_PRICE"] is not None else None,
            "first_received_on": str(row["FIRST_RECEIVED_ON"]) if row["FIRST_RECEIVED_ON"] else None,
            "last_received_on": str(row["LAST_RECEIVED_ON"]) if row["LAST_RECEIVED_ON"] else None,
            "first_invoice_date": str(row["FIRST_INVOICE_DATE"]) if row["FIRST_INVOICE_DATE"] else None,
            "last_invoice_date": str(row["LAST_INVOICE_DATE"]) if row["LAST_INVOICE_DATE"] else None,
        }
        results.append(clean_row)
        row = ibm_db.fetch_assoc(stmt)

    return results


def fetch_line_invoices(conn, po_line_id: int) -> List[Dict[str, Any]]:
    """Fetch all individual invoice line items for detailed price tolerance checks."""
    sql = """
        SELECT id, invoice_no, invoice_date, qty_ratio, invoiced_qty, 
               billing_drift, billed_unit_price, status, paid_on
        FROM supplier_invoices
        WHERE po_line_id = ?
        ORDER BY id
    """
    stmt = ibm_db.prepare(conn, sql)
    ibm_db.execute(stmt, (po_line_id,))
    invoices = []
    row = ibm_db.fetch_assoc(stmt)
    while row:
        invoices.append({
            "id": int(row["ID"]),
            "invoice_no": row["INVOICE_NO"].strip(),
            "invoice_date": str(row["INVOICE_DATE"]),
            "qty_ratio": Decimal(str(row["QTY_RATIO"])),
            "invoiced_qty": int(row["INVOICED_QTY"]),
            "billing_drift": Decimal(str(row["BILLING_DRIFT"])),
            "billed_unit_price": Decimal(str(row["BILLED_UNIT_PRICE"])),
            "status": row["STATUS"].strip(),
            "paid_on": str(row["PAID_ON"]) if row["PAID_ON"] else None,
        })
        row = ibm_db.fetch_assoc(stmt)
    return invoices


def fetch_line_receipts(conn, po_line_id: int) -> List[Dict[str, Any]]:
    """Fetch all individual goods receipts for detailed condition auditing."""
    sql = """
        SELECT id, received_on, received_share, received_qty, condition
        FROM goods_receipts
        WHERE po_line_id = ?
        ORDER BY id
    """
    stmt = ibm_db.prepare(conn, sql)
    ibm_db.execute(stmt, (po_line_id,))
    receipts = []
    row = ibm_db.fetch_assoc(stmt)
    while row:
        receipts.append({
            "id": int(row["ID"]),
            "received_on": str(row["RECEIVED_ON"]),
            "received_share": Decimal(str(row["RECEIVED_SHARE"])),
            "received_qty": int(row["RECEIVED_QTY"]),
            "condition": row["CONDITION"].strip(),
        })
        row = ibm_db.fetch_assoc(stmt)
    return receipts

