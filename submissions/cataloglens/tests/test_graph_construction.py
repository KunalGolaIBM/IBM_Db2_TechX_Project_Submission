"""
Tests for LangGraph Investigation Workflow execution.
"""
import pytest
from backend.graph.investigation_graph import create_investigation_graph


def test_investigation_graph_execution():
    graph = create_investigation_graph()
    initial_state = {
        "schema_name": "ENTERPRISE",
        "selected_table": "CUSTOMER_MST",
        "investigation_question": "Explain purpose of this table",
        "use_demo": True,
        "metadata": None,
        "declared_relationships": [],
        "inferred_relationships": [],
        "table_evidence_ledger": [],
        "ai_understanding": None,
        "validated_evidence": [],
        "discrepancies": [],
        "final_report": None,
        "errors": [],
    }

    final_state = graph.invoke(initial_state)

    assert final_state is not None
    assert len(final_state.get("errors", [])) == 0
    report = final_state.get("final_report")
    assert report is not None
    assert report["table_name"] == "CUSTOMER_MST"
    assert report["table_understanding"] is not None
    assert len(report["table_understanding"]["important_columns"]) > 0
    assert report["total_evidence_claims"] > 0
