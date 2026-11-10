from fastapi import APIRouter, HTTPException
from ..database import db_manager
from ..schemas.models import ApprovalAction

router = APIRouter(tags=["Human Approvals & Governance"])

@router.get("/approvals")
def list_approvals():
    """Lists all pending and resolved administrative approval requests."""
    approvals = db_manager.get_approvals()
    return {"count": len(approvals), "approvals": approvals}

@router.post("/approvals/{approval_id}/approve")
def approve_action(approval_id: str, payload: ApprovalAction):
    """
    Approves a proposed containment action.
    Executes safe simulated remediation and commits an immutable audit record into IBM Db2.
    """
    db_manager.update_approval(
        approval_id=approval_id,
        status="APPROVED",
        reviewer=payload.reviewer,
        notes=payload.notes or "Approved by authorized security administrator."
    )
    db_manager.log_audit(
        action="CONTAINMENT_EXECUTED",
        executed_by=payload.reviewer,
        query=f"FORCE APPLICATION (USER REPORT_USER); -- Executed approval {approval_id}"
    )
    return {
        "message": f"Action {approval_id} approved and executed successfully.",
        "approval_id": approval_id,
        "status": "APPROVED",
        "reviewer": payload.reviewer
    }

@router.post("/approvals/{approval_id}/reject")
def reject_action(approval_id: str, payload: ApprovalAction):
    """Rejects a proposed containment action with justification."""
    db_manager.update_approval(
        approval_id=approval_id,
        status="REJECTED",
        reviewer=payload.reviewer,
        notes=payload.notes or "Rejected by reviewer as false positive."
    )
    db_manager.log_audit(
        action="CONTAINMENT_REJECTED",
        executed_by=payload.reviewer,
        query=f"Approval {approval_id} rejected with notes: {payload.notes}"
    )
    return {
        "message": f"Action {approval_id} rejected.",
        "approval_id": approval_id,
        "status": "REJECTED",
        "reviewer": payload.reviewer
    }
