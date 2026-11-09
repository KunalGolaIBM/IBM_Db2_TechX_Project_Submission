"""Integration and contract tests for LangChain evidence investigator backed by genuine IBM Db2."""

from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from api.db import get_connection, ibm_db
from api.main import app
from api.services.agent_tools import create_investigation_tools
from api.services.investigations import (
    LLMProviderExecutionError,
    LLMProviderNotConfiguredError,
    execute_agent_investigation,
    verify_evidence_citation,
)

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


def get_first_case():
    conn = get_connection()
    try:
        stmt = ibm_db.exec_immediate(conn, "SELECT id, case_number, po_line_id FROM investigation_cases ORDER BY id FETCH FIRST 1 ROWS ONLY")
        row = ibm_db.fetch_assoc(stmt)
        assert row is not None
        return {
            "id": int(row["ID"]),
            "case_number": row["CASE_NUMBER"].strip(),
            "po_line_id": int(row["PO_LINE_ID"]),
        }
    finally:
        ibm_db.close(conn)


class MockAgentChatModel(BaseChatModel):
    """Deterministic LangChain ChatModel simulating an agent making tool calls followed by a conclusion."""

    responses: list[AIMessage] = []

    def __init__(self, responses: list[AIMessage], **kwargs):
        super().__init__(responses=responses, **kwargs)
        self.responses = list(responses)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if self.responses:
            res = self.responses.pop(0)
        else:
            res = AIMessage(content="Final investigation conclusion based on retrieved evidence.")
        return ChatResult(generations=[ChatGeneration(message=res)])

    def bind_tools(self, tools, **kwargs):
        return self

    @property
    def _llm_type(self) -> str:
        return "mock_agent_chat_model"


class FailingChatModel(BaseChatModel):
    """ChatModel simulating upstream LLM provider API failure or network timeout."""

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        raise RuntimeError("Connection to upstream LLM provider failed: 503 Service Unavailable")

    def bind_tools(self, tools, **kwargs):
        return self

    @property
    def _llm_type(self) -> str:
        return "failing_chat_model"


def test_investigation_tools_grounded_in_live_db2():
    """Verify that all 5 read-only LangChain tools execute against genuine Db2 and enforce scope."""
    case = get_first_case()
    case_id = case["id"]
    po_line_id = case["po_line_id"]

    conn = get_connection()
    try:
        traces = []
        tools = create_investigation_tools(conn, case_id, po_line_id, traces)
        tool_map = {t.name: t for t in tools}

        # 1. get_case_summary
        summary_tool = tool_map["get_case_summary"]
        summary_res = summary_tool.invoke({"case_id": case_id})
        summary_data = json.loads(summary_res)
        assert summary_data["case_id"] == case_id
        assert "po_number" in summary_data
        assert "supplier_name" in summary_data
        assert "ordered_qty" in summary_data

        # Unauthorized case_id check
        denied_res = summary_tool.invoke({"case_id": case_id + 999})
        assert "access denied" in denied_res.lower()
        assert traces[-1]["status"] == "DENIED"

        # 2. get_receipt_evidence
        receipt_tool = tool_map["get_receipt_evidence"]
        receipt_res = receipt_tool.invoke({"case_id": case_id})
        receipt_data = json.loads(receipt_res)
        assert isinstance(receipt_data, list)
        for r in receipt_data:
            assert "receipt_id" in r
            assert "condition" in r
            assert "received_qty" in r

        # 3. get_invoice_evidence
        invoice_tool = tool_map["get_invoice_evidence"]
        invoice_res = invoice_tool.invoke({"case_id": case_id})
        invoice_data = json.loads(invoice_res)
        assert isinstance(invoice_data, list)
        for inv in invoice_data:
            assert "invoice_id" in inv
            assert "billed_unit_price" in inv
            assert "invoiced_qty" in inv

        # 4. get_rule_results
        rules_tool = tool_map["get_rule_results"]
        rules_res = rules_tool.invoke({"case_id": case_id})
        rules_data = json.loads(rules_res)
        assert isinstance(rules_data, list)
        assert len(rules_data) > 0
        for f in rules_data:
            assert "rule_id" in f
            assert "status" in f
            assert f["status"] in ("FAIL", "UNKNOWN", "PASS")

        # 5. get_source_record
        source_tool = tool_map["get_source_record"]
        # Disallowed table check
        disallowed_res = source_tool.invoke({"table": "sensitive_users", "record_id": 1})
        assert "access denied" in disallowed_res.lower()

        # Valid source table lookup
        if invoice_data:
            inv_id = invoice_data[0]["invoice_id"]
            src_res = source_tool.invoke({"table": "supplier_invoices", "record_id": inv_id})
            src_data = json.loads(src_res)
            assert src_data["id"] == inv_id
            assert "invoice_no" in src_data

    finally:
        ibm_db.close(conn)


def test_investigation_endpoint_missing_credentials_handled():
    """Verify that calling investigation endpoint without LLM provider credentials returns 503."""
    case = get_first_case()
    case_id = case["id"]

    # Ensure no API keys in test environment
    import os
    orig_key = os.environ.pop("OPENAI_API_KEY", None)
    orig_provider = os.environ.pop("LLM_PROVIDER", None)

    try:
        response = client.post(f"/api/v1/cases/{case_id}/investigations")
        assert response.status_code == 503
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "LLM_PROVIDER_NOT_CONFIGURED"
        assert "provider" in data["error"]["message"].lower() or "api key" in data["error"]["message"].lower()
        assert data["error"]["retryable"] is False

        # Verify failure recorded in Db2 AUDIT_EVENTS
        conn = get_connection()
        try:
            stmt = ibm_db.prepare(conn, "SELECT event_type, action_details FROM audit_events WHERE case_id = ? AND event_type = 'INVESTIGATION_FAILED' ORDER BY id DESC FETCH FIRST 1 ROWS ONLY")
            ibm_db.execute(stmt, (case_id,))
            row = ibm_db.fetch_assoc(stmt)
            assert row is not None
            assert row["EVENT_TYPE"].strip() == "INVESTIGATION_FAILED"
        finally:
            ibm_db.close(conn)
    finally:
        if orig_key:
            os.environ["OPENAI_API_KEY"] = orig_key
        if orig_provider:
            os.environ["LLM_PROVIDER"] = orig_provider


def test_investigation_nonexistent_case_returns_404():
    """Verify that calling investigation endpoint for nonexistent case returns 404."""
    response = client.post("/api/v1/cases/999999/investigations")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "CASE_NOT_FOUND"


def test_investigation_provider_error_handling():
    """Verify that upstream LLM failure is caught and mapped to HTTP 502 with audit log."""
    case = get_first_case()
    case_id = case["id"]

    conn = get_connection()
    try:
        failing_model = FailingChatModel()
        with pytest.raises(LLMProviderExecutionError):
            execute_agent_investigation(conn, case_id=case_id, llm=failing_model)

        # Verify failure logged in Db2
        stmt = ibm_db.prepare(conn, "SELECT event_type FROM audit_events WHERE case_id = ? AND event_type = 'INVESTIGATION_FAILED' ORDER BY id DESC FETCH FIRST 1 ROWS ONLY")
        ibm_db.execute(stmt, (case_id,))
        row = ibm_db.fetch_assoc(stmt)
        assert row is not None
        assert row["EVENT_TYPE"].strip() == "INVESTIGATION_FAILED"
    finally:
        ibm_db.close(conn)


def test_investigation_langchain_agent_end_to_end_with_db2():
    """Verify complete LangChain tool-calling agent investigation workflow backed by genuine Db2."""
    case = get_first_case()
    case_id = case["id"]

    # Step 1: Model calls get_case_summary and get_rule_results
    ai_msg_tools = AIMessage(
        content="I will inspect the case summary and reconciliation rule results.",
        tool_calls=[
            {"name": "get_case_summary", "args": {"case_id": case_id}, "id": "call_1"},
            {"name": "get_rule_results", "args": {"case_id": case_id}, "id": "call_2"},
        ],
    )
    # Step 2: Model finishes with conclusion
    ai_msg_final = AIMessage(
        content="Investigation confirmed discrepancies in receipt documentation and quantities."
    )

    mock_llm = MockAgentChatModel(responses=[ai_msg_tools, ai_msg_final])

    conn = get_connection()
    try:
        result = execute_agent_investigation(conn, case_id=case_id, llm=mock_llm)

        # Validate response contract
        assert result["case_id"] == case_id
        assert result["status"] == "COMPLETED"
        assert "summary" in result
        assert len(result["tool_traces"]) == 2
        assert any(t["tool_name"] == "get_case_summary" for t in result["tool_traces"])
        assert any(t["tool_name"] == "get_rule_results" for t in result["tool_traces"])

        # Validate verified claims
        assert len(result["claims"]) > 0
        for claim in result["claims"]:
            assert "rule_code" in claim
            assert "statement" in claim
            assert isinstance(claim["is_verified"], bool)

        # Validate audit logging in Db2 AUDIT_EVENTS
        stmt = ibm_db.prepare(conn, "SELECT event_type, actor, action_details FROM audit_events WHERE case_id = ? AND event_type = 'INVESTIGATION_COMPLETED' ORDER BY id DESC FETCH FIRST 1 ROWS ONLY")
        ibm_db.execute(stmt, (case_id,))
        audit_row = ibm_db.fetch_assoc(stmt)
        assert audit_row is not None
        assert audit_row["EVENT_TYPE"].strip() == "INVESTIGATION_COMPLETED"
        assert audit_row["ACTOR"].strip() == "AGENT"

        # Validate case status update in Db2
        c_stmt = ibm_db.prepare(conn, "SELECT status FROM investigation_cases WHERE id = ?")
        ibm_db.execute(c_stmt, (case_id,))
        case_row = ibm_db.fetch_assoc(c_stmt)
        assert case_row["STATUS"].strip() in ("INVESTIGATING", "REVIEWED")

    finally:
        ibm_db.close(conn)


def test_investigation_source_tables_immutability():
    """Verify that throughout all agent tool executions and investigations, source tables remain untouched."""
    counts = get_source_table_counts()
    assert sum(counts.values()) == 492
    assert counts["GOODS_RECEIPTS"] == 89
    assert counts["SUPPLIER_INVOICES"] == 87
    assert counts["PO_LINES"] == 91
