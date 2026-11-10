import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException
from app.database.db2_connector import db_connector
from app.models.schemas import ApprovalActionRequest

router = APIRouter(prefix="/responses", tags=["Response Management"])

@router.get("/recommendations")
def get_recommendations(status: Optional[str] = None):
    query = """
        SELECT r.*, i.title as incident_title, i.severity as incident_severity, i.user_id,
               u.full_name as target_user_name, u.email as target_user_email
        FROM RESPONSE_RECOMMENDATIONS r
        LEFT JOIN INCIDENTS i ON r.incident_id = i.incident_id
        LEFT JOIN USER_ACCOUNTS u ON i.user_id = u.user_id
        WHERE 1=1
    """
    params = []
    if status:
        query += " AND r.status = ?"
        params.append(status.upper())
    query += " ORDER BY r.created_at DESC"
    return db_connector.execute_query(query, tuple(params))

@router.post("/{recommendation_id}/action")
def take_recommendation_action(recommendation_id: str, req: ApprovalActionRequest):
    rows = db_connector.execute_query(
        """SELECT r.*, i.user_id 
           FROM RESPONSE_RECOMMENDATIONS r
           LEFT JOIN INCIDENTS i ON r.incident_id = i.incident_id
           WHERE r.recommendation_id = ?""",
        (recommendation_id,)
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    rec = rows[0]
    now_iso = datetime.datetime.now().isoformat()
    action_type = rec.get("action_type")
    user_id = rec.get("user_id")

    if req.action.upper() == "APPROVE":
        new_status = "EXECUTED"
        notes = req.notes or f"Approved and safely executed by {req.admin_name}."
        
        # If action is LOCK_ACCOUNT, update USER_ACCOUNTS status
        if action_type == "LOCK_ACCOUNT" and user_id:
            db_connector.execute_update(
                "UPDATE USER_ACCOUNTS SET status = 'LOCKED' WHERE user_id = ?",
                (user_id,)
            )

        db_connector.execute_update(
            """UPDATE RESPONSE_RECOMMENDATIONS
               SET status = ?, approved_by = ?, approved_at = ?, execution_notes = ?
               WHERE recommendation_id = ?""",
            (new_status, req.admin_name, now_iso, notes, recommendation_id)
        )

        return {
            "success": True,
            "status": new_status,
            "message": f"Action '{action_type}' has been AUTHORIZED and EXECUTED in the defense network boundary.",
            "recommendation_id": recommendation_id
        }

    elif req.action.upper() == "REJECT":
        new_status = "REJECTED"
        notes = req.notes or f"Rejected by {req.admin_name}."
        db_connector.execute_update(
            """UPDATE RESPONSE_RECOMMENDATIONS
               SET status = ?, approved_by = ?, approved_at = ?, execution_notes = ?
               WHERE recommendation_id = ?""",
            (new_status, req.admin_name, now_iso, notes, recommendation_id)
        )
        return {
            "success": True,
            "status": new_status,
            "message": f"Action '{action_type}' was REJECTED by administrator.",
            "recommendation_id": recommendation_id
        }
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Must be 'APPROVE' or 'REJECT'.")

