
"""Utility for writing audit log entries.

Each call records a human or agent action in AUDIT_LOGS.

The existing Db2 AUDIT_LOGS schema supports INCIDENT_ID
but does not contain a RECOMMENDATION_ID column.

Recommendation IDs, when supplied, are preserved in DETAILS.
"""

from app.database.db import execute_dml


def log_action(
    agent_name: str,
    action_taken: str,
    details: str,
    incident_id: int | None = None,
    recommendation_id: int | None = None,
) -> None:
    """Insert an audit entry into AUDIT_LOGS.

    Parameters
    ----------
    agent_name:
        Identifier of the actor or agent.

    action_taken:
        Description of the action.

    details:
        Free-form description of the action.

    incident_id:
        Optional incident foreign key.

    recommendation_id:
        Optional recommendation ID. Stored in DETAILS because
        AUDIT_LOGS has no RECOMMENDATION_ID column.
    """

    if recommendation_id is not None:
        details = (
            f"{details} | recommendation_id={recommendation_id}"
        )

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
        (
            incident_id,
            agent_name,
            action_taken,
            details,
        ),
    )
