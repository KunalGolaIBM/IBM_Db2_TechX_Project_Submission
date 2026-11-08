"""Show how Db2 runs AsOf's hot queries.

    python -m asof.explain

For each statement the app runs most, this asks Db2 for its access plan and writes the plan
to docs/explain/<name>.txt (IBM's db2exfmt format) plus a summary to docs/explain/README.md.

It runs the exact statement constants from the code, with realistic bound values, under
`SET CURRENT EXPLAIN MODE = EXPLAIN`: Db2 explains each statement instead of running it, so
no SQL text is assembled here either. It needs the owner account (DB2_USER) and Db2's explain
tables; if they are missing it creates them from IBM's EXPLAIN.DDL inside the Db2 container
(SYSPROC.SYSINSTALLOBJECTS is a fenced routine, which crashes under Rosetta).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import date, datetime
from typing import Any

import ibm_db_dbi

from . import db, ledger, policy, retriever
from .config import PROJECT_ROOT, ConfigError, Settings, get_settings
from .setup import find_db2_container

OUT_DIR = PROJECT_ROOT / "docs" / "explain"
UNIT = "[" + ",".join(["0.0510310363"] * 384) + "]"  # a unit-length 384-dim vector

# name, what the app uses it for, statement constant, bound values
STATEMENTS = [
    ("as_of_retrieval", "Clauses in force on the customer's date, ranked by cosine distance (every claim)",
     retriever.SQL_AS_OF, (UNIT, date(2026, 3, 10), "AURELIA-CSP", 4)),
    ("replay_retrieval", "The same, as the database held it at a past moment (replay)",
     retriever.SQL_REPLAY, (UNIT, datetime(2026, 11, 6, 12, 0, 0), date(2026, 3, 10), "AURELIA-CSP", 4)),
    ("ledger_page", "One page of the audit ledger, newest first",
     ledger.SQL_LIST, (0, 50)),
    ("ledger_page_by_decision", "One page of one decision type (for example every ESCALATED check), newest first",
     ledger.SQL_LIST_BY_DECISION, ("ESCALATED", 0, 50)),
    ("ledger_citations", "The claim citations of one decision",
     ledger.SQL_CITATIONS, (1,)),
    ("clause_history", "Every row Db2 has held for one clause (FOR SYSTEM_TIME FROM ... TO ...)",
     policy.SQL_HISTORY, ("0001-01-01-00.00.00", "9999-12-30-00.00.00", "BRV-002")),
]


def _latest_plan(conn: ibm_db_dbi.Connection) -> tuple[list[tuple[str, float]], list[str]]:
    """Operators (type, cumulative cost) and objects of the most recent explained statement."""
    ops = db.query(conn, "SELECT OPERATOR_TYPE, TOTAL_COST FROM EXPLAIN_OPERATOR WHERE EXPLAIN_TIME = "
                         "(SELECT MAX(EXPLAIN_TIME) FROM EXPLAIN_OPERATOR) ORDER BY OPERATOR_ID")
    objs = db.query(conn, "SELECT OBJECT_NAME, OBJECT_TYPE FROM EXPLAIN_OBJECT WHERE EXPLAIN_TIME = "
                          "(SELECT MAX(EXPLAIN_TIME) FROM EXPLAIN_OBJECT) AND OBJECT_TYPE IN ('IX', 'TA') "
                          "ORDER BY OBJECT_TYPE DESC, OBJECT_NAME")
    return ([(o[0].strip(), float(o[1])) for o in ops],
            [f"{n.strip()} ({'index' if t.strip() == 'IX' else 'table'})" for n, t in objs])


def _explain(conn: ibm_db_dbi.Connection, sql: str, params: tuple[Any, ...]) -> None:
    db.execute(conn, "SET CURRENT EXPLAIN MODE = EXPLAIN")
    try:
        cur = conn.cursor()
        try:
            cur.execute(sql, params)  # explained, not run: there is no result set to fetch
        finally:
            cur.close()
    finally:
        db.execute(conn, "SET CURRENT EXPLAIN MODE = NO")
        conn.commit()


def _exfmt(settings: Settings, container: str | None) -> str | None:
    """The most recent plan as db2exfmt text, or None without access to the container."""
    if container is None:
        return None
    script = f"db2exfmt -d {db.ident(settings.db2_database)} -1 -o /tmp/asof_plan.txt > /dev/null 2>&1; cat /tmp/asof_plan.txt"
    done = subprocess.run(["docker", "exec", "-u", settings.db2_admin_user, container, "bash", "-lc", script],
                          capture_output=True, text=True, timeout=120)
    return done.stdout if done.returncode == 0 and "Access Plan" in done.stdout else None


def _plan_graph(text: str) -> str:
    """The plan graph plus Plan Details (each operator's predicates, start and stop keys, and costs)."""
    start = text.index("Access Plan:")
    stops = [i for i in (text.find("Extended Diagnostic Information", start), text.find("Plan Details", start)) if i != -1]
    graph = text[start:min(stops) if stops else len(text)].rstrip()
    details_at = text.find("Plan Details:", start)
    if details_at == -1:
        return graph + "\n"
    end = text.find("Objects Used in Access Plan", details_at)
    return graph + "\n\n" + text[details_at:end if end != -1 else len(text)].rstrip() + "\n"


def ensure_explain_tables(conn: ibm_db_dbi.Connection, settings: Settings, container: str | None) -> None:
    have = db.query(conn, "SELECT COUNT(*) FROM SYSCAT.TABLES WHERE TABSCHEMA = CURRENT USER "
                          "AND TABNAME = 'EXPLAIN_INSTANCE'")[0][0]
    if have:
        return
    if container is None:
        raise SystemExit("Db2's explain tables are missing and no Db2 container is reachable. Create them as the "
                         "owner with: db2 -tf ~/sqllib/misc/EXPLAIN.DDL")
    script = f"db2 connect to {db.ident(settings.db2_database)} > /dev/null && db2 -tf ~/sqllib/misc/EXPLAIN.DDL > /dev/null"
    subprocess.run(["docker", "exec", "-u", settings.db2_admin_user, container, "bash", "-lc", script],
                   check=True, timeout=300)


def run(schema: str = db.SCHEMA) -> int:
    try:
        settings = get_settings()
        conn = db.connect(settings, "admin")
    except (ConfigError, db.DatabaseError) as exc:
        print(f"cannot connect: {exc}")
        return 2
    container = find_db2_container(settings.db2_container) if shutil.which("docker") else None
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    try:
        ensure_explain_tables(conn, settings, container)
        db.use_schema(conn, schema)
        versions = int(db.query(conn, "SELECT COUNT(*) FROM POLICY_CLAUSE")[0][0])
        for name, purpose, sql, params in STATEMENTS:
            _explain(conn, sql, params)
            db.use_schema(conn, db.ident(settings.db2_admin_user))  # explain tables live in the owner's schema
            ops, objects = _latest_plan(conn)
            db.use_schema(conn, schema)
            text = _exfmt(settings, container)
            body = [f"-- {purpose}", "-- Statement (as the app runs it, values bound as parameters):", f"-- {sql}", ""]
            body.append(_plan_graph(text) if text else "Operators: " + " > ".join(o for o, _ in ops) + "\n")
            (OUT_DIR / f"{name}.txt").write_text("\n".join(body), encoding="utf-8")
            rows.append((name, purpose, " > ".join(o for o, _ in ops), ", ".join(objects), ops[0][1] if ops else 0.0))
            print(f"{name:18} cost {rows[-1][4]:8.2f}  {rows[-1][2]}")
    finally:
        conn.close()
    lines = ["# Access plans for AsOf's hot queries", "",
             # Two lines of one Markdown paragraph: the dynamic one stays apart from the SQL quoted in the next.
             f"Generated by `python -m asof.explain` against the seeded `{schema}` schema ({versions} clause versions).",
             "Each plan is for the exact statement in the code, explained with bound values under "
             "`SET CURRENT EXPLAIN MODE = EXPLAIN`. Costs are Db2's estimates in timerons.", "",
             "| Query | Used for | Operators (top down) | Tables and indexes | Est. cost |", "|---|---|---|---|---|"]
    lines += [f"| [{n}]({n}.txt) | {p} | {o} | {obj} | {c:.2f} |" for n, p, o, obj, c in rows]
    (OUT_DIR / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} plans to {OUT_DIR.relative_to(PROJECT_ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(run())
