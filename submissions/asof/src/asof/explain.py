"""Show how Db2 runs AsOf's hot queries.

    python -m asof.explain                  # the seeded ASOF schema
    python -m asof.explain --scale 100000   # also the retrieval forms at 100,000 synthetic clause versions

For each statement the app runs most, this asks Db2 for its access plan and writes the plan
to docs/explain/<name>.txt (IBM's db2exfmt format) plus a summary to docs/explain/README.md.
The as-of retrieval is explained three ways: as the app runs it (FETCH EXACT), and with
FETCH APPROX with and without FOR BUSINESS_TIME AS OF, to show when Db2 reads the vector index.
With --scale, those three and a plain FETCH FIRST are explained again against asof.vectorbench's synthetic corpus
(schema ASOF_VBENCH: the shipped DDL, the native vector index, RUNSTATS), built if missing.

It runs the exact statement constants from the code, with realistic bound values, under
`SET CURRENT EXPLAIN MODE = EXPLAIN`: Db2 explains each statement instead of running it, so
no SQL text is assembled here either. It needs the owner account (DB2_USER) and Db2's explain
tables; if they are missing it creates them from IBM's EXPLAIN.DDL inside the Db2 container
(SYSPROC.SYSINSTALLOBJECTS is a fenced routine, which crashes under Rosetta).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import date, datetime
from typing import Any

import ibm_db_dbi

from . import db, ledger, policy, retriever, vectorbench
from . import schema as schema_mod
from .config import PROJECT_ROOT, ConfigError, Settings, get_settings
from .setup import find_db2_container

OUT_DIR = PROJECT_ROOT / "docs" / "explain"
UNIT = "[" + ",".join(["0.0510310363"] * 384) + "]"  # a unit-length 384-dim vector

# name, what the app uses it for, statement constant, bound values
STATEMENTS = [
    ("as_of_retrieval", "Clauses in force on the customer's date, ranked by cosine distance (every claim)",
     retriever.SQL_AS_OF, (UNIT, date(2026, 3, 10), "AURELIA-CSP", 4)),
    ("as_of_retrieval_approx", "The same with FETCH APPROX FIRST 10 ROWS (not used by the app: see vector_benchmark.md)",
     vectorbench.SQL_CLAUSE_APPROX_ON, (UNIT, date(2026, 3, 10), "AURELIA-CSP")),
    ("nearest_any_date_approx", "FETCH APPROX FIRST 10 ROWS without FOR BUSINESS_TIME AS OF (not used by the app)",
     vectorbench.SQL_CLAUSE_APPROX_ALL, (UNIT, "AURELIA-CSP")),
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


# The retrieval forms again at scale: name, purpose, statement, bound values (against vectorbench.CLAUSE_SCHEMA).
SCALED = [
    ("as_of_retrieval", "As the app runs it (FETCH EXACT), at scale",
     vectorbench.SQL_CLAUSE_EXACT_ON, (UNIT, date(2026, 3, 10), vectorbench.CLAUSE_DOC, 10)),
    ("as_of_retrieval_approx", "FETCH APPROX FIRST 10 ROWS under FOR BUSINESS_TIME AS OF, at scale",
     vectorbench.SQL_CLAUSE_APPROX_ON, (UNIT, date(2026, 3, 10), vectorbench.CLAUSE_DOC)),
    ("nearest_any_date_approx", "FETCH APPROX FIRST 10 ROWS without FOR BUSINESS_TIME AS OF, at scale",
     vectorbench.SQL_CLAUSE_APPROX_ALL, (UNIT, vectorbench.CLAUSE_DOC)),
    ("nearest_any_date_default", "FETCH FIRST 10 ROWS, neither EXACT nor APPROX, without the period, at scale",
     vectorbench.SQL_CLAUSE_DEFAULT_ALL, (UNIT, vectorbench.CLAUSE_DOC)),
]


def scaled_name(name: str, rows: int) -> str:
    return f"{name}_{rows // 1000}k" if rows >= 1000 else f"{name}_{rows}"


def _latest_plan(conn: ibm_db_dbi.Connection) -> tuple[list[tuple[str, float]], list[str]]:
    """Operators (type, cumulative cost) and objects of the most recent explained statement."""
    ops = db.query(conn, "SELECT OPERATOR_TYPE, TOTAL_COST FROM EXPLAIN_OPERATOR WHERE EXPLAIN_TIME = "
                         "(SELECT MAX(EXPLAIN_TIME) FROM EXPLAIN_OPERATOR) ORDER BY OPERATOR_ID")
    # A vector index scan also reads the index's hidden tables in SYSIBM; the plan names them, the summary does not.
    objs = db.query(conn, "SELECT OBJECT_NAME, OBJECT_TYPE FROM EXPLAIN_OBJECT WHERE EXPLAIN_TIME = "
                          "(SELECT MAX(EXPLAIN_TIME) FROM EXPLAIN_OBJECT) AND OBJECT_TYPE IN ('IX', 'TA', 'DP', 'VI') "
                          "AND OBJECT_SCHEMA <> 'SYSIBM' ORDER BY OBJECT_TYPE DESC, OBJECT_NAME")
    kinds = {"IX": "index", "TA": "table", "DP": "partitioned table", "VI": "vector index"}
    return ([(o[0].strip(), float(o[1])) for o in ops], [f"{n.strip()} ({kinds[t.strip()]})" for n, t in objs])


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
    # From the instance home: db2exfmt binds its package and writes db2exfmt.msg in the working directory, and in
    # IBM's stock image `docker exec` starts in /, where it cannot ("Error during bind", no plan at all).
    script = (f"cd ~ && db2exfmt -d {db.ident(settings.db2_database)} -1 -o /tmp/asof_plan.txt > /dev/null 2>&1; "
              "cat /tmp/asof_plan.txt")
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


def explain_one(conn: ibm_db_dbi.Connection, settings: Settings, container: str | None, schema: str, name: str,
                purpose: str, sql: str, params: tuple[Any, ...]) -> tuple[str, str, str, str, float]:
    """Explain one statement in `schema`, write docs/explain/<name>.txt, and return its README row."""
    db.use_schema(conn, schema)
    _explain(conn, sql, params)
    db.use_schema(conn, db.ident(settings.db2_admin_user))  # explain tables live in the owner's schema
    ops, objects = _latest_plan(conn)
    db.use_schema(conn, schema)
    text = _exfmt(settings, container)
    body = [f"-- {purpose}", f"-- Schema: {schema}",
            "-- Statement (as the app runs it, values bound as parameters):", f"-- {sql}", ""]
    body.append(_plan_graph(text) if text else "Operators: " + " > ".join(o for o, _ in ops) + "\n")
    (OUT_DIR / f"{name}.txt").write_text("\n".join(body), encoding="utf-8")
    row = (name, purpose, " > ".join(o for o, _ in ops), ", ".join(objects), ops[0][1] if ops else 0.0)
    print(f"{name:30} cost {row[4]:10.2f}  {row[2]}")
    return row


def run(schema: str = db.SCHEMA, scale: int = 0, keep: bool = False) -> int:
    try:
        settings = get_settings()
        conn = db.connect(settings, "admin")
    except (ConfigError, db.DatabaseError) as exc:
        print(f"cannot connect: {exc}")
        return 2
    container = find_db2_container(settings.db2_container) if shutil.which("docker") else None
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    built = False
    try:
        ensure_explain_tables(conn, settings, container)
        db.use_schema(conn, schema)
        versions = int(db.query(conn, "SELECT COUNT(*) FROM POLICY_CLAUSE")[0][0])
        for name, purpose, sql, params in STATEMENTS:
            rows.append(explain_one(conn, settings, container, schema, name, purpose, sql, params))
        if scale:
            if not vectorbench.clause_corpus_ready(conn, scale):
                print(f"building {vectorbench.CLAUSE_SCHEMA} with {scale:,} synthetic clause versions", flush=True)
                vectorbench.build_clause_corpus(conn, settings, container, scale)
                built = True
            for name, purpose, sql, params in SCALED:
                rows.append(explain_one(conn, settings, container, vectorbench.CLAUSE_SCHEMA, scaled_name(name, scale),
                                        f"{purpose} ({scale:,} synthetic clause versions)", sql, params))
    finally:
        if built and not keep:
            schema_mod.drop(conn, vectorbench.CLAUSE_SCHEMA)
        conn.close()
    lines = ["# Access plans for AsOf's hot queries", "",
             # Two lines of one Markdown paragraph: the dynamic one stays apart from the SQL quoted in the next.
             f"Generated by `python -m asof.explain` against the seeded `{schema}` schema ({versions} clause versions).",
             "Each plan is for the exact statement in the code, explained with bound values under "
             "`SET CURRENT EXPLAIN MODE = EXPLAIN`. Costs are Db2's estimates in timerons."]
    if scale:
        lines.append(f"Plans whose name ends in `{scaled_name('', scale)}` were explained against "
                     f"`{vectorbench.CLAUSE_SCHEMA}`, {scale:,} synthetic clause versions in the shipped table, history "
                     f"and indexes, built by `asof.vectorbench` (`python -m asof.explain --scale {scale}`).")
    lines += ["", "| Query | Used for | Operators (top down) | Tables and indexes | Est. cost |", "|---|---|---|---|---|"]
    lines += [f"| [{n}]({n}.txt) | {p} | {o} | {obj} | {c:.2f} |" for n, p, o, obj, c in rows]
    (OUT_DIR / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} plans to {OUT_DIR.relative_to(PROJECT_ROOT)}/")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m asof.explain")
    p.add_argument("--scale", type=int, default=0,
                   help="also explain the retrieval forms at this many synthetic clause versions (0: off)")
    p.add_argument("--keep", action="store_true", help="keep a synthetic corpus this run built")
    args = p.parse_args(argv)
    if not (args.scale == 0 or 100 <= args.scale <= 1_000_000):
        p.error("--scale must be 0 or between 100 and 1,000,000")
    return run(scale=args.scale, keep=args.keep)


if __name__ == "__main__":
    sys.exit(main())
