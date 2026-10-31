"""Rebuild the opening-statistics projection from authoritative saved games.

Run from the repository root:
    python -m backend.scripts.rebuild_opening_stats
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import ibm_db

from . import close_quietly, connect, db2_schema, failure_label


def _projection_count(connection: Any, schema: str) -> int:
    statement = ibm_db.exec_immediate(
        connection,
        f"SELECT COUNT(*) FROM {schema}.CHESS_OPENING_STATISTICS",
    )
    row = ibm_db.fetch_tuple(statement)
    return int(row[0]) if row else 0


def rebuild() -> None:
    schema = db2_schema()
    connection = None
    try:
        connection = connect()
        ibm_db.exec_immediate(connection, f"DELETE FROM {schema}.CHESS_OPENING_STATISTICS")
        statement = ibm_db.prepare(
            connection,
            f"""
            INSERT INTO {schema}.CHESS_OPENING_STATISTICS (
                OPENING_KEY, OPENING_CODE, OPENING_NAME, TOTAL_GAMES,
                WINS, LOSSES, DRAWS, UNKNOWN_GAMES, UPDATED_AT
            )
            SELECT
                COALESCE(OPENING_CODE, '') CONCAT '|' CONCAT OPENING_NAME,
                OPENING_CODE,
                OPENING_NAME,
                COUNT(*),
                SUM(CASE WHEN PLAYER_OUTCOME = 'win' THEN 1 ELSE 0 END),
                SUM(CASE WHEN PLAYER_OUTCOME = 'loss' THEN 1 ELSE 0 END),
                SUM(CASE WHEN PLAYER_OUTCOME = 'draw' THEN 1 ELSE 0 END),
                SUM(CASE WHEN PLAYER_OUTCOME = 'unknown' THEN 1 ELSE 0 END),
                ?
            FROM {schema}.CHESS_GAMES
            GROUP BY OPENING_CODE, OPENING_NAME
            """,
        )
        ibm_db.execute(statement, (datetime.now(timezone.utc).replace(tzinfo=None),))
        count = _projection_count(connection, schema)
        ibm_db.commit(connection)
        print(f"Rebuilt {count} opening-statistics rows in Db2 schema {schema}.")
    except Exception:
        if connection is not None:
            ibm_db.rollback(connection)
        raise SystemExit(failure_label("Opening-statistics rebuild", connection)) from None
    finally:
        close_quietly(connection)


if __name__ == "__main__":
    rebuild()
