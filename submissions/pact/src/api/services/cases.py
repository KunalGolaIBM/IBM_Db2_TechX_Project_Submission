"""Case management, reconciliation ingestion, and review workflow service backed by genuine IBM Db2."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import ibm_db

from core.reconciliation import (
    fetch_line_invoices,
    fetch_line_receipts,
    fetch_reconciliation_summary,
)
from core.rules import evaluate_rules


class CaseNotFoundError(Exception):
    pass


class ConcurrencyConflictError(Exception):
    pass


class InvalidStateTransitionError(Exception):
    pass


def populate_cases_from_reconciliation(conn) -> Dict[str, int]:
    """Run full 3-way reconciliation across all live PO lines and generate/update cases."""
    summaries = fetch_reconciliation_summary(conn)

    pass_count = 0
    fail_count = 0
    unknown_count = 0
    cases_created = 0

    for summary in summaries:
        po_line_id = summary["po_line_id"]
        invoices = fetch_line_invoices(conn, po_line_id)
        receipts = fetch_line_receipts(conn, po_line_id)
        findings = evaluate_rules(summary, invoices, receipts)

        line_fails = [f for f in findings if f["status"] == "FAIL"]
        line_unknowns = [f for f in findings if f["status"] == "UNKNOWN"]
        line_passes = [f for f in findings if f["status"] == "PASS"]

        pass_count += len(line_passes)
        fail_count += len(line_fails)
        unknown_count += len(line_unknowns)

        # Create case only if anomalies exist
        if line_fails or line_unknowns:
            # Check if case exists for this po_line_id
            check_sql = "SELECT id, version FROM investigation_cases WHERE po_line_id = ?"
            stmt = ibm_db.prepare(conn, check_sql)
            ibm_db.execute(stmt, (po_line_id,))
            existing = ibm_db.fetch_assoc(stmt)

            high_count = sum(1 for f in (line_fails + line_unknowns) if f["severity"] == "HIGH")
            priority = "CRITICAL" if high_count >= 2 else ("HIGH" if high_count == 1 else "MEDIUM")

            rule_ids_str = ", ".join(f["rule_id"] for f in (line_fails + line_unknowns))
            summary_text = f"Anomalies detected ({rule_ids_str}) on PO {summary['po_number']}"

            if not existing:
                case_number = f"CASE-POL-{po_line_id:04d}"
                insert_case_sql = """
                    INSERT INTO investigation_cases 
                    (case_number, po_line_id, status, priority, version, summary)
                    VALUES (?, ?, 'OPEN', ?, 1, ?)
                """
                stmt_ins = ibm_db.prepare(conn, insert_case_sql)
                ibm_db.execute(stmt_ins, (case_number, po_line_id, priority, summary_text))

                # Retrieve generated identity id
                id_stmt = ibm_db.exec_immediate(conn, "VALUES IDENTITY_VAL_LOCAL()")
                case_id = int(ibm_db.fetch_tuple(id_stmt)[0])
                cases_created += 1

                # Insert findings
                for f in findings:
                    if f["status"] in ("FAIL", "UNKNOWN"):
                        evidence_refs = json.dumps({
                            "po_line_id": po_line_id,
                            "purchase_order_id": summary["purchase_order_id"],
                            "invoices": [inv["id"] for inv in invoices],
                            "receipts": [rcp["id"] for rcp in receipts],
                        })
                        discrepancy = float(f.get("discrepancy_amount", 0.0))
                        ins_finding_sql = """
                            INSERT INTO case_findings 
                            (case_id, rule_id, rule_name, status, severity, discrepancy_amount, details, evidence_refs)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """
                        stmt_find = ibm_db.prepare(conn, ins_finding_sql)
                        ibm_db.execute(stmt_find, (
                            case_id,
                            f["rule_id"],
                            f["name"],
                            f["status"],
                            f["severity"],
                            discrepancy,
                            f["details"],
                            evidence_refs,
                        ))

                # Log audit event
                audit_sql = """
                    INSERT INTO audit_events 
                    (case_id, entity_type, entity_id, event_type, actor, action_details)
                    VALUES (?, 'CASE', ?, 'CASE_INITIALIZED', 'SYSTEM', ?)
                """
                stmt_audit = ibm_db.prepare(conn, audit_sql)
                audit_desc = f"Investigation case generated from automated reconciliation audit with {len(line_fails)} FAIL, {len(line_unknowns)} UNKNOWN."
                ibm_db.execute(stmt_audit, (case_id, case_number, audit_desc))
            else:
                case_id = int(existing["ID"])
                upd_case_sql = """
                    UPDATE investigation_cases 
                    SET priority = ?, summary = ?, updated_at = CURRENT TIMESTAMP 
                    WHERE id = ?
                """
                stmt_upd = ibm_db.prepare(conn, upd_case_sql)
                ibm_db.execute(stmt_upd, (priority, summary_text, case_id))
                cases_created += 1

    return {
        "po_lines_reconciled": len(summaries),
        "total_evaluations": pass_count + fail_count + unknown_count,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "unknown_count": unknown_count,
        "cases_created_or_updated": cases_created,
    }


def list_cases(
    conn,
    page: int = 1,
    limit: int = 20,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    search: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """Retrieve paginated investigation cases with summary stats and metadata."""
    offset = (page - 1) * limit

    base_query = """
        FROM investigation_cases c
        JOIN po_lines l ON l.id = c.po_line_id
        JOIN purchase_orders p ON p.id = l.purchase_order_id
        JOIN suppliers s ON s.id = p.supplier_id
        JOIN items it ON it.id = l.item_id
        WHERE 1 = 1
    """
    params: List[Any] = []

    if status:
        base_query += " AND c.status = ?"
        params.append(status)
    if priority:
        base_query += " AND c.priority = ?"
        params.append(priority)
    if search:
        search_pattern = f"%{search.strip().upper()}%"
        base_query += " AND (UPPER(p.po_number) LIKE ? OR UPPER(s.supplier_name) LIKE ? OR UPPER(it.item_label) LIKE ?)"
        params.extend([search_pattern, search_pattern, search_pattern])

    # Count total
    count_sql = "SELECT COUNT(*) " + base_query
    count_stmt = ibm_db.prepare(conn, count_sql)
    ibm_db.execute(count_stmt, tuple(params))
    total_count = int(ibm_db.fetch_tuple(count_stmt)[0])

    # Query items with pagination (Db2 OFFSET/LIMIT)
    items_sql = f"""
        SELECT 
            c.id, c.case_number, c.po_line_id, c.status, c.priority, c.version, c.summary,
            VARCHAR_FORMAT(c.created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at,
            VARCHAR_FORMAT(c.updated_at, 'YYYY-MM-DD HH24:MI:SS') AS updated_at,
            p.po_number, s.supplier_name, it.item_label, l.quantity AS ordered_qty, l.unit_price AS agreed_unit_price,
            (SELECT COUNT(*) FROM case_findings cf WHERE cf.case_id = c.id) AS findings_count,
            (SELECT COUNT(*) FROM case_findings cf WHERE cf.case_id = c.id AND cf.status = 'FAIL') AS fail_count,
            (SELECT COUNT(*) FROM case_findings cf WHERE cf.case_id = c.id AND cf.status = 'UNKNOWN') AS unknown_count
        {base_query}
        ORDER BY c.id ASC
        OFFSET {offset} ROWS FETCH NEXT {limit} ROWS ONLY
    """
    items_stmt = ibm_db.prepare(conn, items_sql)
    ibm_db.execute(items_stmt, tuple(params))

    cases = []
    row = ibm_db.fetch_assoc(items_stmt)
    while row:
        cases.append({
            "id": int(row["ID"]),
            "case_number": row["CASE_NUMBER"].strip(),
            "po_line_id": int(row["PO_LINE_ID"]),
            "status": row["STATUS"].strip(),
            "priority": row["PRIORITY"].strip(),
            "version": int(row["VERSION"]),
            "summary": row["SUMMARY"].strip() if row["SUMMARY"] else None,
            "po_number": row["PO_NUMBER"].strip(),
            "supplier_name": row["SUPPLIER_NAME"].strip(),
            "item_label": row["ITEM_LABEL"].strip(),
            "ordered_qty": int(row["ORDERED_QTY"]),
            "agreed_unit_price": float(row["AGREED_UNIT_PRICE"]),
            "created_at": str(row["CREATED_AT"]),
            "updated_at": str(row["UPDATED_AT"]),
            "findings_count": int(row["FINDINGS_COUNT"]),
            "fail_count": int(row["FAIL_COUNT"]),
            "unknown_count": int(row["UNKNOWN_COUNT"]),
        })
        row = ibm_db.fetch_assoc(items_stmt)

    return cases, total_count


def get_case_detail(conn, case_id: int) -> Dict[str, Any]:
    """Retrieve full details for a single investigation case including its findings."""
    sql = """
        SELECT 
            c.id, c.case_number, c.po_line_id, c.status, c.priority, c.version, c.summary,
            VARCHAR_FORMAT(c.created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at,
            VARCHAR_FORMAT(c.updated_at, 'YYYY-MM-DD HH24:MI:SS') AS updated_at,
            p.po_number, s.supplier_name, b.first_name || ' ' || b.last_name AS buyer_name,
            it.sku AS item_sku, it.item_label, l.quantity AS ordered_qty, l.unit_price AS agreed_unit_price,
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
        raise CaseNotFoundError(f"Case with ID {case_id} not found")

    case_data = {
        "id": int(row["ID"]),
        "case_number": row["CASE_NUMBER"].strip(),
        "po_line_id": int(row["PO_LINE_ID"]),
        "status": row["STATUS"].strip(),
        "priority": row["PRIORITY"].strip(),
        "version": int(row["VERSION"]),
        "summary": row["SUMMARY"].strip() if row["SUMMARY"] else None,
        "created_at": str(row["CREATED_AT"]),
        "updated_at": str(row["UPDATED_AT"]),
        "po_number": row["PO_NUMBER"].strip(),
        "supplier_name": row["SUPPLIER_NAME"].strip(),
        "buyer_name": row["BUYER_NAME"].strip(),
        "item_sku": row["ITEM_SKU"].strip(),
        "item_label": row["ITEM_LABEL"].strip(),
        "ordered_qty": int(row["ORDERED_QTY"]),
        "agreed_unit_price": float(row["AGREED_UNIT_PRICE"]),
        "ordered_on": str(row["ORDERED_ON"]),
        "findings": [],
    }

    # Fetch findings
    findings_sql = """
        SELECT id, case_id, rule_id, rule_name, status, severity, discrepancy_amount, details, evidence_refs,
               VARCHAR_FORMAT(created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at
        FROM case_findings
        WHERE case_id = ?
        ORDER BY id ASC
    """
    f_stmt = ibm_db.prepare(conn, findings_sql)
    ibm_db.execute(f_stmt, (case_id,))
    f_row = ibm_db.fetch_assoc(f_stmt)
    while f_row:
        case_data["findings"].append({
            "id": int(f_row["ID"]),
            "case_id": int(f_row["CASE_ID"]),
            "rule_id": f_row["RULE_ID"].strip(),
            "rule_name": f_row["RULE_NAME"].strip(),
            "status": f_row["STATUS"].strip(),
            "severity": f_row["SEVERITY"].strip(),
            "discrepancy_amount": float(f_row["DISCREPANCY_AMOUNT"]),
            "details": f_row["DETAILS"].strip(),
            "evidence_refs": f_row["EVIDENCE_REFS"].strip() if f_row["EVIDENCE_REFS"] else None,
            "created_at": str(f_row["CREATED_AT"]),
        })
        f_row = ibm_db.fetch_assoc(f_stmt)

    return case_data


def get_case_evidence(conn, case_id: int) -> Dict[str, Any]:
    """Retrieve exact Db2 source record references and facts for a case."""
    case = get_case_detail(conn, case_id)
    po_line_id = case["po_line_id"]

    # Reconciliation summary
    summaries = fetch_reconciliation_summary(conn, po_line_id=po_line_id)
    summary_data = summaries[0] if summaries else {}

    # Format Decimals to floats for JSON serialization
    serialized_summary = {}
    for k, v in summary_data.items():
        if isinstance(v, Decimal):
            serialized_summary[k] = float(v)
        else:
            serialized_summary[k] = v

    # Fetch Purchase Order record
    po_sql = "SELECT id, po_number, supplier_id, buyer_id, ordered_on, payment_terms FROM purchase_orders WHERE id = (SELECT purchase_order_id FROM po_lines WHERE id = ?)"
    stmt_po = ibm_db.prepare(conn, po_sql)
    ibm_db.execute(stmt_po, (po_line_id,))
    po_row = ibm_db.fetch_assoc(stmt_po)
    po_record = {
        "table": "purchase_orders",
        "id": int(po_row["ID"]),
        "record_data": {
            "po_number": po_row["PO_NUMBER"].strip(),
            "supplier_id": int(po_row["SUPPLIER_ID"]),
            "buyer_id": int(po_row["BUYER_ID"]),
            "ordered_on": str(po_row["ORDERED_ON"]),
            "payment_terms": po_row["PAYMENT_TERMS"].strip(),
        }
    }

    # Fetch PO Line record
    pol_sql = "SELECT id, purchase_order_id, requisition_id, item_id, quantity, ordered_on, negotiated_factor, unit_price FROM po_lines WHERE id = ?"
    stmt_pol = ibm_db.prepare(conn, pol_sql)
    ibm_db.execute(stmt_pol, (po_line_id,))
    pol_row = ibm_db.fetch_assoc(stmt_pol)
    pol_record = {
        "table": "po_lines",
        "id": int(pol_row["ID"]),
        "record_data": {
            "purchase_order_id": int(pol_row["PURCHASE_ORDER_ID"]),
            "requisition_id": int(pol_row["REQUISITION_ID"]),
            "item_id": int(pol_row["ITEM_ID"]),
            "quantity": int(pol_row["QUANTITY"]),
            "ordered_on": str(pol_row["ORDERED_ON"]),
            "negotiated_factor": float(pol_row["NEGOTIATED_FACTOR"]),
            "unit_price": float(pol_row["UNIT_PRICE"]),
        }
    }

    # Fetch Goods Receipts
    receipts_data = fetch_line_receipts(conn, po_line_id)
    receipt_records = [
        {
            "table": "goods_receipts",
            "id": r["id"],
            "record_data": {
                "received_on": r["received_on"],
                "received_share": float(r["received_share"]),
                "received_qty": r["received_qty"],
                "condition": r["condition"],
            }
        }
        for r in receipts_data
    ]

    # Fetch Invoices
    invoices_data = fetch_line_invoices(conn, po_line_id)
    invoice_records = [
        {
            "table": "supplier_invoices",
            "id": inv["id"],
            "record_data": {
                "invoice_no": inv["invoice_no"],
                "invoice_date": inv["invoice_date"],
                "qty_ratio": float(inv["qty_ratio"]),
                "invoiced_qty": inv["invoiced_qty"],
                "billing_drift": float(inv["billing_drift"]),
                "billed_unit_price": float(inv["billed_unit_price"]),
                "status": inv["status"],
                "paid_on": inv["paid_on"],
            }
        }
        for inv in invoices_data
    ]

    return {
        "case_id": case_id,
        "po_line_id": po_line_id,
        "reconciliation_facts": serialized_summary,
        "purchase_order": po_record,
        "po_line": pol_record,
        "receipts": receipt_records,
        "invoices": invoice_records,
    }


def record_case_review(
    conn,
    case_id: int,
    decision: str,
    reviewer: str,
    reviewer_notes: str,
    rationale: Optional[str],
    expected_version: int,
) -> Dict[str, Any]:
    """Execute review recording and state transition within an atomic Db2 transaction with optimistic locking."""
    # First check current case
    check_sql = "SELECT id, case_number, status, version FROM investigation_cases WHERE id = ?"
    stmt = ibm_db.prepare(conn, check_sql)
    ibm_db.execute(stmt, (case_id,))
    row = ibm_db.fetch_assoc(stmt)
    if not row:
        raise CaseNotFoundError(f"Case {case_id} not found")

    current_version = int(row["VERSION"])
    current_status = row["STATUS"].strip()
    case_number = row["CASE_NUMBER"].strip()

    if current_version != expected_version:
        raise ConcurrencyConflictError(
            f"Optimistic lock conflict: Case version is {current_version}, but client expected {expected_version}"
        )

    # Determine next status
    if decision == "ADDITIONAL_EVIDENCE_REQUESTED":
        next_status = "NEEDS_EVIDENCE"
    else:
        next_status = "REVIEWED"

    new_version = current_version + 1

    # 1. Update investigation case with version check
    upd_sql = """
        UPDATE investigation_cases 
        SET status = ?, version = ?, updated_at = CURRENT TIMESTAMP 
        WHERE id = ? AND version = ?
    """
    upd_stmt = ibm_db.prepare(conn, upd_sql)
    ibm_db.execute(upd_stmt, (next_status, new_version, case_id, current_version))
    affected = ibm_db.num_rows(upd_stmt)
    if affected == 0:
        raise ConcurrencyConflictError("Concurrent modification detected during state transition update.")

    # 2. Insert into review_decisions
    dec_sql = """
        INSERT INTO review_decisions (case_id, decision, reviewer, reviewer_notes, rationale)
        VALUES (?, ?, ?, ?, ?)
    """
    dec_stmt = ibm_db.prepare(conn, dec_sql)
    ibm_db.execute(dec_stmt, (case_id, decision, reviewer, reviewer_notes, rationale or ""))

    # Retrieve generated decision id
    id_stmt = ibm_db.exec_immediate(conn, "VALUES IDENTITY_VAL_LOCAL()")
    decision_id = int(ibm_db.fetch_tuple(id_stmt)[0])

    # 3. Insert audit event
    audit_sql = """
        INSERT INTO audit_events (case_id, entity_type, entity_id, event_type, actor, action_details)
        VALUES (?, 'REVIEW_DECISION', ?, 'REVIEW_RECORDED', ?, ?)
    """
    audit_stmt = ibm_db.prepare(conn, audit_sql)
    audit_details = f"Decision {decision} recorded by {reviewer}. Status transitioned from {current_status} to {next_status}."
    ibm_db.execute(audit_stmt, (case_id, str(decision_id), reviewer, audit_details))

    # Retrieve decision timestamp
    time_stmt = ibm_db.prepare(conn, "SELECT VARCHAR_FORMAT(decided_at, 'YYYY-MM-DD HH24:MI:SS') FROM review_decisions WHERE id = ?")
    ibm_db.execute(time_stmt, (decision_id,))
    decided_at = ibm_db.fetch_tuple(time_stmt)[0]

    return {
        "id": decision_id,
        "case_id": case_id,
        "decision": decision,
        "reviewer": reviewer,
        "reviewer_notes": reviewer_notes,
        "rationale": rationale,
        "decided_at": str(decided_at),
        "new_case_status": next_status,
        "new_case_version": new_version,
    }


def list_case_audit_events(conn, case_id: int) -> List[Dict[str, Any]]:
    """Retrieve chronologically ordered audit trail for a specific case."""
    sql = """
        SELECT id, case_id, entity_type, entity_id, event_type, actor, action_details,
               VARCHAR_FORMAT(created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at
        FROM audit_events
        WHERE case_id = ?
        ORDER BY id DESC
    """
    stmt = ibm_db.prepare(conn, sql)
    ibm_db.execute(stmt, (case_id,))
    events = []
    row = ibm_db.fetch_assoc(stmt)
    while row:
        events.append({
            "id": int(row["ID"]),
            "case_id": int(row["CASE_ID"]) if row["CASE_ID"] else None,
            "entity_type": row["ENTITY_TYPE"].strip(),
            "entity_id": row["ENTITY_ID"].strip(),
            "event_type": row["EVENT_TYPE"].strip(),
            "actor": row["ACTOR"].strip(),
            "action_details": row["ACTION_DETAILS"].strip(),
            "created_at": str(row["CREATED_AT"]),
        })
        row = ibm_db.fetch_assoc(stmt)
    return events
