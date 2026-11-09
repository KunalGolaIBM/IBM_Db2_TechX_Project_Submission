"""
ClaimGuard AI - Supervisor Agent & LangGraph Workflow Orchestrator
Coordinates all specialized agents (Document, Database, Fraud, Decision)
using LangGraph StateGraph, managing shared state and execution audit trails.
"""

import logging
import time
from typing import Any, Dict, List
from langgraph.graph import END, START, StateGraph
from ..database.repository import repository
from .database_agent import database_agent
from .decision_agent import decision_agent
from .document_agent import document_agent
from .fraud_agent import fraud_agent
from .state import ClaimGuardState

logger = logging.getLogger("claimguard.agent.supervisor")


# -----------------------------------------------------------------------------
# LangGraph Workflow Nodes
# -----------------------------------------------------------------------------
def document_extraction_node(state: ClaimGuardState) -> Dict[str, Any]:
    """Node 1: Parses all attached claim documents and extracts medical billing data."""
    logger.info("LangGraph Node: [document_extraction_node] executing for claim %s", state.get("claim_id"))
    documents = state.get("documents", [])
    extracted_docs = []

    for doc in documents:
        file_path = doc.get("FILE_PATH", "")
        doc_id = doc.get("DOCUMENT_ID")
        try:
            extracted = document_agent.extract(file_path=file_path, document_id=doc_id)
            extracted_docs.append(extracted.model_dump())
        except Exception as e:
            logger.warning("Error in document extraction for %s: %s", file_path, e)

    return {
        "extracted_docs": extracted_docs,
        "current_step": "DATABASE_VERIFICATION"
    }


def database_verification_node(state: ClaimGuardState) -> Dict[str, Any]:
    """Node 2: Queries IBM Db2 to cross-examine customer, policy, and coverage constraints."""
    logger.info("LangGraph Node: [database_verification_node] executing for claim %s", state.get("claim_id"))
    claim_data = state.get("claim_data", {})
    try:
        db_res = database_agent.verify(claim_data)
        return {
            "db_verification": db_res.model_dump(),
            "current_step": "FRAUD_DETECTION"
        }
    except Exception as e:
        logger.error("Error in database verification node: %s", e)
        return {
            "errors": state.get("errors", []) + [f"Database agent error: {str(e)}"],
            "current_step": "FRAUD_DETECTION"
        }


def fraud_detection_node(state: ClaimGuardState) -> Dict[str, Any]:
    """Node 3: Checks for duplicate document hashes, invoice collisions, and date anomalies."""
    logger.info("LangGraph Node: [fraud_detection_node] executing for claim %s", state.get("claim_id"))
    claim_data = state.get("claim_data", {})
    documents = state.get("documents", [])
    extracted_docs = state.get("extracted_docs", [])

    try:
        fraud_res = fraud_agent.analyze(
            claim_data=claim_data,
            documents=documents,
            extracted_docs=extracted_docs
        )
        return {
            "fraud_analysis": fraud_res.model_dump(),
            "current_step": "DECISION_SUPPORT"
        }
    except Exception as e:
        logger.error("Error in fraud detection node: %s", e)
        return {
            "errors": state.get("errors", []) + [f"Fraud agent error: {str(e)}"],
            "current_step": "DECISION_SUPPORT"
        }


def decision_support_node(state: ClaimGuardState) -> Dict[str, Any]:
    """Node 4: Synthesizes multi-agent signals into a transparent risk score and recommendation."""
    logger.info("LangGraph Node: [decision_support_node] executing for claim %s", state.get("claim_id"))
    claim_data = state.get("claim_data", {})
    db_data = state.get("db_verification") or {}
    fraud_data = state.get("fraud_analysis") or {}

    from .state import DbVerificationResult, FraudAnalysisResult

    db_res = DbVerificationResult(**db_data)
    fraud_res = FraudAnalysisResult(**fraud_data)

    try:
        dec_res = decision_agent.evaluate(
            claim_data=claim_data,
            db_result=db_res,
            fraud_result=fraud_res,
            extracted_docs=state.get("extracted_docs")
        )
        return {
            "decision_output": dec_res.model_dump(),
            "current_step": "SUPERVISOR_FINALIZE"
        }
    except Exception as e:
        logger.error("Error in decision support node: %s", e)
        return {
            "errors": state.get("errors", []) + [f"Decision agent error: {str(e)}"],
            "current_step": "SUPERVISOR_FINALIZE"
        }


def supervisor_finalize_node(state: ClaimGuardState) -> Dict[str, Any]:
    """Node 5: Supervisor logs final summary and concludes LangGraph workflow."""
    claim_id = state.get("claim_id", "UNKNOWN")
    logger.info("LangGraph Node: [supervisor_finalize_node] wrapping up verification for claim %s", claim_id)

    dec = state.get("decision_output") or {}
    rec = dec.get("recommendation", "UNKNOWN")
    score = dec.get("risk_score", 0.0)

    # Record Supervisor audit trail in IBM Db2 VERIFICATION_LOGS
    log_entry = {
        "CLAIM_ID": claim_id,
        "AGENT_NAME": "SUPERVISOR_AGENT",
        "ACTION": "COMPLETE_VERIFICATION_WORKFLOW",
        "STATUS": "SUCCESS",
        "DETAILS": f"LangGraph workflow finalized. Final recommendation: {rec} (Risk Score: {score}/100)",
        "EXECUTION_TIME_MS": 10
    }
    try:
        repository.create_log(log_entry)
    except Exception as e:
        logger.debug("Could not record supervisor log: %s", e)

    return {
        "completed": True,
        "current_step": "COMPLETED"
    }


# -----------------------------------------------------------------------------
# Construct LangGraph Workflow
# -----------------------------------------------------------------------------
def build_claimguard_workflow():
    """Builds and compiles the multi-agent LangGraph workflow."""
    workflow = StateGraph(ClaimGuardState)

    # Add Nodes
    workflow.add_node("document_extraction", document_extraction_node)
    workflow.add_node("database_verification", database_verification_node)
    workflow.add_node("fraud_detection", fraud_detection_node)
    workflow.add_node("decision_support", decision_support_node)
    workflow.add_node("supervisor_finalize", supervisor_finalize_node)

    # Add Directed Edges
    workflow.add_edge(START, "document_extraction")
    workflow.add_edge("document_extraction", "database_verification")
    workflow.add_edge("database_verification", "fraud_detection")
    workflow.add_edge("fraud_detection", "decision_support")
    workflow.add_edge("decision_support", "supervisor_finalize")
    workflow.add_edge("supervisor_finalize", END)

    return workflow.compile()


# Global compiled workflow instance
claimguard_orchestrator = build_claimguard_workflow()


def run_claim_verification(claim_id: str) -> Dict[str, Any]:
    """
    Orchestration entry point: retrieves claim and documents from Db2 repository,
    initializes workflow state, executes the LangGraph graph, and returns final state.
    """
    claim = repository.get_claim_by_id(claim_id)
    if not claim:
        raise ValueError(f"Claim '{claim_id}' not found in IBM Db2 CLAIM_RECORDS.")

    documents = repository.get_documents_by_claim(claim_id)

    initial_state: ClaimGuardState = {
        "claim_id": claim_id,
        "claim_data": claim,
        "documents": documents,
        "extracted_docs": [],
        "db_verification": None,
        "fraud_analysis": None,
        "decision_output": None,
        "audit_logs": [],
        "errors": [],
        "current_step": "INITIATED",
        "completed": False
    }

    start_time = time.time()
    logger.info("Starting LangGraph multi-agent verification for claim %s", claim_id)
    final_state = claimguard_orchestrator.invoke(initial_state)
    elapsed = round(time.time() - start_time, 3)
    logger.info("LangGraph verification for %s completed in %s seconds", claim_id, elapsed)

    return dict(final_state)
