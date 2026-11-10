"""Db2 workload management for the analyst users: the limits Db2 enforces on every query they run.

    python -m asof.wlm           # show the workload, its thresholds and where each analyst connection lands
    python -m asof.wlm --drop    # remove the workload and thresholds (database-level; setup creates them again)

The objects are in sql/07_wlm.sql (setup creates them); this module holds the same limits, turns Db2's threshold
error into the refusal Ask the ledger shows, and drops the objects on request. See docs/wlm.md.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass

import ibm_db_dbi

from . import db

WORKLOAD = "WL_ASOF_ANALYST"
THRESHOLD_STATE = "5U026"  # SQL4712N: the activity was stopped because a threshold was exceeded


@dataclass(frozen=True)
class Limit:
    threshold: str
    predicate: str  # as SYSCAT.THRESHOLDS.THRESHOLDPREDICATE stores it
    value: int
    reason_code: int  # SQL4712N's reason code when it trips


# The same numbers as 07_wlm.sql (tests/test_wlm.py keeps them in step).
COST = Limit("TH_ASOF_ANALYST_COST", "ESTSQLCOST", 1_000_000, 7)  # timerons, the optimizer's estimate
ROWS = Limit("TH_ASOF_ANALYST_ROWS", "ROWSRET", 10_000, 8)  # rows returned to the client
TIME = Limit("TH_ASOF_ANALYST_TIME", "TOTALTIME", 10, 9)  # seconds, queueing and running
LIMITS = (COST, ROWS, TIME)

_STOPPED = re.compile(r'SQL4712N.*?threshold "([A-Z0-9_]+)".*?[Rr]eason code: "?(\d+)')


def stopped(exc: db.DatabaseError) -> str | None:
    """The plain refusal for a query Db2's workload management stopped (SQL4712N), or None for any other error."""
    if exc.sqlstate != THRESHOLD_STATE and "SQL4712N" not in str(exc):
        return None
    m = _STOPPED.search(str(exc))
    name, code = (m.group(1), int(m.group(2))) if m else ("unknown", 0)
    if code == COST.reason_code:
        return (f"Db2 refused to run this query: the optimizer estimated it at more than {COST.value:,} timerons, the "
                f"limit for analyst queries (threshold {name}). Ask about fewer views at once, or a narrower period.")
    if code == ROWS.reason_code:
        return (f"Db2 stopped this query when it passed {ROWS.value:,} rows returned, the limit for analyst queries "
                f"(threshold {name}). Ask for counts or totals instead of every row.")
    if code == TIME.reason_code:
        return (f"Db2 stopped this query after more than {TIME.value} seconds, the limit for analyst queries "
                f"(threshold {name}).")
    return f"Db2's workload management stopped this query (threshold {name}, reason code {code})."


SQL_THRESHOLDS = ("SELECT T.THRESHOLDNAME, T.THRESHOLDPREDICATE, T.MAXVALUE, T.EXECUTION, T.ENABLED "
                  "FROM SYSCAT.THRESHOLDS T JOIN SYSCAT.WORKLOADS W ON T.DOMAIN = 'WD' AND T.DOMAINID = W.WORKLOADID "
                  "WHERE W.WORKLOADNAME = ? ORDER BY T.THRESHOLDNAME")
SQL_WORKLOAD = "SELECT ENABLED FROM SYSCAT.WORKLOADS WHERE WORKLOADNAME = ?"
# Where each current connection landed (the owner's view: it needs monitoring authority).
SQL_CONNECTIONS = ("SELECT SESSION_AUTH_ID, WORKLOAD_NAME, COUNT(*) "
                   "FROM TABLE(WLM_GET_SERVICE_CLASS_WORKLOAD_OCCURRENCES(NULL, NULL, -2)) "
                   "GROUP BY SESSION_AUTH_ID, WORKLOAD_NAME ORDER BY 1")


def installed(conn: ibm_db_dbi.Connection) -> dict[str, tuple[str, int, str, str]]:
    """Threshold name -> (predicate, value, execution, enabled), as Db2 holds them."""
    return {r[0].strip(): (r[1].strip(), int(r[2]), r[3].strip(), r[4].strip())
            for r in db.query(conn, SQL_THRESHOLDS, (WORKLOAD,))}


def drop(conn: ibm_db_dbi.Connection) -> list[str]:
    """Remove the thresholds, then the workload (Db2 drops a workload only once it is disabled and has no threshold).
    Returns what was dropped. The role stays: the grants use it."""
    dropped = []
    for name in installed(conn):
        db.execute(conn, f"DROP THRESHOLD {db.ident(name)}")
        conn.commit()
        dropped.append(name)
    if db.query(conn, SQL_WORKLOAD, (WORKLOAD,)):
        db.execute(conn, f"ALTER WORKLOAD {db.ident(WORKLOAD)} DISABLE")
        conn.commit()
        db.execute(conn, f"DROP WORKLOAD {db.ident(WORKLOAD)}")
        conn.commit()
        dropped.append(WORKLOAD)
    return dropped


def main(argv: list[str] | None = None) -> int:
    from .config import get_settings

    parser = argparse.ArgumentParser(prog="python -m asof.wlm", description=__doc__.split("\n\n")[0])
    parser.add_argument("--drop", action="store_true", help="remove the analyst workload and its thresholds")
    args = parser.parse_args(argv)
    with db.connection(get_settings(), "admin") as conn:
        if args.drop:
            print("dropped: " + (", ".join(drop(conn)) or "nothing (not installed)"))
            return 0
        workload = db.query(conn, SQL_WORKLOAD, (WORKLOAD,))
        if not workload:
            print(f"{WORKLOAD} is not installed: run python -m asof.setup")
            return 1
        print(f"{WORKLOAD}: enabled={workload[0][0].strip()}")
        for name, (predicate, value, execution, enabled) in installed(conn).items():
            print(f"  {name:<22} {predicate:<13} > {value:>9,}  execution={execution} enabled={enabled}")
        for user, workload_name, n in db.query(conn, SQL_CONNECTIONS):
            print(f"  connected: {user.strip():<10} -> {workload_name.strip()} ({n})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
