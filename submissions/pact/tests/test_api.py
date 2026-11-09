"""Contract and integration tests for PACT FastAPI service backed by genuine IBM Db2."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health_live():
    """Verify liveness probe returns 200 ALIVE."""
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ALIVE"}


def test_health_ready_live_db2():
    """Verify readiness probe confirms connection to live Db2 PACTDB."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert data["db2_connected"] is True
    assert data["database"] == "PACTDB"
    assert data["server_version"] == "12.01.0500"


def test_reconciliation_run_populates_db2_cases():
    """Verify executing reconciliation run analyzes all 91 PO lines and populates Db2 tables."""
    response = client.post("/api/v1/reconciliation-runs")
    assert response.status_code == 200
    data = response.json()
    assert data["po_lines_reconciled"] == 91
    assert data["total_evaluations"] == 637
    assert data["pass_count"] == 396
    assert data["fail_count"] == 151
    assert data["unknown_count"] == 90
    assert data["cases_created_or_updated"] > 0


def test_list_cases_pagination_and_filters():
    """Verify listing cases with pagination and status/search filters."""
    # 1. Unfiltered page 1
    response = client.get("/api/v1/cases?page=1&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["page"] == 1
    assert data["limit"] == 10
    assert len(data["items"]) <= 10
    assert data["total"] > 0

    first_case = data["items"][0]
    assert "id" in first_case
    assert "case_number" in first_case
    assert "po_line_id" in first_case
    assert "status" in first_case
    assert "priority" in first_case
    assert "findings_count" in first_case
    assert first_case["findings_count"] > 0

    # 2. Status filter
    response_open = client.get("/api/v1/cases?status=OPEN")
    assert response_open.status_code == 200
    open_cases = response_open.json()["items"]
    assert all(c["status"] == "OPEN" for c in open_cases)

    # 3. Search filter
    response_search = client.get(f"/api/v1/cases?search={first_case['po_number']}")
    assert response_search.status_code == 200
    search_cases = response_search.json()["items"]
    assert len(search_cases) >= 1
    assert any(c["po_number"] == first_case["po_number"] for c in search_cases)


def test_get_case_detail():
    """Verify retrieving detailed case information including all rule findings."""
    # Get first case ID
    list_resp = client.get("/api/v1/cases?limit=1")
    first_case_id = list_resp.json()["items"][0]["id"]

    response = client.get(f"/api/v1/cases/{first_case_id}")
    assert response.status_code == 200
    detail = response.json()
    assert detail["id"] == first_case_id
    assert "buyer_name" in detail
    assert "supplier_name" in detail
    assert "findings" in detail
    assert len(detail["findings"]) > 0

    finding = detail["findings"][0]
    assert "rule_id" in finding
    assert "rule_name" in finding
    assert finding["status"] in ("FAIL", "UNKNOWN", "PASS")
    assert finding["severity"] in ("HIGH", "MEDIUM", "LOW", "INFO")


def test_get_case_evidence_exact_db2_source_records():
    """Verify retrieving exact Db2 source record references (table and id)."""
    list_resp = client.get("/api/v1/cases?limit=1")
    first_case_id = list_resp.json()["items"][0]["id"]

    response = client.get(f"/api/v1/cases/{first_case_id}/evidence")
    assert response.status_code == 200
    evidence = response.json()

    assert evidence["case_id"] == first_case_id
    assert "reconciliation_facts" in evidence

    # Check purchase_order reference
    assert evidence["purchase_order"]["table"] == "purchase_orders"
    assert isinstance(evidence["purchase_order"]["id"], int)
    assert "po_number" in evidence["purchase_order"]["record_data"]

    # Check po_line reference
    assert evidence["po_line"]["table"] == "po_lines"
    assert isinstance(evidence["po_line"]["id"], int)

    # Check receipts & invoices references
    for r in evidence["receipts"]:
        assert r["table"] == "goods_receipts"
        assert isinstance(r["id"], int)
        assert "received_qty" in r["record_data"]

    for inv in evidence["invoices"]:
        assert inv["table"] == "supplier_invoices"
        assert isinstance(inv["id"], int)
        assert "invoiced_qty" in inv["record_data"]


def test_case_not_found_consistent_error_envelope():
    """Verify 404 response adheres to exact error envelope shape."""
    response = client.get("/api/v1/cases/999999")
    assert response.status_code == 404
    err_body = response.json()
    assert "error" in err_body
    assert err_body["error"]["code"] == "CASE_NOT_FOUND"
    assert "not found" in err_body["error"]["message"].lower()
    assert err_body["error"]["retryable"] is False


def test_optimistic_locking_and_review_workflow():
    """Verify optimistic concurrency control and atomic review recording."""
    # Pick a case
    list_resp = client.get("/api/v1/cases?status=OPEN&limit=1")
    cases = list_resp.json()["items"]
    assert len(cases) > 0, "Expected at least one OPEN case"
    case = cases[0]
    case_id = case["id"]
    initial_version = case["version"]

    # 1. Stale version attempt must fail with 409 Conflict
    stale_payload = {
        "decision": "FINDING_CONFIRMED",
        "reviewer": "Auditor Dave",
        "reviewer_notes": "Attempting review with wrong version",
        "rationale": "Testing conflict detection",
        "expected_version": initial_version + 99,
    }
    conflict_resp = client.post(f"/api/v1/cases/{case_id}/submit-review", json=stale_payload)
    assert conflict_resp.status_code == 409
    err_data = conflict_resp.json()
    assert err_data["error"]["code"] == "CONCURRENCY_CONFLICT"
    assert err_data["error"]["retryable"] is True

    # 2. Valid review submission with matching version succeeds
    valid_payload = {
        "decision": "FINDING_CONFIRMED",
        "reviewer": "Senior Auditor Alice",
        "reviewer_notes": "Confirmed quantity mismatch against delivery receipt log.",
        "rationale": "Rule QTY-01 exceeded tolerance.",
        "expected_version": initial_version,
    }
    review_resp = client.post(f"/api/v1/cases/{case_id}/submit-review", json=valid_payload)
    assert review_resp.status_code == 200
    review_data = review_resp.json()
    assert review_data["case_id"] == case_id
    assert review_data["decision"] == "FINDING_CONFIRMED"
    assert review_data["new_case_status"] == "REVIEWED"
    assert review_data["new_case_version"] == initial_version + 1

    # 3. Check updated case state
    updated_resp = client.get(f"/api/v1/cases/{case_id}")
    assert updated_resp.status_code == 200
    assert updated_resp.json()["status"] == "REVIEWED"
    assert updated_resp.json()["version"] == initial_version + 1

    # 4. Check audit events log
    audit_resp = client.get(f"/api/v1/cases/{case_id}/audit")
    assert audit_resp.status_code == 200
    audit_events = audit_resp.json()
    assert len(audit_events) >= 1
    assert any(ev["event_type"] == "REVIEW_RECORDED" for ev in audit_events)
    review_event = next(ev for ev in audit_events if ev["event_type"] == "REVIEW_RECORDED")
    assert review_event["actor"] == "Senior Auditor Alice"

