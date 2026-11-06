"""
IBM Db2-backed Checkpointer for LangGraph Multi-Agent Workflows.
Persists intermediate agent state snapshots, tool outputs, and reasoning steps
directly into Db2 tables for ACID reliability, pause-and-resume, and compliance audit.
"""

import json
from typing import Dict, Any, Optional, List
from src.db.connection import get_db_manager


class Db2AgentCheckpointer:
    """Saves and restores LangGraph execution state snapshots to/from IBM Db2."""

    def __init__(self):
        self.db = get_db_manager()

    def save_checkpoint(self, thread_id: str, step_num: int, agent_name: str, state: Dict[str, Any]):
        """Persists a state checkpoint to Db2."""
        state_json = json.dumps(state, default=str)
        sql = """
        INSERT INTO AGENT_CHECKPOINTS (THREAD_ID, STEP_NUM, AGENT_NAME, STATE_JSON)
        VALUES (?, ?, ?, ?)
        """
        self.db.execute_update(sql, (thread_id, step_num, agent_name, state_json))

    def load_latest_checkpoint(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves the most recent checkpoint for a given thread_id."""
        sql = """
        SELECT THREAD_ID, STEP_NUM, AGENT_NAME, STATE_JSON, CREATED_AT
        FROM AGENT_CHECKPOINTS
        WHERE THREAD_ID = ?
        ORDER BY STEP_NUM DESC
        FETCH FIRST 1 ROWS ONLY
        """
        rows = self.db.execute_query(sql, (thread_id,))
        if rows:
            data = rows[0]
            state = json.loads(data["STATE_JSON"])
            return {
                "thread_id": data["THREAD_ID"],
                "step_num": data["STEP_NUM"],
                "agent_name": data["AGENT_NAME"],
                "state": state,
                "created_at": data["CREATED_AT"],
            }
        return None

    def get_thread_history(self, thread_id: str) -> List[Dict[str, Any]]:
        """Retrieves full execution trace of checkpoints for a thread."""
        sql = """
        SELECT STEP_NUM, AGENT_NAME, STATE_JSON, CREATED_AT
        FROM AGENT_CHECKPOINTS
        WHERE THREAD_ID = ?
        ORDER BY STEP_NUM ASC
        """
        rows = self.db.execute_query(sql, (thread_id,))
        history = []
        for r in rows:
            history.append({
                "step_num": r["STEP_NUM"],
                "agent_name": r["AGENT_NAME"],
                "state": json.loads(r["STATE_JSON"]),
                "created_at": r["CREATED_AT"],
            })
        return history
