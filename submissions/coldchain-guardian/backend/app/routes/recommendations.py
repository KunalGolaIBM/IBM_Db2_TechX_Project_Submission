from fastapi import APIRouter, HTTPException, Query, Body, status
from typing import List, Optional
from datetime import datetime

from app.database.db import execute_query, execute_query_one, execute_dml, execute_insert_get_id
from app.models.recommendation import RecommendationOut, RecommendationCreate, RecommendationApproval
from app.database.audit import log_action

router = APIRouter(prefix="/api/recommendations", tags=["Recommendations"])


def format_dt(value):
    """Convert database datetime values to ISO-8601 strings."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _format_recommendation_rows(rows):
    """Format timestamps while preserving all other recommendation fields."""
    for row in rows:
        row["created_at"] = format_dt(row.get("created_at"))
    return rows


def _generate_rules(severity: str) -> List[tuple]:
    base = [
        ("Inspect refrigeration equipment",
         "Temperature out-of-range detected; equipment may be faulty.", 1),
        ("Contact logistics operator",
         "Shipment could be compromised; operator needs to be notified.", 2),
    ]
    if severity == "CRITICAL":
        base.append(("Divert to qualified cold-storage facility",
                     "Immediate cooling required to prevent product loss.", 1))
        base.append(("Escalate to supervisor",
                     "High-risk incident demands senior oversight.", 1))
    elif severity == "HIGH":
        base.append(("Quarantine shipment pending expert assessment",
                     "Risk is high; isolate until further analysis.", 2))
    else:
        base.append(("Monitor closely",
                     "Deviation modest; continue observation.", 3))
    return base


@router.get("/", response_model=List[RecommendationOut])
def list_recommendations(incident_id: Optional[int] = Query(None, description="Filter by incident")):
    """Return all recommendations, optionally filtered by incident ID."""
    sql = """
        SELECT RECOMMENDATION_ID, INCIDENT_ID, ACTION, JUSTIFICATION,
               PRIORITY, APPROVAL_STATUS, CREATED_AT
        FROM RECOMMENDATIONS
    """
    params = ()
    if incident_id is not None:
        sql += " WHERE INCIDENT_ID = ?"
        params = (incident_id,)
    sql += " ORDER BY PRIORITY, CREATED_AT"

    rows = execute_query(sql, params)
    return _format_recommendation_rows(rows)


@router.post(
    "/generate/{incident_id}",
    response_model=List[RecommendationOut],
    status_code=status.HTTP_201_CREATED,
)
def generate_recommendations(incident_id: int):
    """Generate deterministic recommendations without duplicating existing actions."""
    incident = execute_query_one(
        "SELECT SEVERITY FROM INCIDENTS WHERE INCIDENT_ID = ?",
        (incident_id,),
    )
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    severity = incident["severity"]
    rules = _generate_rules(severity)

    for action, justification, priority in rules:
        insert_sql = """
            INSERT INTO RECOMMENDATIONS (
                INCIDENT_ID, ACTION, JUSTIFICATION, PRIORITY, APPROVAL_STATUS
            )
            SELECT ?, ?, ?, ?, 'PENDING'
            FROM SYSIBM.SYSDUMMY1
            WHERE NOT EXISTS (
                SELECT 1 FROM RECOMMENDATIONS
                WHERE INCIDENT_ID = ? AND ACTION = ?
            )
        """
        rec_id = execute_insert_get_id(
            insert_sql,
            (incident_id, action, justification, priority, incident_id, action),
        )
        if rec_id:
            log_action(
                agent_name="RecommendationAgent",
                action_taken="generate",
                details=f"Generated recommendation '{action}' for incident {incident_id}",
                incident_id=incident_id,
                recommendation_id=rec_id,
            )

    rows = execute_query(
        """
        SELECT RECOMMENDATION_ID, INCIDENT_ID, ACTION, JUSTIFICATION,
               PRIORITY, APPROVAL_STATUS, CREATED_AT
        FROM RECOMMENDATIONS
        WHERE INCIDENT_ID = ?
        ORDER BY PRIORITY, CREATED_AT
        """,
        (incident_id,),
    )
    return _format_recommendation_rows(rows)


@router.patch("/{rec_id}/approval", response_model=RecommendationOut)
def approve_recommendation(rec_id: int, payload: RecommendationApproval = Body(...)):
    """Human approves or rejects a recommendation."""
    rec = execute_query_one(
        "SELECT * FROM RECOMMENDATIONS WHERE RECOMMENDATION_ID = ?",
        (rec_id,),
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    new_status = payload.status.upper()
    if new_status not in {"APPROVED", "REJECTED"}:
        raise HTTPException(status_code=400, detail="Status must be APPROVED or REJECTED")

    execute_dml(
        "UPDATE RECOMMENDATIONS SET APPROVAL_STATUS = ? WHERE RECOMMENDATION_ID = ?",
        (new_status, rec_id),
    )

    log_action(
        agent_name="human",
        action_taken="approve" if new_status == "APPROVED" else "reject",
        details=f"User set recommendation {rec_id} to {new_status}",
        incident_id=rec["incident_id"],
        recommendation_id=rec_id,
    )

    row = execute_query_one(
        """
        SELECT RECOMMENDATION_ID, INCIDENT_ID, ACTION, JUSTIFICATION,
               PRIORITY, APPROVAL_STATUS, CREATED_AT
        FROM RECOMMENDATIONS
        WHERE RECOMMENDATION_ID = ?
        """,
        (rec_id,),
    )
    return _format_recommendation_rows([row])[0] if row else None
