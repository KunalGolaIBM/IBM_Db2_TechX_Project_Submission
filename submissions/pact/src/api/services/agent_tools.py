"""Strictly read-only, Db2-grounded LangChain tools for PACT evidence investigations."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Dict, List
import ibm_db
from langchain_core.tools import tool

from core.reconciliation import fetch_line_invoices, fetch_line_receipts

ALLOWED_SOURCE_TABLES = {
    "buyers",
    "suppliers",
    "items",
    "requisitions",
    "purchase_orders",
    "po_lines",
    "goods_receipts",
    "supplier_invoices",
}


def create_investigation_tools(
    conn,
    authorized_case_id: int,
    authorized_po_line_id: int,
    traces: List[Dict[str, Any]],
):
    """Create scoped, read-only LangChain tools bound to an authorized case context."""

    @tool
    def get_case_summary(case_id: int) -> str:
        """Retrieve core procurement case summary, purchase order, buyer, and item details.
        
        Args:
            case_id: The ID of the investigation case. Must match current case context.
        """
        if case_id != authorized_case_id:
            msg = f"Access denied: case_id {case_id} does not match authorized case context {authorized_case_id}."
            traces.append({
                "tool_name": "get_case_summary",
                "arguments": {"case_id": case_id},
                "status": "DENIED",
                "record_ids": [],
            })
            return msg

        sql = """
            SELECT 
                c.id AS case_id, c.case_number, c.status, c.priority, c.version, c.summary,
                p.po_number, s.supplier_name, b.first_name || ' ' || b.last_name AS buyer_name,
                it.sku, it.item_label, l.quantity AS ordered_qty, l.unit_price AS agreed_unit_price,
                VARCHAR_FORMAT(l.ordered_on, 'YYYY-MM-DD') AS ordered_on
            FROM investigation_cases c
            JOIN po_lines l ON l.id = c.po_line_id
            JOIN purchase_orders p ON p.id = l.purchase_order_id
            JOIN suppliers s ON s.id = p.supplier_id
            JOIN buyers b ON b.id = p.buyer_id
            JOIN items it ON it.id = l.item_id
            WHERE c.id = ?
        """
        stmt = ibm_db.prepare(conn, sql)
        ibm_db.execute(stmt, (case_id,))
        row = ibm_db.fetch_assoc(stmt)
        if not row:
            return f"Case {case_id} not found."

        data = {k.lower(): (float(v) if isinstance(v, Decimal) else v) for k, v in row.items()}
        traces.append({
            "tool_name": "get_case_summary",
            "arguments": {"case_id": case_id},
            "status": "SUCCESS",
            "record_ids": [case_id],
        })
        return json.dumps(data)

    @tool
    def get_receipt_evidence(case_id: int) -> str:
        """Retrieve all recorded goods receipt records from IBM Db2 for this case.
        
        Args:
            case_id: The ID of the investigation case. Must match current case context.
        """
        if case_id != authorized_case_id:
            traces.append({
                "tool_name": "get_receipt_evidence",
                "arguments": {"case_id": case_id},
                "status": "DENIED",
                "record_ids": [],
            })
            return f"Access denied: case_id {case_id} not authorized."

        receipts = fetch_line_receipts(conn, authorized_po_line_id)
        serialized = []
        rec_ids = []
        for r in receipts:
            rec_ids.append(r["id"])
            serialized.append({
                "receipt_id": r["id"],
                "received_on": r["received_on"],
                "received_qty": r["received_qty"],
                "condition": r["condition"],
                "received_share": float(r["received_share"]),
            })

        traces.append({
            "tool_name": "get_receipt_evidence",
            "arguments": {"case_id": case_id},
            "status": "SUCCESS",
            "record_ids": rec_ids,
        })
        return json.dumps(serialized)

    @tool
    def get_invoice_evidence(case_id: int) -> str:
        """Retrieve all recorded supplier invoices from IBM Db2 for this case.
        
        Args:
            case_id: The ID of the investigation case. Must match current case context.
        """
        if case_id != authorized_case_id:
            traces.append({
                "tool_name": "get_invoice_evidence",
                "arguments": {"case_id": case_id},
                "status": "DENIED",
                "record_ids": [],
            })
            return f"Access denied: case_id {case_id} not authorized."

        invoices = fetch_line_invoices(conn, authorized_po_line_id)
        serialized = []
        inv_ids = []
        for inv in invoices:
            inv_ids.append(inv["id"])
            serialized.append({
                "invoice_id": inv["id"],
                "invoice_no": inv["invoice_no"],
                "invoice_date": inv["invoice_date"],
                "invoiced_qty": inv["invoiced_qty"],
                "billed_unit_price": float(inv["billed_unit_price"]),
                "billing_drift": float(inv["billing_drift"]),
                "status": inv["status"],
                "paid_on": inv["paid_on"],
            })

        traces.append({
            "tool_name": "get_invoice_evidence",
            "arguments": {"case_id": case_id},
            "status": "SUCCESS",
            "record_ids": inv_ids,
        })
        return json.dumps(serialized)

    @tool
    def get_rule_results(case_id: int) -> str:
        """Retrieve the deterministic 3-way reconciliation audit rule findings for this case.
        
        Args:
            case_id: The ID of the investigation case. Must match current case context.
        """
        if case_id != authorized_case_id:
            traces.append({
                "tool_name": "get_rule_results",
                "arguments": {"case_id": case_id},
                "status": "DENIED",
                "record_ids": [],
            })
            return f"Access denied: case_id {case_id} not authorized."

        sql = """
            SELECT id, rule_id, rule_name, status, severity, discrepancy_amount, details, evidence_refs
            FROM case_findings
            WHERE case_id = ?
            ORDER BY id ASC
        """
        stmt = ibm_db.prepare(conn, sql)
        ibm_db.execute(stmt, (case_id,))
        findings = []
        finding_ids = []
        row = ibm_db.fetch_assoc(stmt)
        while row:
            finding_ids.append(int(row["ID"]))
            findings.append({
                "finding_id": int(row["ID"]),
                "rule_id": row["RULE_ID"].strip(),
                "rule_name": row["RULE_NAME"].strip(),
                "status": row["STATUS"].strip(),
                "severity": row["SEVERITY"].strip(),
                "discrepancy_amount": float(row["DISCREPANCY_AMOUNT"]),
                "details": row["DETAILS"].strip(),
            })
            row = ibm_db.fetch_assoc(stmt)

        traces.append({
            "tool_name": "get_rule_results",
            "arguments": {"case_id": case_id},
            "status": "SUCCESS",
            "record_ids": finding_ids,
        })
        return json.dumps(findings)

    @tool
    def get_source_record(table: str, record_id: int) -> str:
        """Inspect an exact source record in genuine IBM Db2 by table and record ID.
        
        Args:
            table: The name of the source table (e.g. goods_receipts, supplier_invoices, po_lines).
            record_id: The primary key ID of the record.
        """
        clean_table = table.strip().lower()
        if clean_table not in ALLOWED_SOURCE_TABLES:
            traces.append({
                "tool_name": "get_source_record",
                "arguments": {"table": table, "record_id": record_id},
                "status": "DENIED",
                "record_ids": [],
            })
            return f"Access denied: Table '{clean_table}' is not in allowed source tables list."

        # Case-scope authorization: if inspecting goods_receipts or supplier_invoices, ensure po_line_id matches
        if clean_table in ("goods_receipts", "supplier_invoices"):
            scope_sql = f"SELECT id, po_line_id FROM {clean_table} WHERE id = ?"
            stmt_scope = ibm_db.prepare(conn, scope_sql)
            ibm_db.execute(stmt_scope, (record_id,))
            s_row = ibm_db.fetch_assoc(stmt_scope)
            if not s_row or int(s_row["PO_LINE_ID"]) != authorized_po_line_id:
                traces.append({
                    "tool_name": "get_source_record",
                    "arguments": {"table": table, "record_id": record_id},
                    "status": "DENIED",
                    "record_ids": [],
                })
                return f"Access denied: Record {record_id} in {clean_table} does not belong to authorized PO line {authorized_po_line_id}."

        sql = f"SELECT * FROM {clean_table} WHERE id = ?"
        stmt = ibm_db.prepare(conn, sql)
        ibm_db.execute(stmt, (record_id,))
        row = ibm_db.fetch_assoc(stmt)
        if not row:
            traces.append({
                "tool_name": "get_source_record",
                "arguments": {"table": table, "record_id": record_id},
                "status": "NOT_FOUND",
                "record_ids": [],
            })
            return f"Record {record_id} not found in {clean_table}."

        clean_row = {}
        for k, v in row.items():
            if isinstance(v, Decimal):
                clean_row[k.lower()] = float(v)
            else:
                clean_row[k.lower()] = v.strip() if isinstance(v, str) else v

        traces.append({
            "tool_name": "get_source_record",
            "arguments": {"table": table, "record_id": record_id},
            "status": "SUCCESS",
            "record_ids": [record_id],
        })
        return json.dumps(clean_row)

    return [
        get_case_summary,
        get_receipt_evidence,
        get_invoice_evidence,
        get_rule_results,
        get_source_record,
    ]

