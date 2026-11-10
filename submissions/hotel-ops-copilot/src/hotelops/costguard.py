"""Db2 EXPLAIN cost guard for SQL written by the LLM.

Before an agent-written query runs, Db2's optimizer estimates its cost with
``EXPLAIN PLAN`` (the statement is compiled, never executed). Queries above
``SQL_MAX_COST`` timerons are refused, and the agent is told to filter or
aggregate. This protects a production database from runaway cross joins or
full scans that an LLM can produce.

EXPLAIN runs on a dedicated *manager* connection, so the agent identity stays
strictly read-only: it needs no INSERT privilege on the explain tables.
The explain tables are created once in SYSTOOLS with SYSPROC.SYSINSTALLOBJECTS.
"""
from __future__ import annotations

import itertools
import os
import threading
import time

from .config import load_settings
from .db import Db2, Db2Error

_conn: Db2 | None = None
_lock = threading.Lock()
_queryno = itertools.count(int(time.time()) % 1_000_000)


class QueryTooExpensive(ValueError):
    """Raised when Db2's optimizer estimate exceeds the configured ceiling."""


def max_cost() -> float:
    return float(os.getenv("SQL_MAX_COST", "25000"))


def ensure_explain_tables(db: Db2) -> bool:
    """Create the explain tables in SYSTOOLS if they do not exist yet (idempotent)."""
    try:
        db.scalar("SELECT COUNT(*) FROM SYSTOOLS.EXPLAIN_STATEMENT")
        return False
    except Db2Error:
        db.execute("CALL SYSPROC.SYSINSTALLOBJECTS('EXPLAIN', 'C', CAST(NULL AS VARCHAR(128)), 'SYSTOOLS')")
        return True


def _explain_db() -> Db2:
    global _conn
    if _conn is None:
        s = load_settings().db2
        _conn = Db2(s.conn_str(s.admin_user, s.admin_password), "explain")
        ensure_explain_tables(_conn)
    return _conn


def estimate_cost(sql: str) -> float:
    """Optimizer cost estimate (timerons) for ``sql`` without executing it."""
    with _lock:
        db = _explain_db()
        qno = next(_queryno) % 2_000_000_000
        db.execute(f"EXPLAIN PLAN SET QUERYNO = {qno} FOR {sql}")
        cost = db.scalar("SELECT TOTAL_COST FROM SYSTOOLS.EXPLAIN_STATEMENT WHERE QUERYNO = ? "
                         "AND EXPLAIN_LEVEL = 'P' ORDER BY EXPLAIN_TIME DESC FETCH FIRST 1 ROW ONLY", (qno,))
        # keep the explain tables small: drop this plan (rows cascade from EXPLAIN_INSTANCE)
        db.execute("DELETE FROM SYSTOOLS.EXPLAIN_INSTANCE WHERE (EXPLAIN_TIME, SOURCE_NAME) IN ("
                   "SELECT EXPLAIN_TIME, SOURCE_NAME FROM SYSTOOLS.EXPLAIN_STATEMENT WHERE QUERYNO = ?)", (qno,))
        return float(cost or 0)


def check_cost(sql: str) -> float:
    """Return the estimate, or raise QueryTooExpensive with an actionable message for the agent."""
    cost = estimate_cost(sql)
    limit = max_cost()
    if cost > limit:
        raise QueryTooExpensive(
            f"Db2 optimizer estimates this query at {cost:,.0f} timerons, above the {limit:,.0f} limit for "
            "agent queries. Add WHERE filters (dates, room type), aggregate in SQL, or avoid cross joins.")
    return cost
