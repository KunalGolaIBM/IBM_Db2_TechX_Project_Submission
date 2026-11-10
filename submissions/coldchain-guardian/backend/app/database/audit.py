"""Utility for writing audit log entries."""

from app.database.db import execute_dml


def log_action(
    agent_name: str,
    action_taken: str,
    details: str,
    incident_id: int | None = None,
    recommendation_id: int | None = None,
) -> None:
    """Insert an audit entry into AUDIT_LOGS.

    AUDIT_LOGS has no RECOMMENDATION_ID column.
    Recommendation IDs are preserved in the DETAILS field.
    """

    if recommendation_id is not None:
        details = f"{details} | recommendation_id={recommendation_id}"

    sql = """
        INSERT INTO AUDIT_LOGS (
            INCIDENT_ID,
            AGENT_NAME,
            ACTION_TAKEN,
            DETAILS,
            TIMESTAMP
        )
        VALUES (?, ?, ?, ?, CURRENT TIMESTAMP)
    """

    execute_dml(
        sql,
        (incident_id, agent_name, action_taken, details),
    )
