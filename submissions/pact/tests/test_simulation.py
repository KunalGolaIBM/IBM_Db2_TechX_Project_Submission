"""Integration tests for counterfactual simulation service backed by genuine IBM Db2."""

from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient

from api.db import get_connection, ibm_db
from api.main import app

client = TestClient(app)

SOURCE_TABLES = [
    "BUYERS", "SUPPLIERS", "ITEMS", "REQUISITIONS",
    "PURCHASE_ORDERS", "PO_LINES", "GOODS_RECEIPTS", "SUPPLIER_INVOICES"
]


def get_source_table_counts():
    conn = get_connection()
    try:
        counts = {}
        for tbl in SOURCE_TABLES:
            stmt = ibm_db.exec_immediate(conn, f"SELECT COUNT(*) FROM {tbl}")
            counts[tbl] = int(ibm_db.fetch_tuple(stmt)[0])
        return counts
    finally:
        ibm_db.close(conn)


def test_simulation_valid_add_acceptable_receipt():
    """Verify executing ADD_ACCEPTABLE_RECEIPT calculates in-memory rule diff and persists in Db2."""
    counts_before = get_source_table_counts()
    assert sum(counts_before.values()) == 492

    # Find a case with QTY-01 or DOC-01 anomaly
    list_resp = client.get("/api/v1/cases?status=OPEN&limit=10")
    assert list_resp.status_code == 200
    cases = list_resp.json()["items"]
    assert len(cases) > 0

    target_case = None
    target_case_detail = None
    for c in cases:
        det = client.get(f"/api/v1/cases/{c['id']}").json()
        qty_finding = next((f for f in det["findings"] if f["rule_id"] in ("QTY-01", "DOC-01") and f["status"] in ("FAIL", "UNKNOWN")), None)
        if qty_finding:
            target_case = c
            target_case_detail = det
            break

    assert target_case is not None, "Expected at least one case with QTY-01 or DOC-01 anomaly"
    case_id = target_case["id"]

    # Retrieve case evidence to see the exact gap
    ev_resp = client.get(f"/api/v1/cases/{case_id}/evidence")
    assert ev_resp.status_code == 200
    facts = ev_resp.json()["reconciliation_facts"]
    gap = facts.get("total_invoiced_qty", 0) - (facts.get("acceptable_received_qty") or 0)
    delta_qty = gap if gap > 0 else 10

    payload = {
        "simulation_type": "ADD_ACCEPTABLE_RECEIPT",
        "parameters": {
            "delta_quantity": delta_qty,
            "condition": "good",
            "received_on": "2026-05-02",
            "notes": "Testing counterfactual delivery fulfillment",
        },
    }

    # Execute simulation
    sim_resp = client.post(f"/api/v1/cases/{case_id}/simulations", json=payload)
    assert sim_resp.status_code == 200
    sim_data = sim_resp.json()

    # Validate response structure
    assert sim_data["id"] > 0
    assert sim_data["case_id"] == case_id
    assert sim_data["simulation_type"] == "ADD_ACCEPTABLE_RECEIPT"
    assert sim_data["parameters"]["delta_quantity"] == delta_qty
    assert sim_data["parameters"]["condition"] == "good"
    assert "delta_summary" in sim_data
    assert isinstance(sim_data["is_recommended"], bool)

    # Validate state transitions
    assert sim_data["baseline_state"]["receipt_count"] < sim_data["simulated_state"]["receipt_count"]
    assert sim_data["simulated_state"]["accepted_qty"] == sim_data["baseline_state"]["accepted_qty"] + delta_qty
    assert len(sim_data["rule_diff"]) == 7

    # Validate direct Db2 persistence in SCENARIO_RUNS
    conn = get_connection()
    try:
        check_stmt = ibm_db.prepare(conn, "SELECT id, case_id, simulation_type, is_recommended, delta_summary FROM scenario_runs WHERE id = ?")
        ibm_db.execute(check_stmt, (sim_data["id"],))
        run_row = ibm_db.fetch_assoc(check_stmt)
        assert run_row is not None
        assert int(run_row["CASE_ID"]) == case_id
        assert run_row["SIMULATION_TYPE"].strip() == "ADD_ACCEPTABLE_RECEIPT"

        # Validate direct Db2 persistence in AUDIT_EVENTS
        audit_stmt = ibm_db.prepare(conn, "SELECT event_type, actor FROM audit_events WHERE entity_type = 'SCENARIO_RUN' AND entity_id = ?")
        ibm_db.execute(audit_stmt, (str(sim_data["id"]),))
        audit_row = ibm_db.fetch_assoc(audit_stmt)
        assert audit_row is not None
        assert audit_row["EVENT_TYPE"].strip() == "SIMULATION_EXECUTED"
    finally:
        ibm_db.close(conn)

    # Verify source tables remain 100% untouched
    counts_after = get_source_table_counts()
    assert counts_before == counts_after
    assert counts_after["GOODS_RECEIPTS"] == 89
    assert sum(counts_after.values()) == 492


def test_simulation_invalid_type_rejected():
    """Verify that unsupported simulation type is rejected with 400 and consistent error envelope."""
    payload = {
        "simulation_type": "UNSUPPORTED_TYPE_XYZ",
        "parameters": {
            "delta_quantity": 10,
        },
    }
    resp = client.post("/api/v1/cases/1/simulations", json=payload)
    assert resp.status_code == 400
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "UNSUPPORTED_SIMULATION_TYPE"
    assert "unsupported" in data["error"]["message"].lower()
    assert data["error"]["retryable"] is False


def test_simulation_invalid_parameters_rejected():
    """Verify that invalid parameters (zero, negative, missing) are rejected with 422 or 400."""
    # 1. Negative quantity
    resp_neg = client.post("/api/v1/cases/1/simulations", json={
        "simulation_type": "ADD_ACCEPTABLE_RECEIPT",
        "parameters": {"delta_quantity": -5},
    })
    assert resp_neg.status_code == 422
    assert "error" in resp_neg.json()

    # 2. Zero quantity
    resp_zero = client.post("/api/v1/cases/1/simulations", json={
        "simulation_type": "ADD_ACCEPTABLE_RECEIPT",
        "parameters": {"delta_quantity": 0},
    })
    assert resp_zero.status_code == 422
    assert "error" in resp_zero.json()

    # 3. Missing delta_quantity
    resp_miss = client.post("/api/v1/cases/1/simulations", json={
        "simulation_type": "ADD_ACCEPTABLE_RECEIPT",
        "parameters": {},
    })
    assert resp_miss.status_code == 422
    assert "error" in resp_miss.json()


def test_simulation_nonexistent_case_rejected():
    """Verify that running simulation on non-existent case returns 404."""
    payload = {
        "simulation_type": "ADD_ACCEPTABLE_RECEIPT",
        "parameters": {"delta_quantity": 10},
    }
    resp = client.post("/api/v1/cases/999999/simulations", json=payload)
    assert resp.status_code == 404
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "CASE_NOT_FOUND"
    assert data["error"]["retryable"] is False


def test_simulation_repeated_execution_consistency():
    """Verify repeated simulations on the same case produce consistent results without data corruption."""
    counts_before = get_source_table_counts()

    # Get valid case id dynamically
    list_resp = client.get("/api/v1/cases?limit=1")
    first_case_id = list_resp.json()["items"][0]["id"]

    payload = {
        "simulation_type": "ADD_ACCEPTABLE_RECEIPT",
        "parameters": {"delta_quantity": 15, "notes": "Repeatability test"},
    }

    resp1 = client.post(f"/api/v1/cases/{first_case_id}/simulations", json=payload)
    resp2 = client.post(f"/api/v1/cases/{first_case_id}/simulations", json=payload)

    assert resp1.status_code == 200
    assert resp2.status_code == 200

    d1, d2 = resp1.json(), resp2.json()
    assert d1["id"] != d2["id"]  # Distinct persistent run IDs
    assert d1["baseline_state"] == d2["baseline_state"]
    assert d1["simulated_state"] == d2["simulated_state"]
    assert d1["is_recommended"] == d2["is_recommended"]

    counts_after = get_source_table_counts()
    assert counts_before == counts_after


def test_simulation_transaction_rollback_on_failure():
    """Verify that if an error occurs within simulation transaction, all changes roll back."""
    from api.services.simulations import execute_simulation
    from api.db import db_transaction

    # Get valid case id dynamically
    list_resp = client.get("/api/v1/cases?limit=1")
    first_case_id = list_resp.json()["items"][0]["id"]

    # Record scenario_runs count before
    conn = get_connection()
    try:
        cnt_stmt = ibm_db.exec_immediate(conn, "SELECT COUNT(*) FROM scenario_runs")
        count_before = int(ibm_db.fetch_tuple(cnt_stmt)[0])
    finally:
        ibm_db.close(conn)

    # Intentionally trigger an error after insert by patching or executing an illegal statement in transaction
    with pytest.raises(Exception):
        with db_transaction() as txn_conn:
            # Insert a scenario run
            execute_simulation(
                txn_conn,
                case_id=first_case_id,
                simulation_type="ADD_ACCEPTABLE_RECEIPT",
                parameters={"delta_quantity": 10},
            )
            # Intentionally cause an error before commit
            ibm_db.exec_immediate(txn_conn, "SELECT * FROM NON_EXISTENT_TABLE_TRIGGERING_ROLLBACK")

    # Verify scenario_runs count after failed transaction is unchanged
    conn2 = get_connection()
    try:
        cnt_stmt2 = ibm_db.exec_immediate(conn2, "SELECT COUNT(*) FROM scenario_runs")
        count_after = int(ibm_db.fetch_tuple(cnt_stmt2)[0])
        assert count_after == count_before
    finally:
        ibm_db.close(conn2)
