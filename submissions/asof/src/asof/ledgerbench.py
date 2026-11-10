"""Ledger benchmark: monthly range partitioning and materialized query tables, before and after, at volume.

    python -m asof.ledgerbench [--rows 1000000] [--keep]

Installs the full AsOf schema twice, in scratch schemas, and fills both with the same synthetic year of
decisions (by default 1,000,000, about 2,700 a day, each with two claim citations):

  LBFLAT  the design before: ANSWER_LEDGER unpartitioned, the analytics views as GROUP BY over the base tables
  LBPART  the shipped design: ANSWER_LEDGER range-partitioned by month, the views read REFRESH IMMEDIATE MQTs

Then, in each, it collects statistics, asks Db2 for the access plan of each query (EXPLAIN, estimated cost
in timerons, plans written with db2exfmt), times it (median of 5 runs after one warm-up), and times 100
appends through APPEND_LEDGER, which in LBPART also maintain the MQTs. The queries are the app's own
statement constants where it has one. Results go to docs/ledger_benchmark.md and docs/ledgerbench/.
The synthetic rows are not a hash chain; nothing here reads them as one.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
import time
import uuid
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import ibm_db_dbi

from . import db, explain, ledger, policy, schema, seed
from .config import PROJECT_ROOT, Settings, get_settings
from .setup import find_db2_container

FLAT, PART = "LBFLAT", "LBPART"
BATCH = 5_000  # rows per committed batch: TESTDB's circular log is 100 MB, and LBPART also logs MQT upkeep
OUT_DIR = PROJECT_ROOT / "docs" / "ledgerbench"
REPORT = PROJECT_ROOT / "docs" / "ledger_benchmark.md"
YEAR_SECONDS = 365 * 24 * 3600

# The two analytics views as they were before the MQTs (04_views.sql up to 7 Nov 2026).
OLD_VIEWS = {
    "V_DECISION_STATS": """CREATE OR REPLACE VIEW ASOF.V_DECISION_STATS AS
  SELECT CHANNEL, DECISION, REASON_CODE, COUNT(*) AS DECISIONS,
         INTEGER(AVG(LATENCY_MS)) AS AVG_LATENCY_MS, MIN(CREATED_AT) AS FIRST_AT, MAX(CREATED_AT) AS LAST_AT
  FROM ASOF.ANSWER_LEDGER
  GROUP BY CHANNEL, DECISION, REASON_CODE""",
    "V_CLAIM_OUTCOMES_BY_AREA": """CREATE OR REPLACE VIEW ASOF.V_CLAIM_OUTCOMES_BY_AREA AS
  SELECT AREA,
         SUM(CASE WHEN VERDICT = 'SUPPORTED' THEN 1 ELSE 0 END)    AS SUPPORTED,
         SUM(CASE WHEN VERDICT = 'CONTRADICTED' THEN 1 ELSE 0 END) AS CONTRADICTED,
         SUM(CASE WHEN VERDICT = 'NOT_COVERED' THEN 1 ELSE 0 END)  AS NOT_COVERED,
         COUNT(*) AS CLAIMS
  FROM ASOF.CLAIM_CITATION
  WHERE PASS_NO = 1
  GROUP BY AREA""",
}
NEW_ONLY = {"IX_LEDGER_GROUP_CREATED", "P_MQT_DECISION_STATS_ALL_ROWS"}
PARTITION_CLAUSE = re.compile(r"\n\s*PARTITION BY RANGE \(CREATED_AT\) \(.*?MAXVALUE\)", re.S)

# One batch of synthetic decisions: ledger IDs from ? up to ?, one every ? microseconds from 1 Jan 2026.
SQL_LOAD_LEDGER = """INSERT INTO ANSWER_LEDGER (LEDGER_ID, REQUEST_ID, CREATED_AT, CHANNEL, DOC_ID, AS_OF_DATE,
  QUESTION_REDACTED, DRAFT_REDACTED, FINAL_ANSWER, DECISION, REASON_CODE, MODEL_INFO, PROMPT_VERSION, LATENCY_MS,
  VERDICTS_JSON, PREV_HASH, ROW_HASH)
WITH D(N) AS (VALUES 0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
     G(I) AS (SELECT CAST(? AS BIGINT) + A.N * 1000 + B.N * 100 + C.N * 10 + E.N FROM D A, D B, D C, D E),
     R(I, T, DEC) AS (SELECT I, TIMESTAMP('2026-01-01-00.00.00') + (I * CAST(? AS BIGINT)) MICROSECONDS,
                             CASE WHEN MOD(I * 13, 20) < 11 THEN 'PASS' WHEN MOD(I * 13, 20) < 16 THEN 'CORRECTED'
                                  ELSE 'ESCALATED' END
                      FROM G WHERE I <= ?)
SELECT I, '00000000-0000-4000-8000-' || DIGITS(DECIMAL(I, 12)), T,
       CASE WHEN MOD(I * 7, 20) < 12 THEN 'chat' WHEN MOD(I * 7, 20) < 17 THEN 'api'
            WHEN MOD(I * 7, 20) < 19 THEN 'email' ELSE 'faq' END,
       CASE WHEN MOD(I, 5) = 0 THEN 'FERNHOLLOW-FEES' ELSE 'AURELIA-CSP' END,
       DATE(T) - MOD(I, 60) DAYS,
       'Synthetic question ' || VARCHAR(I) || ': can I still get a refund on my booking after the fare changed?',
       'Synthetic draft ' || VARCHAR(I) || ': yes, you can request a refund within 24 hours of booking for a full '
         || 'refund, and after that a travel credit valid for 12 months, minus the change fee of $75.',
       'Synthetic answer ' || VARCHAR(I) || ': you can request a refund within 24 hours of booking for a full refund. '
         || 'After that, unused fares become a travel credit valid for 12 months.',
       DEC,
       CASE DEC WHEN 'PASS' THEN 'ALL_SUPPORTED' WHEN 'CORRECTED' THEN 'CORRECTED_FROM_CLAUSES'
                ELSE CASE MOD(I, 3) WHEN 0 THEN 'NOT_COVERED' WHEN 1 THEN 'CORRECTION_FAILED'
                     ELSE 'ERROR_FAIL_CLOSED' END END,
       CASE WHEN MOD(I, 10) = 0 THEN 'ollama:qwen2.5:7b-instruct' ELSE 'openrouter:google/gemini-3.1-flash-lite' END,
       'p7', 800 + MOD(I * 37, 8000),
       '{"version":1,"synthetic":true,"claims":[{"pass":1,"claim_no":1,"verdict":"SUPPORTED","clause_id":"CXL-001",'
         || '"rule_check":"MATCH"},{"pass":1,"claim_no":2,"verdict":"SUPPORTED","clause_id":"CRD-001",'
         || '"rule_check":"NOT_APPLICABLE"}],"id":' || VARCHAR(I) || '}',
       LOWER(HEX(HASH(VARCHAR(I - 1), 2))), LOWER(HEX(HASH(VARCHAR(I), 2)))
FROM R"""
SQL_LOAD_CITATIONS = """INSERT INTO CLAIM_CITATION (LEDGER_ID, PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT,
  RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, DISTANCE)
WITH D(N) AS (VALUES 0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
     G(I) AS (SELECT CAST(? AS BIGINT) + A.N * 1000 + B.N * 100 + C.N * 10 + E.N FROM D A, D B, D C, D E),
     K(NO) AS (VALUES 1, 2),
     R(I, NO, V) AS (SELECT I, NO, CASE WHEN MOD(I * 7 + NO, 10) < 7 THEN 'SUPPORTED'
                                         WHEN MOD(I * 7 + NO, 10) < 9 THEN 'CONTRADICTED' ELSE 'NOT_COVERED' END
                     FROM G, K WHERE I <= ?)
SELECT I, 1, NO, 'Synthetic claim ' || VARCHAR(NO) || ' of decision ' || VARCHAR(I),
       CASE MOD(I + NO * 3, 8) WHEN 0 THEN 'bereavement' WHEN 1 THEN 'cancellation' WHEN 2 THEN 'change_fees'
            WHEN 3 THEN 'baggage' WHEN 4 THEN 'refund' WHEN 5 THEN 'delay' WHEN 6 THEN 'credit' ELSE 'pets' END,
       V, V, CASE WHEN V = 'CONTRADICTED' THEN 'MISMATCH' WHEN V = 'SUPPORTED' THEN 'MATCH' ELSE 'NOT_APPLICABLE' END,
       CASE WHEN V = 'NOT_COVERED' THEN NULL ELSE 'CXL-001' END, CASE WHEN V = 'NOT_COVERED' THEN NULL ELSE 'v1' END,
       CASE WHEN V = 'NOT_COVERED' THEN NULL ELSE DATE('2026-01-01') END, 0.2
FROM R"""
SQL_SET_HEAD = "UPDATE CHAIN_HEAD SET LAST_LEDGER_ID = ?, LAST_HASH = (SELECT ROW_HASH FROM ANSWER_LEDGER WHERE LEDGER_ID = ?)"
SQL_AUDIT_MONTH = ("SELECT REASON_CODE, MODEL_INFO, COUNT(*), AVG(LATENCY_MS) FROM V_AUDIT_DECISIONS "
                   "WHERE CREATED_AT >= ? AND CREATED_AT < ? AND DECISION = 'ESCALATED' GROUP BY REASON_CODE, MODEL_INFO")
SQL_AUDIT_MONTH_COUNT = ("SELECT DECISION, COUNT(*) FROM V_AUDIT_DECISIONS WHERE CREATED_AT >= ? AND CREATED_AT < ? "
                         "GROUP BY DECISION")
MARCH = (datetime(2026, 3, 1), datetime(2026, 4, 1))

# name, what it answers, statement, bound values
QUERIES: list[tuple[str, str, str, tuple[Any, ...]]] = [
    ("analytics_decisions", "Analytics page: decisions and mean latency by outcome (V_DECISION_STATS)",
     policy.SQL_DECISIONS, ()),
    ("analytics_reasons", "Analytics page: decisions by reason (V_DECISION_STATS)", policy.SQL_REASONS, ()),
    ("analytics_areas", "Analytics page: claim verdicts by policy area (V_CLAIM_OUTCOMES_BY_AREA)", policy.SQL_AREAS, ()),
    ("audit_month_escalations", "An auditor's question: March's escalations by reason and model (V_AUDIT_DECISIONS)",
     SQL_AUDIT_MONTH, MARCH),
    ("audit_month_decisions", "March's decisions by outcome (V_AUDIT_DECISIONS)", SQL_AUDIT_MONTH_COUNT, MARCH),
    ("ledger_page", "The audit ledger page, newest first", ledger.SQL_LIST, (0, 50)),
    ("ledger_page_by_decision", "One decision type, newest first", ledger.SQL_LIST_BY_DECISION, ("ESCALATED", 0, 50)),
]


def flat_statements(target: str) -> list[schema.Statement]:
    """The shipped object files, minus partitioning and the MQTs, with the analytics views as they were."""
    out = []
    for st in schema.load_statements(target):
        if st.kind == "mqt" or st.name in NEW_ONLY:
            continue
        if st.kind == "table" and st.name == "ANSWER_LEDGER":
            sql, n = PARTITION_CLAUSE.subn("", st.sql)
            if n != 1:
                raise RuntimeError("the ANSWER_LEDGER DDL no longer has the partition clause this benchmark removes")
            st = replace(st, sql=sql)
        if st.kind == "index" and st.sql.rstrip().endswith(" NOT PARTITIONED"):  # only valid on a partitioned table
            st = replace(st, sql=st.sql.rstrip()[: -len(" NOT PARTITIONED")])
        if st.kind == "view" and st.name in OLD_VIEWS:
            st = replace(st, sql=OLD_VIEWS[st.name].replace("ASOF.", f"{target}."))
        out.append(st)
    return out


# The synthetic decisions cite no seeded clause (this benchmark loads no policy), so Db2's release rules
# (08_release_rules.sql) would refuse every PASS and CORRECTED row: they are left out of both designs here.
NOT_INSTALLED = {"ANSWER_LEDGER_RELEASE_RULES"}


def _install(conn: ibm_db_dbi.Connection, target: str, flat: bool) -> None:
    if db.query(conn, "SELECT 1 FROM SYSCAT.SCHEMATA WHERE SCHEMANAME = ?", (target,)):
        schema.drop(conn, target)
    statements = flat_statements(target) if flat else schema.load_statements(target)
    schema.install(conn, target, [st for st in statements if st.name not in NOT_INSTALLED])
    seed.seed_documents(conn, target)
    seed.seed_chain_head(conn, target)


def _load(conn: ibm_db_dbi.Connection, target: str, rows: int) -> float:
    db.use_schema(conn, target)
    step = YEAR_SECONDS * 1_000_000 // rows  # microseconds between decisions, so the rows span one year
    started = time.monotonic()
    for base in range(1, rows + 1, BATCH):
        last = min(base + BATCH - 1, rows)  # the generator yields 10,000 IDs from `base`; keep one batch of them
        # Synthetic rows, not logged: on TESTDB's circular log a fast bulk insert can fill it (SQL0964C) before
        # the page cleaners let Db2 reuse it. Logging resumes at the commit; the timed appends below are logged.
        db.execute(conn, "ALTER TABLE ANSWER_LEDGER ACTIVATE NOT LOGGED INITIALLY")
        db.execute(conn, "ALTER TABLE CLAIM_CITATION ACTIVATE NOT LOGGED INITIALLY")
        db.execute(conn, SQL_LOAD_LEDGER, (base, step, last))
        db.execute(conn, SQL_LOAD_CITATIONS, (base, last))
        conn.commit()
    db.execute(conn, SQL_SET_HEAD, (rows, rows))
    conn.commit()
    loaded = (db.query(conn, "SELECT COUNT(*) FROM ANSWER_LEDGER")[0][0],
              db.query(conn, "SELECT COUNT(*) FROM CLAIM_CITATION")[0][0])
    if loaded != (rows, 2 * rows):
        raise RuntimeError(f"{target}: loaded {loaded[0]} decisions and {loaded[1]} citations, expected {rows} and {2 * rows}")
    return time.monotonic() - started


def _runstats(settings: Settings, container: str, target: str) -> None:
    tables = [r[0].strip() for r in _admin_query(settings, "SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND "
                                                  "TABNAME IN ('ANSWER_LEDGER', 'CLAIM_CITATION', 'MQT_DECISION_STATS', "
                                                  "'MQT_CLAIM_OUTCOMES')", (target,))]
    script = f"db2 connect to {db.ident(settings.db2_database)} > /dev/null && " + " && ".join(
        f'db2 "RUNSTATS ON TABLE {db.ident(target)}.{db.ident(t)} WITH DISTRIBUTION AND SAMPLED DETAILED INDEXES ALL" '
        "> /dev/null" for t in tables)
    subprocess.run(["docker", "exec", "-u", settings.db2_admin_user, container, "bash", "-lc", script], check=True,
                   timeout=1800, capture_output=True)


def _admin_query(settings: Settings, sql: str, params: tuple[Any, ...]) -> list[tuple[Any, ...]]:
    with db.connection(settings, "admin") as conn:
        return db.query(conn, sql, params)


def _time(conn: ibm_db_dbi.Connection, sql: str, params: tuple[Any, ...], runs: int = 5) -> tuple[float, list[Any]]:
    rows = db.query(conn, sql, params)  # warm-up
    times = []
    for _ in range(runs):
        started = time.perf_counter()
        rows = db.query(conn, sql, params)
        times.append((time.perf_counter() - started) * 1000)
    return statistics.median(times), rows


def _plan(conn: ibm_db_dbi.Connection, settings: Settings, container: str, target: str, name: str, sql: str,
          params: tuple[Any, ...], plans_dir: Path) -> dict[str, Any]:
    db.use_schema(conn, target)
    explain._explain(conn, sql, params)
    db.use_schema(conn, db.ident(settings.db2_admin_user))  # explain tables live in the owner's schema
    ops, objects = explain._latest_plan(conn)
    db.use_schema(conn, target)
    text = explain._exfmt(settings, container)
    if text:
        plans_dir.mkdir(parents=True, exist_ok=True)
        (plans_dir / f"{name}__{target.lower()}.txt").write_text(explain._plan_graph(text), encoding="utf-8")
    return {"cost": round(ops[0][1], 2) if ops else None, "operators": sorted({o for o, _ in ops}), "objects": objects}


def _appends(settings: Settings, target: str, n: int = 100) -> float:
    entry = ledger.LedgerEntry(
        request_id="", channel="api", doc_id="AURELIA-CSP", as_of=date(2026, 3, 10), question_redacted="q",
        draft_redacted="d", final_answer="f", decision="PASS", reason_code="ALL_SUPPORTED", model_info="bench",
        prompt_version="bench", latency_ms=1, verdicts={"version": 1, "claims": [
            {"pass": 1, "claim_no": 1, "text": "c", "area": "refund", "verdict": "SUPPORTED", "llm_verdict": "SUPPORTED",
             "rule_check": "MATCH", "clause_id": "CXL-001", "clause_version": "v1", "clause_bus_start": "2026-01-01",
             "clause_sys_start": None, "distance": 0.2, "quoted_span": None}]})
    times = []
    with db.connection(settings, "admin") as conn:
        for _ in range(n):
            started = time.perf_counter()
            ledger.append(conn, replace(entry, request_id=str(uuid.uuid4())), target)
            times.append((time.perf_counter() - started) * 1000)
    return statistics.median(times)


def run(settings: Settings, rows: int, keep: bool = False, plans_dir: Path = OUT_DIR) -> dict[str, Any]:
    container = find_db2_container(settings.db2_container)
    if container is None:
        raise SystemExit("the benchmark collects statistics and plans with Db2's own tools: a Db2 container is needed")
    result: dict[str, Any] = {"rows": rows, "citations": 2 * rows, "ran_at": datetime.now(UTC).isoformat(timespec="seconds"),
                              "git_commit": _commit(), "load_s": {}, "append_ms": {}, "queries": {}}
    with db.connection(settings, "admin") as conn:
        explain.ensure_explain_tables(conn, settings, container)
        for target, flat in ((FLAT, True), (PART, False)):
            print(f"{target}: install and load {rows:,} decisions", flush=True)
            _install(conn, target, flat)
            result["load_s"][target] = round(_load(conn, target, rows), 1)
            _runstats(settings, container, target)
        for name, what, sql, params in QUERIES:
            entry: dict[str, Any] = {"what": what}
            answers = []
            for target in (FLAT, PART):
                db.use_schema(conn, target)
                ms, rows_out = _time(conn, sql, params)
                answers.append(sorted(map(repr, rows_out)))
                entry[target] = {"median_ms": round(ms, 1), "rows": len(rows_out),
                                 **_plan(conn, settings, container, target, name, sql, params, plans_dir)}
            entry["same_rows"] = answers[0] == answers[1]  # both designs must give the same answer
            result["queries"][name] = entry
            print(f"  {name}: {entry[FLAT]['median_ms']} ms -> {entry[PART]['median_ms']} ms", flush=True)
    for target in (FLAT, PART):
        result["append_ms"][target] = round(_appends(settings, target), 1)
    if not keep:
        with db.connection(settings, "admin") as conn:
            for target in (FLAT, PART):
                schema.drop(conn, target)
    return result


def _commit() -> str:
    done = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=PROJECT_ROOT,
                          check=False)
    return done.stdout.strip() or "unknown"


def report(r: dict[str, Any]) -> str:
    lines = ["# Ledger benchmark: partitions and materialized query tables", "",
             f"Generated by `python -m asof.ledgerbench --rows {r['rows']}` at `{r['git_commit']}` on {r['ran_at'][:10]}: "
             f"Db2 12.1.5 Community Edition under Rosetta on a MacBook Air, {r['rows']:,} synthetic decisions over 2026 "
             f"and {r['citations']:,} claim citations, statistics collected. Times are medians of 5 runs after a warm-up; "
             "costs are the optimizer's estimates in timerons; the faster time is in bold. "
             "Plans: [docs/ledgerbench/](ledgerbench/).", "",
             "| Query | Before: unpartitioned, views over base tables | After: monthly partitions, views over MQTs | "
             "Rows |", "|---|---|---|---|"]
    for name, q in r["queries"].items():
        f, p = q[FLAT], q[PART]
        plans = f"[before]({OUT_DIR.name}/{name}__{FLAT.lower()}.txt), [after]({OUT_DIR.name}/{name}__{PART.lower()}.txt)"
        before, after = f"{f['median_ms']} ms", f"{p['median_ms']} ms"
        if p["median_ms"] < f["median_ms"]:
            after = f"**{after}**"
        elif f["median_ms"] < p["median_ms"]:
            before = f"**{before}**"
        lines.append(f"| {q['what']} ({plans}) | {before}, cost {f['cost']} | {after}, cost {p['cost']} | {p['rows']} |")
    lines += ["", f"Loading (`NOT LOGGED INITIALLY`, {BATCH:,} rows a batch) took {r['load_s'][FLAT]} s before and "
              f"{r['load_s'][PART]} s after, where the MQTs are maintained on every insert. One logged append through "
              f"APPEND_LEDGER, median of 100: {r['append_ms'][FLAT]} ms before, {r['append_ms'][PART]} ms after.", "",
              "", ("Both designs returned identical rows for every query." if all(q["same_rows"] for q in r["queries"].values())
                   else "WARNING: the designs returned different rows for: "
                   + ", ".join(n for n, q in r["queries"].items() if not q["same_rows"])), "",
              "## What each plan reads", ""]
    for name, q in r["queries"].items():
        lines.append(f"- **{name}**: before {', '.join(q[FLAT]['objects']) or 'no table'}; "
                     f"after {', '.join(q[PART]['objects']) or 'no table'}.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m asof.ledgerbench", description=(__doc__ or "").split("\n\n")[0])
    p.add_argument("--rows", type=int, default=1_000_000)
    p.add_argument("--keep", action="store_true", help="keep both schemas for inspection")
    args = p.parse_args(argv)
    if not BATCH <= args.rows <= 5_000_000 or args.rows % BATCH:
        p.error(f"--rows must be a multiple of {BATCH:,} between {BATCH:,} and 5,000,000")
    settings = get_settings()
    settings.require("db2_admin_password")
    result = run(settings, args.rows, args.keep)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "results.json").write_text(json.dumps(result, indent=1, default=str) + "\n", encoding="utf-8")
    REPORT.write_text(report(result), encoding="utf-8")
    print(f"wrote {REPORT.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
