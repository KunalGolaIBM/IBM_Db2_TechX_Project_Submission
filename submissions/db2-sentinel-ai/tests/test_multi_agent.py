"""
Tests for LangGraph multi-agent forensic pipeline and Db2 checkpoint persistence.
"""

import pytest
from src.db.schema import initialize_schema
from src.db.seed_data import seed_database
from src.db.checkpointer import Db2AgentCheckpointer
from src.agents.workflow import SentinelWorkflow


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    initialize_schema()
    seed_database(force=True)


def test_workflow_structuring_case():
    workflow = SentinelWorkflow()
    result = workflow.run_investigation("TX-STRUCT-01", auto_approve=True)

    assert result["tx_id"] == "TX-STRUCT-01"
    assert result["risk_score"] >= 75
    assert result["recommended_action"] in ("FREEZE_AND_FILE_SAR", "ENHANCED_DUE_DILIGENCE")
    assert result["supervisor_decision"] in ("APPROVED_ENFORCEMENT", "ENHANCED_MONITORING")
    assert result["audit_signature"] is not None
    assert len(result["agent_logs"]) >= 5


def test_workflow_circular_routing_case():
    workflow = SentinelWorkflow()
    result = workflow.run_investigation("TX-LOOP-01", auto_approve=True)

    assert result["tx_id"] == "TX-LOOP-01"
    assert result["risk_score"] >= 85
    assert len(result["circular_loops"]) > 0
    assert result["recommended_action"] == "FREEZE_AND_FILE_SAR"


def test_workflow_normal_transaction_case():
    workflow = SentinelWorkflow()
    result = workflow.run_investigation("TX-NORM-01", auto_approve=True)

    assert result["tx_id"] == "TX-NORM-01"
    assert result["risk_score"] < 65
    assert result["recommended_action"] == "CLEAR_ALERT"


def test_db2_checkpoint_persistence():
    workflow = SentinelWorkflow()
    result = workflow.run_investigation("TX-STRUCT-01", auto_approve=True)
    thread_id = result["thread_id"]

    checkpointer = Db2AgentCheckpointer()
    history = checkpointer.get_thread_history(thread_id)

    # Should have checkpoints saved across all 5 agents
    assert len(history) == 5
    agent_names = [h["agent_name"] for h in history]
    assert "ScreeningAgent" in agent_names
    assert "ForensicInvestigatorAgent" in agent_names
    assert "SupervisorAgent" in agent_names
