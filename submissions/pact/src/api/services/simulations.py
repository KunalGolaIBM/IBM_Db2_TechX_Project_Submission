"""Counterfactual simulation service backed by genuine IBM Db2."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Dict, List, Optional
import ibm_db

from core.reconciliation import (
    fetch_line_invoices,
    fetch_line_receipts,
    fetch_reconciliation_summary,
)
from core.rules import evaluate_rules


class CaseNotFoundError(Exception):
    pass


class UnsupportedSimulationTypeError(Exception):
    pass


class InvalidSimulationParameterError(Exception):
    pass


def execute_simulation(
    conn,
    case_id: int,
    simulation_type: str,
    parameters: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute counterfactual simulation in-memory and persist run record in Db2 SCENARIO_RUNS."""
    if simulation_type != "ADD_ACCEPTABLE_RECEIPT":
        raise UnsupportedSimulationTypeError(
            f"Unsupported simulation type '{simulation_type}'. Supported types: ['ADD_ACCEPTABLE_RECEIPT']"
        )

    delta_qty = parameters.get("delta_quantity")
    if delta_qty is None or not isinstance(delta_qty, int) or delta_qty <= 0:
        raise InvalidSimulationParameterError(
            "delta_quantity must be a positive integer greater than 0"
        )

    condition = str(parameters.get("condition") or "good").strip().lower()
    received_on = str(parameters.get("received_on") or "2026-05-01").strip()
    notes = parameters.get("notes")

    # 1. Verify case existence in Db2
    case_sql = "SELECT id, case_number, po_line_id FROM investigation_cases WHERE id = ?"
    stmt = ibm_db.prepare(conn, case_sql)
    ibm_db.execute(stmt, (case_id,))
    case_row = ibm_db.fetch_assoc(stmt)
    if not case_row:
        raise CaseNotFoundError(f"Case {case_id} not found")

    po_line_id = int(case_row["PO_LINE_ID"])
    case_number = case_row["CASE_NUMBER"].strip()

    # 2. Fetch baseline data from Db2
    summaries = fetch_reconciliation_summary(conn, po_line_id=po_line_id)
    if not summaries:
        raise CaseNotFoundError(f"No reconciliation data found for PO line {po_line_id}")
    baseline_summary = summaries[0]
    invoices = fetch_line_invoices(conn, po_line_id)
    baseline_receipts = fetch_line_receipts(conn, po_line_id)

    # 3. Evaluate baseline rules
    baseline_findings = evaluate_rules(baseline_summary, invoices, baseline_receipts)
    b_fails = sum(1 for f in baseline_findings if f["status"] == "FAIL")
    b_unknowns = sum(1 for f in baseline_findings if f["status"] == "UNKNOWN")
    b_passes = sum(1 for f in baseline_findings if f["status"] == "PASS")
    b_anomalies = b_fails + b_unknowns

    b_acc_qty = baseline_summary["acceptable_received_qty"] or 0
    b_inv_qty = baseline_summary["total_invoiced_qty"]
    b_gap = b_inv_qty - b_acc_qty

    baseline_state = {
        "receipt_count": baseline_summary["receipt_count"],
        "accepted_qty": b_acc_qty,
        "invoiced_qty": b_inv_qty,
        "gap": b_gap,
        "findings_count": len(baseline_findings),
        "fail_count": b_fails,
        "unknown_count": b_unknowns,
    }

    # 4. Construct hypothetical in-memory simulation (NEVER written to goods_receipts)
    hypothetical_receipt = {
        "id": 0,  # Explicit hypothetical identifier
        "received_on": received_on,
        "received_share": Decimal("0.0"),
        "received_qty": delta_qty,
        "condition": condition,
    }
    simulated_receipts = list(baseline_receipts) + [hypothetical_receipt]

    simulated_summary = dict(baseline_summary)
    simulated_summary["receipt_count"] = baseline_summary["receipt_count"] + 1
    simulated_summary["total_received_qty"] = (baseline_summary["total_received_qty"] or 0) + delta_qty
    if condition == "good":
        simulated_summary["acceptable_received_qty"] = (baseline_summary["acceptable_received_qty"] or 0) + delta_qty
    else:
        simulated_summary["non_good_received_qty"] = (baseline_summary["non_good_received_qty"] or 0) + delta_qty

    # 5. Evaluate simulated rules
    simulated_findings = evaluate_rules(simulated_summary, invoices, simulated_receipts)
    s_fails = sum(1 for f in simulated_findings if f["status"] == "FAIL")
    s_unknowns = sum(1 for f in simulated_findings if f["status"] == "UNKNOWN")
    s_passes = sum(1 for f in simulated_findings if f["status"] == "PASS")
    s_anomalies = s_fails + s_unknowns

    s_acc_qty = simulated_summary["acceptable_received_qty"] or 0
    s_inv_qty = simulated_summary["total_invoiced_qty"]
    s_gap = s_inv_qty - s_acc_qty

    simulated_state = {
        "receipt_count": simulated_summary["receipt_count"],
        "accepted_qty": s_acc_qty,
        "invoiced_qty": s_inv_qty,
        "gap": s_gap,
        "findings_count": len(simulated_findings),
        "fail_count": s_fails,
        "unknown_count": s_unknowns,
    }

    # 6. Compare findings & compute rule diff
    rule_diff = []
    b_map = {f["rule_id"]: f for f in baseline_findings}
    s_map = {f["rule_id"]: f for f in simulated_findings}

    improved_count = 0
    regressed_count = 0
    changes_list = []

    for rule_id, s_f in s_map.items():
        b_f = b_map.get(rule_id, {})
        b_st = b_f.get("status", "UNKNOWN")
        s_st = s_f.get("status", "UNKNOWN")

        improved = (b_st in ("FAIL", "UNKNOWN") and s_st == "PASS")
        regressed = (b_st == "PASS" and s_st in ("FAIL", "UNKNOWN"))

        if improved:
            improved_count += 1
            changes_list.append(f"{rule_id} ({b_st} -> {s_st})")
        elif regressed:
            regressed_count += 1
            changes_list.append(f"{rule_id} REGRESSED ({b_st} -> {s_st})")

        rule_diff.append({
            "rule_id": rule_id,
            "rule_name": s_f.get("name", rule_id),
            "baseline_status": b_st,
            "simulated_status": s_st,
            "improved": improved,
            "details_baseline": b_f.get("details"),
            "details_simulated": s_f.get("details"),
        })

    is_recommended = (improved_count > 0 and regressed_count == 0)

    # 7. Build delta summary string
    changes_str = ", ".join(changes_list) if changes_list else "No rule status transitions"
    rec_str = "YES" if is_recommended else "NO"
    delta_summary = (
        f"Simulated +{delta_qty} units ({condition}). "
        f"Baseline: {b_fails} FAIL, {b_unknowns} UNKNOWN. "
        f"Simulated: {s_fails} FAIL, {s_unknowns} UNKNOWN. "
        f"Changes: {changes_str}. Recommended: {rec_str}."
    )[:1000]

    # 8. Persist scenario run in Db2 SCENARIO_RUNS
    params_json = json.dumps({
        "delta_quantity": delta_qty,
        "condition": condition,
        "received_on": received_on,
        "notes": notes,
    })

    ins_sql = """
        INSERT INTO scenario_runs 
        (case_id, simulation_type, parameters, original_findings_count, simulated_findings_count, delta_summary, is_recommended)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    ins_stmt = ibm_db.prepare(conn, ins_sql)
    ibm_db.execute(ins_stmt, (
        case_id,
        simulation_type,
        params_json,
        b_anomalies,
        s_anomalies,
        delta_summary,
        1 if is_recommended else 0,
    ))

    # Retrieve generated scenario run ID
    id_stmt = ibm_db.exec_immediate(conn, "VALUES IDENTITY_VAL_LOCAL()")
    scenario_id = int(ibm_db.fetch_tuple(id_stmt)[0])

    # 9. Record audit event in Db2 AUDIT_EVENTS
    audit_sql = """
        INSERT INTO audit_events (case_id, entity_type, entity_id, event_type, actor, action_details)
        VALUES (?, 'SCENARIO_RUN', ?, 'SIMULATION_EXECUTED', 'SYSTEM', ?)
    """
    audit_stmt = ibm_db.prepare(conn, audit_sql)
    audit_details = f"Counterfactual scenario {simulation_type} executed. ScenarioRun ID: {scenario_id}. Delta: {delta_summary}"
    ibm_db.execute(audit_stmt, (case_id, str(scenario_id), audit_details))

    # Retrieve timestamp
    time_stmt = ibm_db.prepare(conn, "SELECT VARCHAR_FORMAT(created_at, 'YYYY-MM-DD HH24:MI:SS') FROM scenario_runs WHERE id = ?")
    ibm_db.execute(time_stmt, (scenario_id,))
    created_at = str(ibm_db.fetch_tuple(time_stmt)[0])

    return {
        "id": scenario_id,
        "case_id": case_id,
        "simulation_type": simulation_type,
        "parameters": {
            "delta_quantity": delta_qty,
            "condition": condition,
            "received_on": received_on,
            "notes": notes,
        },
        "original_findings_count": b_anomalies,
        "simulated_findings_count": s_anomalies,
        "delta_summary": delta_summary,
        "is_recommended": is_recommended,
        "baseline_state": baseline_state,
        "simulated_state": simulated_state,
        "rule_diff": rule_diff,
        "created_at": created_at,
    }

