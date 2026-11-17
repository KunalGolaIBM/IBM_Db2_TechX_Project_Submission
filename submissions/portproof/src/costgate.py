"""What a repair costs, in the optimizer's own estimate.

A meaning repair is accepted because the rows now match. Nothing in that test
asks what the rewrite does to the plan, and the rewrites that fix collation
wrap a column in a function, which is the classic way to stop an index being
used. A repair that is correct and ten times slower is a regression the
differential proof cannot see.

So Db2 is asked. ``EXPLAIN PLAN`` compiles the statement without running it and
writes the optimizer's estimate, in timerons, to the Explain tables. The
statement before the repair and the statement after it are explained against
the same tables, and the two estimates are reported side by side.

Two limits, stated plainly. The estimate is made over PortProof's small proof
datasets with no indexes of the application's own, so the ratio says the plan
got more expensive and not by how much it will in production. And it needs the
Explain tables, which the schema owner cannot create for itself
(``scripts/create_explain_tables.sh``); without them every estimate is None and
the check is silently absent, never wrong.
"""
from __future__ import annotations

import random
import re

from . import db

#: A repair at or above this ratio is called out in the report.
SLOWER_RATIO = 2.0


def estimate(conn, sql: str) -> float | None:
    """Db2's estimated total cost of ``sql`` in timerons, or None if unavailable.

    The statement is the subject of the measurement, so it is inlined into the
    EXPLAIN text, exactly as it is handed to PREPARE elsewhere. It is compiled
    and never executed.
    """
    text = (sql or "").strip().rstrip(";")
    if not text:
        return None
    queryno = random.randint(100_000, 2_000_000_000)
    try:
        # The Explain tables live in the schema named after the session user,
        # wherever CURRENT SCHEMA happens to point for the proof.
        owner = str(db.fetch_one(conn, "VALUES SESSION_USER")[0]).strip()
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,29}", owner):
            return None
    except db.Db2Error:
        return None
    try:
        db.execute(conn, f"EXPLAIN PLAN SET QUERYNO = {queryno} FOR {text}")
        row = db.fetch_one(
            conn,
            f"SELECT TOTAL_COST FROM {owner}.EXPLAIN_STATEMENT "
            "WHERE QUERYNO = ? AND EXPLAIN_LEVEL = 'P' "
            "ORDER BY EXPLAIN_TIME DESC FETCH FIRST 1 ROW ONLY",
            (queryno,),
        )
    except db.Db2Error:
        return None
    finally:
        try:
            db.execute(
                conn,
                f"DELETE FROM {owner}.EXPLAIN_INSTANCE WHERE (EXPLAIN_REQUESTER, EXPLAIN_TIME) IN "
                f"(SELECT EXPLAIN_REQUESTER, EXPLAIN_TIME FROM {owner}.EXPLAIN_STATEMENT "
                "WHERE QUERYNO = ?)",
                (queryno,),
            )
        except db.Db2Error:
            pass
    return float(row[0]) if row and row[0] is not None else None


def ratio(before: float | None, after: float | None) -> float | None:
    if not before or after is None:
        return None
    return after / before
