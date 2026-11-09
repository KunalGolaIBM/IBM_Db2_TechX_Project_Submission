"""
ClaimGuard AI - Verification Workflow Router
Triggers and monitors the multi-agent LangGraph workflow for insurance claims.
"""

from fastapi import APIRouter, HTTPException, status
from ..agents.workflow import run_claim_verification
from ..database.repository import repository

router = APIRouter(prefix="/api/verification", tags=["Agentic Verification"])


@router.post("/{claim_id}")
def trigger_claim_verification(claim_id: str):
    """
    Executes the autonomous LangGraph verification workflow:
    Document Agent -> Database Verification Agent -> Fraud Detection Agent ->
    Decision Support Agent -> Supervisor Agent.
    """
    claim = repository.get_claim_by_id(claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim '{claim_id}' not found in IBM Db2."
        )

    try:
        final_state = run_claim_verification(claim_id)
        return {
            "status": "success",
            "claim_id": claim_id,
            "completed": final_state.get("completed", False),
            "current_step": final_state.get("current_step"),
            "db_verification": final_state.get("db_verification"),
            "fraud_analysis": final_state.get("fraud_analysis"),
            "decision_output": final_state.get("decision_output"),
            "extracted_docs_count": len(final_state.get("extracted_docs", [])),
            "errors": final_state.get("errors", [])
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent verification failed: {str(e)}"
        )


@router.get("/{claim_id}")
def get_claim_verification_status(claim_id: str):
    """Retrieves current verification state, logs, and fraud alerts for a claim."""
    claim = repository.get_claim_by_id(claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim '{claim_id}' not found in IBM Db2."
        )

    logs = repository.get_logs_by_claim(claim_id)
    alerts = repository.get_alerts_by_claim(claim_id)

    return {
        "claim_id": claim_id,
        "status": claim.get("STATUS"),
        "risk_score": float(claim.get("RISK_SCORE") or 0.0),
        "risk_level": claim.get("RISK_LEVEL", "LOW"),
        "decision_notes": claim.get("DECISION_NOTES"),
        "reviewed_by": claim.get("REVIEWED_BY"),
        "fraud_alerts_count": len(alerts),
        "audit_logs_count": len(logs),
        "audit_logs": logs,
        "fraud_alerts": alerts
    }
