"""Exact versus approximate vector search in Db2, measured.

    python -m asof.vectorbench                        # 1,000 / 5,000 / 20,000 rows, plus the check's own query
    python -m asof.vectorbench --sizes 2000,50000 --queries 30 --clause-rows 100000

AsOf's own table holds a few dozen clause versions, where an exact scan is the right plan and
the app asks for it (FETCH EXACT). This tool answers what happens at scale, in two parts.

The check's own query. The retriever's statement (retriever.SQL_AS_OF) runs against AsOf's real
table layout: the seeded ASOF schema, and a throwaway ASOF_VBENCH schema built from the same DDL
with --clause-rows synthetic clause versions (several business-time versions per clause id,
contiguous periods, some clauses retired), loaded first and then given the native vector index,
then RUNSTATS. Each query runs four ways: EXACT and APPROX, each with and without
FOR BUSINESS_TIME AS OF. Recall@10 compares APPROX with EXACT under the same predicate, and the
plan says whether the optimizer used IX_CLAUSE_EMBEDDING.

A generic table. For each --sizes value it builds a throwaway table of clustered 384-dimension unit
vectors in AsOf's 32K tablespace, adds the same native vector index (CREATE VECTOR INDEX ... WITH
DISTANCE COSINE, type VANN), collects statistics, and runs the same queries three ways:

1. FETCH EXACT: the exact top-10, the reference.
2. FETCH APPROX: latency, recall@10 against the exact result, and whether Db2's plan used the index,
   with k as a constant and, for comparison, as a parameter marker.
3. FETCH APPROX with a date filter on half the rows: does an approximate top-k still return k rows,
   and the right ones?

Results go to docs/vector_benchmark.md; anything under its "## Earlier runs" heading is kept. Every
statement is a literal; values are bound. The throwaway schemas are dropped at the end unless --keep
is given.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import shutil
import statistics
import subprocess
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from importlib import resources
from typing import Any

import ibm_db_dbi

from . import db, retriever, schema
from .config import PROJECT_ROOT, ConfigError, Settings, get_settings
from .domains import AIRLINE, BANK
from .setup import find_db2_container

BENCH_SCHEMA = "ASOF_BENCH"
DIM = 384
REPORT = PROJECT_ROOT / "docs" / "vector_benchmark.md"
ON = date(2026, 3, 10)  # half the rows are "in force" on this date

SQL_TABLE = ("CREATE TABLE VEC_BENCH (ID INTEGER NOT NULL PRIMARY KEY, BUS_START DATE NOT NULL, BUS_END DATE NOT NULL, "
             "EMBEDDING VECTOR(384, FLOAT32) NOT NULL) IN ASOF_TS32K")
SQL_INDEX = ("CREATE VECTOR INDEX VEC_BENCH_ANN ON VEC_BENCH (EMBEDDING) WITH DISTANCE COSINE "
             "IN ASOF_TS32K COMPRESSED VECTORS IN ASOF_TS32K")
SQL_INSERT = "INSERT INTO VEC_BENCH (ID, BUS_START, BUS_END, EMBEDDING) VALUES (?, ?, ?, VECTOR(?, 384, FLOAT32))"
# k is a constant (10) on purpose: with a parameter marker in FETCH APPROX FIRST ? ROWS, Db2 12.1.5
# does not match the vector index at all and runs an exact scan (SQL_APPROX_PARAM_K shows it).
K = 10
SQL_EXACT = ("SELECT ID FROM VEC_BENCH ORDER BY VECTOR_DISTANCE(EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) "
             "FETCH EXACT FIRST 10 ROWS ONLY")
SQL_APPROX = ("SELECT ID FROM VEC_BENCH ORDER BY VECTOR_DISTANCE(EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) "
              "FETCH APPROX FIRST 10 ROWS ONLY")
SQL_APPROX_PARAM_K = ("SELECT ID FROM VEC_BENCH ORDER BY VECTOR_DISTANCE(EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) "
                      "FETCH APPROX FIRST ? ROWS ONLY")
SQL_EXACT_ON = ("SELECT ID FROM VEC_BENCH WHERE BUS_START <= ? AND BUS_END > ? "
                "ORDER BY VECTOR_DISTANCE(EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) FETCH EXACT FIRST 10 ROWS ONLY")
SQL_APPROX_ON = ("SELECT ID FROM VEC_BENCH WHERE BUS_START <= ? AND BUS_END > ? "
                 "ORDER BY VECTOR_DISTANCE(EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) FETCH APPROX FIRST 10 ROWS ONLY")
SQL_INDEX_IN_PLAN = ("SELECT COUNT(*) FROM EXPLAIN_OBJECT WHERE EXPLAIN_TIME = (SELECT MAX(EXPLAIN_TIME) FROM EXPLAIN_OBJECT) "
                     "AND OBJECT_NAME = ?")

# The check's own statement, four ways, at AsOf's real table layout. SQL_CLAUSE_EXACT_ON is the app's statement
# (k bound, as the retriever binds it); the others change only FETCH EXACT to FETCH APPROX FIRST 10 (a constant, or
# Db2 ignores the index) and/or drop FOR BUSINESS_TIME AS OF. tests/test_vector_tools.py pins that.
CLAUSE_SCHEMA = "ASOF_VBENCH"
CLAUSE_DOC = "VBENCH-POLICY"
CLAUSE_INDEX = "IX_CLAUSE_EMBEDDING"
# The shipped DDL objects the as-of query touches; the vector index is created after the load, like VEC_BENCH's.
CLAUSE_OBJECTS = {"POLICY_DOC", "POLICY_CLAUSE", "POLICY_CLAUSE_HIST", "IX_CLAUSE_DOC_ASOF", "IX_CLAUSE_HIST_ID"}
SQL_CLAUSE_EXACT_ON = retriever.SQL_AS_OF
SQL_CLAUSE_APPROX_ON = (
    "SELECT c.CLAUSE_ID, c.AREA, c.TITLE, c.VERSION_LABEL, c.CLAUSE_TEXT, c.RULE_JSON, "
    "c.BUS_START, c.BUS_END, c.SYS_START, "
    "VECTOR_DISTANCE(c.EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) AS DIST "
    "FROM POLICY_CLAUSE FOR BUSINESS_TIME AS OF ? AS c "
    "WHERE c.DOC_ID = ? ORDER BY DIST FETCH APPROX FIRST 10 ROWS ONLY"
)
SQL_CLAUSE_EXACT_ALL = (
    "SELECT c.CLAUSE_ID, c.AREA, c.TITLE, c.VERSION_LABEL, c.CLAUSE_TEXT, c.RULE_JSON, "
    "c.BUS_START, c.BUS_END, c.SYS_START, "
    "VECTOR_DISTANCE(c.EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) AS DIST "
    "FROM POLICY_CLAUSE AS c "
    "WHERE c.DOC_ID = ? ORDER BY DIST FETCH EXACT FIRST 10 ROWS ONLY"
)
SQL_CLAUSE_APPROX_ALL = (
    "SELECT c.CLAUSE_ID, c.AREA, c.TITLE, c.VERSION_LABEL, c.CLAUSE_TEXT, c.RULE_JSON, "
    "c.BUS_START, c.BUS_END, c.SYS_START, "
    "VECTOR_DISTANCE(c.EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) AS DIST "
    "FROM POLICY_CLAUSE AS c "
    "WHERE c.DOC_ID = ? ORDER BY DIST FETCH APPROX FIRST 10 ROWS ONLY"
)
# Neither EXACT nor APPROX: with a vector index present, Db2's default is the approximate search (explained at scale
# by python -m asof.explain --scale, which is why the app's statement says FETCH EXACT).
SQL_CLAUSE_DEFAULT_ALL = (
    "SELECT c.CLAUSE_ID, c.AREA, c.TITLE, c.VERSION_LABEL, c.CLAUSE_TEXT, c.RULE_JSON, "
    "c.BUS_START, c.BUS_END, c.SYS_START, "
    "VECTOR_DISTANCE(c.EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) AS DIST "
    "FROM POLICY_CLAUSE AS c "
    "WHERE c.DOC_ID = ? ORDER BY DIST FETCH FIRST 10 ROWS ONLY"
)
# The optimizer never picked the vector index under FOR BUSINESS_TIME AS OF (docs/explain/*_100k.txt), so these force
# it with an embedded optimizer guideline, to measure what an approximate search under the period would return. TABID
# 'Q1' is the clause table's quantifier: TABLE='C' is not found once Db2 rewrites the period (EXP0009W). 200 is the
# largest search list that runs: with any date predicate, 210 and above fail at 100,000 rows with SQL0901N ("Fetched
# nodes unexpectedly unsorted."), while without one 1,000 runs (docs/db2.md).
SQL_CLAUSE_FORCED_ON_100 = (
    "SELECT c.CLAUSE_ID, c.AREA, c.TITLE, c.VERSION_LABEL, c.CLAUSE_TEXT, c.RULE_JSON, "
    "c.BUS_START, c.BUS_END, c.SYS_START, "
    "VECTOR_DISTANCE(c.EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) AS DIST "
    "FROM POLICY_CLAUSE FOR BUSINESS_TIME AS OF ? AS c "
    "WHERE c.DOC_ID = ? ORDER BY DIST FETCH APPROX FIRST 10 ROWS ONLY "
    "/* <OPTGUIDELINES><IXSCAN TABID='Q1' INDEX='IX_CLAUSE_EMBEDDING' SEARCH_LIST_SIZE='100'/></OPTGUIDELINES> */"
)
SQL_CLAUSE_FORCED_ON_200 = (
    "SELECT c.CLAUSE_ID, c.AREA, c.TITLE, c.VERSION_LABEL, c.CLAUSE_TEXT, c.RULE_JSON, "
    "c.BUS_START, c.BUS_END, c.SYS_START, "
    "VECTOR_DISTANCE(c.EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) AS DIST "
    "FROM POLICY_CLAUSE FOR BUSINESS_TIME AS OF ? AS c "
    "WHERE c.DOC_ID = ? ORDER BY DIST FETCH APPROX FIRST 10 ROWS ONLY "
    "/* <OPTGUIDELINES><IXSCAN TABID='Q1' INDEX='IX_CLAUSE_EMBEDDING' SEARCH_LIST_SIZE='200'/></OPTGUIDELINES> */"
)
SQL_CLAUSE_DOC = "INSERT INTO POLICY_DOC (DOC_ID, TITLE, OWNER_TEAM, SOURCE_NOTE) VALUES (?, ?, ?, ?)"
SQL_CLAUSE_INSERT = ("INSERT INTO POLICY_CLAUSE (CLAUSE_ID, DOC_ID, AREA, TITLE, VERSION_LABEL, CLAUSE_TEXT, RULE_JSON, "
                     "EMBEDDING, BUS_START, BUS_END) VALUES (?, ?, ?, ?, ?, ?, ?, VECTOR(?, 384, FLOAT32), ?, ?)")
SQL_CLAUSE_COUNT = "SELECT COUNT(*) FROM POLICY_CLAUSE"
SQL_CLAUSE_IN_FORCE = "SELECT COUNT(*) FROM POLICY_CLAUSE FOR BUSINESS_TIME AS OF ? WHERE DOC_ID = ?"
SQL_HAS_INDEX = "SELECT COUNT(*) FROM SYSCAT.INDEXES WHERE INDSCHEMA = ? AND INDNAME = ? AND INDEXTYPE = 'VANN'"
# The four forms: name, statement, whether it carries FOR BUSINESS_TIME AS OF, whether it is approximate.
CLAUSE_FORMS = (("exact_all", SQL_CLAUSE_EXACT_ALL, False, False), ("approx_all", SQL_CLAUSE_APPROX_ALL, False, True),
                ("exact_on", SQL_CLAUSE_EXACT_ON, True, False), ("approx_on", SQL_CLAUSE_APPROX_ON, True, True),
                ("forced_on_100", SQL_CLAUSE_FORCED_ON_100, True, True),
                ("forced_on_200", SQL_CLAUSE_FORCED_ON_200, True, True))
FORCED = (("forced_on_100", 100), ("forced_on_200", 200))

# Synthetic clause versions. The spreads are per-dimension Gaussian noise on unit vectors; in 384 dimensions they give
# cosine distances of about 0.4 between clauses of one topic, about 0.14 between two versions of a clause (BRV-002 v1
# to v2 is 0.13 in the seeded corpus) and about 0.3 from a claim to the clause it is about.
VERSIONS = (1, 6)            # versions per clause id, uniform: 3.5 on average
RETIRED = 0.1                # share of clause ids whose last version ends (the rest stay in force, BUS_END 9999-12-30)
TOPIC_SIZE = 25              # clause ids per topic
SPREAD_CLAUSE, SPREAD_VERSION, SPREAD_QUERY = 0.042, 0.02, 0.042
FIRST_START = date(2019, 1, 1)
QUERY_FROM, QUERY_TO = date(2021, 1, 1), date(2026, 11, 10)
OPEN_END = date(9999, 12, 30)
AREAS = ("bereavement", "cancellation", "change_fee", "baggage", "refund", "delay", "travel_credit", "pets")
SEEDED_CASES = (("cases_dev.jsonl", AIRLINE.doc_id), ("bank_cases_dev.jsonl", BANK.doc_id))


def _unit(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _lit(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def make_data(rows: int, queries: int, seed: int = 7) -> tuple[list[tuple[Any, ...]], list[str]]:
    """Clustered unit vectors (real embeddings cluster by topic), half valid before ON, half on it."""
    rng = random.Random(seed)
    centers = [_unit([rng.gauss(0, 1) for _ in range(DIM)]) for _ in range(max(4, rows // 50))]
    data = []
    for i in range(rows):
        c = centers[i % len(centers)]
        v = _unit([x + rng.gauss(0, 0.06) for x in c])
        in_force = i % 2 == 0
        data.append((i, date(2026, 1, 1) if in_force else date(2026, 5, 1),
                     date(2026, 5, 1) if in_force else date(9999, 12, 30), _lit(v)))
    qs = [_lit(_unit([x + rng.gauss(0, 0.06) for x in centers[rng.randrange(len(centers))]])) for _ in range(queries)]
    return data, qs


def _ids(conn: ibm_db_dbi.Connection, sql: str, params: tuple[Any, ...]) -> tuple[list[int], float]:
    t = time.perf_counter()
    rows = db.query(conn, sql, params)
    return [r[0] for r in rows], (time.perf_counter() - t) * 1000


def _index_used(conn: ibm_db_dbi.Connection, sql: str, params: tuple[Any, ...], owner: str,
                index: str = "VEC_BENCH_ANN", schema_name: str = BENCH_SCHEMA) -> bool:
    """Whether Db2's plan for `sql` reads `index`. The statement is explained, not run."""
    db.execute(conn, "SET CURRENT EXPLAIN MODE = EXPLAIN")
    try:
        cur = conn.cursor()
        try:
            cur.execute(sql, params)
        finally:
            cur.close()
    finally:
        db.execute(conn, "SET CURRENT EXPLAIN MODE = NO")
        conn.commit()
    db.use_schema(conn, owner)
    used = bool(db.query(conn, SQL_INDEX_IN_PLAN, (index,))[0][0] > 0)
    db.use_schema(conn, schema_name)
    return used


def _runstats(settings: Settings, container: str | None, schema_name: str = BENCH_SCHEMA,
              table: str = "VEC_BENCH") -> str:
    cmd = f"RUNSTATS ON TABLE {db.ident(schema_name)}.{db.ident(table)} WITH DISTRIBUTION AND INDEXES ALL"
    if container:
        script = f'db2 connect to {db.ident(settings.db2_database)} > /dev/null && db2 "{cmd}" > /dev/null'
        done = subprocess.run(["docker", "exec", "-u", settings.db2_admin_user, container, "bash", "-lc", script],
                              capture_output=True, text=True, timeout=1800)
        if done.returncode == 0:
            return "CLP"
    return "none"


_ELAPSED = re.compile(r"Elapsed Time is:\s+([0-9.]+) seconds")
_SQL_ERROR = re.compile(r"SQL\d{4,5}N")


def _batch_value(value: Any) -> str:
    """A bound value as db2batch's --#PARAM wants it. Vectors, dates and ids here never contain a quote."""
    if isinstance(value, bool) or not isinstance(value, (str, date, int)):
        raise TypeError(f"unsupported parameter {type(value).__name__}")
    if isinstance(value, int):
        return str(value)
    text = value.isoformat() if isinstance(value, date) else value
    if "'" in text or "\n" in text:
        raise ValueError("a db2batch parameter cannot contain a quote or a newline")
    return "'" + text + "'"


def batch_script(schema_name: str, runs: list[tuple[str, str, tuple[Any, ...]]]) -> str:
    """A db2batch input file: the schema, then each statement with its values as --#PARAM lines, one per marker."""
    lines = ["--#SET ROWS_OUT 0", f"SET CURRENT SCHEMA {db.ident(schema_name)};"]
    for _, sql, params in runs:
        if sql.count("?") != len(params):
            raise ValueError("every parameter marker needs a value")
        lines += [f"--#PARAM {_batch_value(v)}" for v in params]
        lines.append(sql + ";")
    return "\n".join(lines) + "\n"


def server_ms(settings: Settings, container: str | None, schema_name: str,
              runs: list[tuple[str, str, tuple[Any, ...]]]) -> dict[str, list[float]] | None:
    """Elapsed milliseconds (prepare, execute, fetch every row) per run name, timed inside the Db2 container by IBM's
    db2batch at isolation CS, so the client's network round trip is not in the numbers. None without a container."""
    if container is None:
        return None
    script = (f'f="$(mktemp)" && cat > "$f" && db2batch -d {db.ident(settings.db2_database)} -f "$f" -i complete '
              f'-iso CS -cli; rc=$?; rm -f "$f"; exit $rc')
    done = subprocess.run(["docker", "exec", "-i", "-u", settings.db2_admin_user, container, "bash", "-lc", script],
                          input=batch_script(schema_name, runs), capture_output=True, text=True, timeout=3600)
    elapsed = [float(x) * 1000 for x in _ELAPSED.findall(done.stdout)]
    error = _SQL_ERROR.search(done.stdout + done.stderr)  # db2batch prints SQL errors on stderr
    if done.returncode != 0 or error or len(elapsed) != len(runs) + 1:  # + the SET CURRENT SCHEMA
        raise RuntimeError(f"db2batch failed (exit {done.returncode}, {len(elapsed)} timings for {len(runs) + 1} "
                           f"statements{', ' + error.group(0) if error else ''})")
    out: dict[str, list[float]] = {}
    for (name, _, _), ms in zip(runs, elapsed[1:], strict=True):
        out.setdefault(name, []).append(ms)
    return out


def bench_size(conn: ibm_db_dbi.Connection, settings: Settings, container: str | None, rows: int, queries: int,
               k: int = K) -> dict[str, Any]:
    data, qs = make_data(rows, queries)
    schema.drop(conn, BENCH_SCHEMA)
    db.use_schema(conn, BENCH_SCHEMA)
    db.execute(conn, SQL_TABLE)
    conn.commit()
    t = time.perf_counter()
    cur = conn.cursor()
    try:
        for i in range(0, rows, 500):
            cur.executemany(SQL_INSERT, data[i:i + 500])
            conn.commit()
    finally:
        cur.close()
    insert_s = time.perf_counter() - t
    t = time.perf_counter()
    db.execute(conn, SQL_INDEX)
    conn.commit()
    index_s = time.perf_counter() - t
    stats = _runstats(settings, container)
    owner = db.ident(settings.db2_admin_user)

    exact_ms, approx_ms, recall, short_on, recall_on = [], [], [], [], []
    db.query(conn, SQL_EXACT, (qs[0],))  # warm the bufferpool and the plan cache before timing
    db.query(conn, SQL_APPROX, (qs[0],))
    for q in qs:
        e, te = _ids(conn, SQL_EXACT, (q,))
        a, ta = _ids(conn, SQL_APPROX, (q,))
        exact_ms.append(te)
        approx_ms.append(ta)
        recall.append(len(set(e) & set(a)) / k)
        e_on, _ = _ids(conn, SQL_EXACT_ON, (ON, ON, q))
        a_on, _ = _ids(conn, SQL_APPROX_ON, (ON, ON, q))
        short_on.append(len(a_on) < k)
        recall_on.append(len(set(e_on) & set(a_on)) / k)
    timed = server_ms(settings, container, BENCH_SCHEMA, [("warm", SQL_EXACT, (qs[0],)), ("warm", SQL_APPROX, (qs[0],))]
                      + [run for q in qs for run in (("exact", SQL_EXACT, (q,)), ("approx", SQL_APPROX, (q,)))])
    if timed is not None:
        exact_ms, approx_ms = timed["exact"], timed["approx"]
    used = _index_used(conn, SQL_APPROX, (qs[0],), owner)
    used_param_k = _index_used(conn, SQL_APPROX_PARAM_K, (qs[0], k), owner)
    used_on = _index_used(conn, SQL_APPROX_ON, (ON, ON, qs[0]), owner)
    return {
        "rows": rows, "insert_s": insert_s, "index_s": index_s, "stats": stats,
        "exact_p50": statistics.median(exact_ms), "approx_p50": statistics.median(approx_ms),
        "recall": statistics.fmean(recall), "index_used": used, "index_used_param_k": used_param_k,
        "recall_on": statistics.fmean(recall_on), "short_on": sum(short_on), "index_used_on": used_on,
        "queries": len(qs), "timing": "client" if timed is None else "db2batch",
    }


# --- The check's own query, at AsOf's table layout -------------------------------------------------------------------

@dataclass(frozen=True)
class SyntheticClause:
    cid: int
    periods: tuple[tuple[date, date], ...]  # contiguous business-time periods, oldest first


def clause_plan(rows: int, seed: int = 11) -> list[SyntheticClause]:
    """Clause ids with 1 to 6 versions each, `rows` versions in all. Each clause starts between 2019 and 2023; each
    version lasts 90 to 989 days and the next one starts where it ends; the last stays in force unless retired."""
    rng = random.Random(f"{seed}:plan")
    plan: list[SyntheticClause] = []
    total = 0
    while total < rows:
        n = min(rng.randint(*VERSIONS), rows - total)
        start = FIRST_START + timedelta(days=rng.randrange(5 * 365))
        retired = rng.random() < RETIRED
        periods = []
        for v in range(n):
            end = start + timedelta(days=90 + rng.randrange(900))
            if v == n - 1 and not retired:
                end = OPEN_END
            periods.append((start, end))
            start = end
        plan.append(SyntheticClause(len(plan), tuple(periods)))
        total += n
    return plan


def _topics(plan: list[SyntheticClause], seed: int) -> list[list[float]]:
    rng = random.Random(f"{seed}:topics")
    return [_unit([rng.gauss(0, 1) for _ in range(DIM)]) for _ in range(max(4, len(plan) // TOPIC_SIZE))]


def _clause_base(topics: list[list[float]], cid: int, seed: int) -> tuple[random.Random, list[float]]:
    """A clause's own direction, from a generator of its own, so rows and queries can be made apart."""
    rng = random.Random(f"{seed}:clause:{cid}")
    return rng, _unit([x + rng.gauss(0, SPREAD_CLAUSE) for x in topics[cid % len(topics)]])


def clause_rows(plan: list[SyntheticClause], seed: int = 11) -> Iterator[tuple[Any, ...]]:
    """POLICY_CLAUSE rows for SQL_CLAUSE_INSERT, one clause at a time (100,000 vectors as text would be 400 MB)."""
    topics = _topics(plan, seed)
    for c in plan:
        rng, base = _clause_base(topics, c.cid, seed)
        for v, (start, end) in enumerate(c.periods, 1):
            vec = _unit([x + rng.gauss(0, SPREAD_VERSION) for x in base])
            yield (f"SYN-{c.cid:06d}", CLAUSE_DOC, AREAS[c.cid % len(AREAS)], f"Synthetic clause {c.cid}", f"v{v}",
                   f"Synthetic clause {c.cid}, version {v} (vector benchmark).", json.dumps({"version": v}), _lit(vec),
                   start, end)


def clause_queries(plan: list[SyntheticClause], queries: int, seed: int = 11) -> list[tuple[str, date, str]]:
    """(vector, as-of date, doc id): a claim near a random clause, on a random date from 2021 to 2026."""
    topics = _topics(plan, seed)
    rng = random.Random(f"{seed}:queries")
    out = []
    for _ in range(queries):
        c = plan[rng.randrange(len(plan))]
        _, base = _clause_base(topics, c.cid, seed)
        on = QUERY_FROM + timedelta(days=rng.randrange((QUERY_TO - QUERY_FROM).days))
        out.append((_lit(_unit([x + rng.gauss(0, SPREAD_QUERY) for x in base])), on, CLAUSE_DOC))
    return out


def clause_corpus_ready(conn: ibm_db_dbi.Connection, rows: int, target: str = CLAUSE_SCHEMA) -> bool:
    """True when `target` (ASOF_VBENCH) already holds `rows` clause versions and the vector index (a kept earlier build)."""
    if not schema.table_exists(conn, target, "POLICY_CLAUSE"):
        return False
    db.use_schema(conn, target)
    held = int(db.query(conn, SQL_CLAUSE_COUNT)[0][0])
    return held == rows and int(db.query(conn, SQL_HAS_INDEX, (target, CLAUSE_INDEX))[0][0]) == 1


def build_clause_corpus(conn: ibm_db_dbi.Connection, settings: Settings, container: str | None, rows: int,
                        seed: int = 11, target: str = CLAUSE_SCHEMA) -> dict[str, Any]:
    """`target` (ASOF_VBENCH) from the shipped DDL (policy tables, history, versioning, indexes), `rows` synthetic versions,
    then the shipped vector index and RUNSTATS. Returns load timings."""
    statements = schema.load_statements(target)
    tables = [st for st in statements if st.kind in ("bufferpool", "tablespace")
              or (st.kind in ("table", "versioning", "index") and st.name in CLAUSE_OBJECTS)]
    vector_index = [st for st in statements if st.kind == "index" and st.name == CLAUSE_INDEX]
    if len(vector_index) != 1:
        raise RuntimeError(f"{CLAUSE_INDEX} is not in the shipped DDL")
    schema.drop(conn, target)
    schema.install(conn, target, tables)
    db.use_schema(conn, target)
    db.execute(conn, SQL_CLAUSE_DOC, (CLAUSE_DOC, "Synthetic policy library (vector benchmark)", "benchmark",
                                      "Synthetic rows; dropped after the run"))
    conn.commit()
    plan = clause_plan(rows, seed)
    t = time.perf_counter()
    cur = conn.cursor()
    try:
        batch: list[tuple[Any, ...]] = []
        for row in clause_rows(plan, seed):
            batch.append(row)
            if len(batch) == 500:
                cur.executemany(SQL_CLAUSE_INSERT, batch)
                conn.commit()
                batch = []
        if batch:
            cur.executemany(SQL_CLAUSE_INSERT, batch)
            conn.commit()
    finally:
        cur.close()
    insert_s = time.perf_counter() - t
    t = time.perf_counter()
    schema.install(conn, target, vector_index)
    index_s = time.perf_counter() - t
    stats = _runstats(settings, container, target, "POLICY_CLAUSE")
    db.use_schema(conn, target)
    return {"rows": rows, "clause_ids": len(plan), "insert_s": insert_s, "index_s": index_s, "stats": stats}


def seeded_queries(conn: ibm_db_dbi.Connection, settings: Settings) -> list[tuple[str, date, str]]:
    """Every airline and bank dev case's draft, embedded with the app's own model, at the case's as-of date."""
    from .embeddings import get_embeddings  # torch loads only when the seeded corpus is measured

    cases = []
    for name, doc_id in SEEDED_CASES:
        text = (resources.files("asof") / "eval" / name).read_text(encoding="utf-8")
        cases += [(json.loads(line), doc_id) for line in text.splitlines() if line.strip()]
    vectors = get_embeddings(settings.embedding_model).embed_documents([c["draft"] for c, _ in cases])
    return [(db.vector_literal(v), date.fromisoformat(c["as_of"]), doc_id) for (c, doc_id), v in zip(cases, vectors,
                                                                                                    strict=True)]


def _versions(conn: ibm_db_dbi.Connection, sql: str, params: tuple[Any, ...]) -> tuple[list[tuple[str, date]], float]:
    """The (CLAUSE_ID, BUS_START) of each row, which names one clause version, and the time taken."""
    t = time.perf_counter()
    rows = db.query(conn, sql, params)
    return [(r[0], r[6]) for r in rows], (time.perf_counter() - t) * 1000


def _form_params(on_date: bool, approx: bool, vec: str, on: date, doc: str) -> tuple[Any, ...]:
    if on_date:
        return (vec, on, doc) if approx else (vec, on, doc, K)
    return (vec, doc)


def measure_clauses(conn: ibm_db_dbi.Connection, settings: Settings, container: str | None, schema_name: str,
                    queries: list[tuple[str, date, str]], owner: str) -> dict[str, Any]:
    """Each query four ways; recall@10 of each APPROX form against EXACT under the same predicate; p50 latencies
    (inside the container when there is one); and whether each form's plan reads the vector index."""
    db.use_schema(conn, schema_name)
    versions = int(db.query(conn, SQL_CLAUSE_COUNT)[0][0])
    vec, on, doc = queries[0]
    for _, sql, on_date, approx in CLAUSE_FORMS:  # warm the bufferpool and the plan cache before timing
        db.query(conn, sql, _form_params(on_date, approx, vec, on, doc))
    client_ms: dict[str, list[float]] = {name: [] for name, *_ in CLAUSE_FORMS}
    compared = (("approx_all", "exact_all"), ("approx_on", "exact_on"), ("forced_on_100", "exact_on"),
                ("forced_on_200", "exact_on"))
    recall: dict[str, list[float]] = {name: [] for name, _ in compared}
    short = dict.fromkeys(recall, 0)
    in_force, nearest = [], []
    runs = [("warm", sql, _form_params(on_date, approx, vec, on, doc)) for _, sql, on_date, approx in CLAUSE_FORMS]
    for vec, on, doc in queries:
        got = {}
        for name, sql, on_date, approx in CLAUSE_FORMS:
            params = _form_params(on_date, approx, vec, on, doc)
            got[name], took = _versions(conn, sql, params)
            client_ms[name].append(took)
            runs.append((name, sql, params))
        for approx_name, exact_name in compared:
            exact = set(got[exact_name])
            recall[approx_name].append(len(exact & set(got[approx_name])) / len(exact) if exact else 1.0)
            short[approx_name] += len(got[approx_name]) < min(K, len(exact))
        in_force.append(int(db.query(conn, SQL_CLAUSE_IN_FORCE, (on, doc))[0][0]))
        nearest.append(float(db.query(conn, SQL_CLAUSE_EXACT_ON, (vec, on, doc, 1))[0][9]) if got["exact_on"] else 0.0)
    used = {name: _index_used(conn, sql, _form_params(on_date, approx, *queries[0]), owner, CLAUSE_INDEX, schema_name)
            for name, sql, on_date, approx in CLAUSE_FORMS}
    timed = server_ms(settings, container, schema_name, runs)
    ms = client_ms if timed is None else {name: timed[name] for name in client_ms}
    return {"versions": versions, "queries": len(queries), "in_force": statistics.fmean(in_force),
            "nearest": statistics.fmean(nearest), "p50": {n: statistics.median(v) for n, v in ms.items()},
            "timing": "client" if timed is None else "db2batch",
            "recall": {n: statistics.fmean(v) for n, v in recall.items()},
            "min_recall": {n: min(v) for n, v in recall.items()}, "short": short, "index_used": used}


def _yes(flag: bool) -> str:
    return "yes" if flag else "no"


def render_clauses(results: list[tuple[str, dict[str, Any]]]) -> list[str]:
    lines = ["## The check's own query", "",
             "The retriever's statement (`retriever.SQL_AS_OF`) at AsOf's real table layout, each query four ways: "
             "`FETCH EXACT` (what the app runs) and `FETCH APPROX FIRST 10 ROWS ONLY`, each with and without "
             "`FOR BUSINESS_TIME AS OF ?`. Recall@10 compares APPROX with EXACT under the same predicate and counts "
             "clause versions, `(CLAUSE_ID, BUS_START)`. \"Index used\" is whether Db2's plan read `IX_CLAUSE_EMBEDDING`.",
             "",
             "| Corpus | Versions | In force on the date (mean) | Exact, any date p50 | Approx, any date p50 | "
             "Recall@10, any date | Index used, any date | Exact, as of the date p50 | Approx, as of the date p50 | "
             "Recall@10, as of the date (min) | Fewer than 10 rows | Index used, as of the date |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for label, r in results:
        p, rc, u = r["p50"], r["recall"], r["index_used"]
        lines.append(
            f"| {label} | {r['versions']:,} | {r['in_force']:,.0f} | {p['exact_all']:.1f} ms | {p['approx_all']:.1f} ms | "
            f"{rc['approx_all']:.2f} | {_yes(u['approx_all'])} | {p['exact_on']:.1f} ms | {p['approx_on']:.1f} ms | "
            f"{rc['approx_on']:.2f} ({r['min_recall']['approx_on']:.1f}) | {r['short']['approx_on']} of {r['queries']} | "
            f"{_yes(u['approx_on'])} |")
    lines += ["", "Forcing the vector index under the period with an embedded optimizer guideline "
              "(`<IXSCAN TABID='Q1' INDEX='IX_CLAUSE_EMBEDDING' SEARCH_LIST_SIZE='...'/>`), which the app does not do:", "",
              "| Corpus | Search list size | Approx, as of the date p50 | Recall@10 (min) | Fewer than 10 rows | Index used |",
              "|---|---|---|---|---|---|"]
    for label, r in results:
        for name, size in FORCED:
            lines.append(f"| {label} | {size:,} | {r['p50'][name]:.1f} ms | {r['recall'][name]:.2f} "
                         f"({r['min_recall'][name]:.1f}) | {r['short'][name]} of {r['queries']} | "
                         f"{_yes(r['index_used'][name])} |")
    lines.append("")
    for label, r in results:
        if "clause_ids" in r:
            built = (f", loaded in {r['insert_s']:.0f} s, vector index built in {r['index_s']:.0f} s after the load"
                     if "insert_s" in r else "")
            lines.append(f"- {label}: {r['versions']:,} versions of {r['clause_ids']:,} clause ids (1 to 6 versions each, "
                         f"contiguous business-time periods from 2019, {RETIRED:.0%} of clauses retired){built}. Each "
                         f"query is a claim near a random clause on a random date from {QUERY_FROM:%Y} to {QUERY_TO:%Y}; "
                         f"the nearest version in force was {r['nearest']:.2f} away on average.")
        else:
            lines.append(f"- {label}: {r['queries']} queries; the nearest version in force was {r['nearest']:.2f} away "
                         f"on average.")
    return lines


HISTORY = "## Earlier runs"


def _timing_note(results: list[dict[str, Any]]) -> str:
    if results and all(r.get("timing") == "db2batch" for r in results):
        return ("Latencies are p50s timed inside the Db2 container by IBM's `db2batch` (prepare, execute and fetch, "
                "isolation CS), so the client's network round trip is not in them.")
    return "Latencies are p50s measured at the client, so they include the network round trip to Db2."


def kept_history(text: str) -> str:
    """Everything from the "## Earlier runs" heading of an existing report, so a new run keeps the old ones."""
    at = text.find(HISTORY)
    return text[at:].rstrip() + "\n" if at != -1 else ""


def render(results: list[dict[str, Any]], k: int, host: str, clauses: list[tuple[str, dict[str, Any]]] | None = None,
           history: str = "") -> str:
    lines = ["# Exact versus approximate vector search in Db2", "",
             f"Generated by `python -m asof.vectorbench` on {datetime.now():%Y-%m-%d} ({host}). "
             + _timing_note([r for _, r in clauses or []] + results), ""]
    if clauses:
        lines += render_clauses(clauses) + [""]
    if results:
        lines += ["## A generic table", "",
                  f"Synthetic, clustered, unit-length 384-dimension vectors in AsOf's 32K tablespace, with the same native "
                  f"index AsOf uses (`CREATE VECTOR INDEX ... WITH DISTANCE COSINE`, type VANN), statistics collected, "
                  f"top-{k}. The date filter is a plain `BUS_START <= ? AND BUS_END > ?` that half the rows pass.", "",
                  "| Rows | Insert | Index build | Exact p50 | Approx p50 | Recall@{k} | Index used (constant k) | "
                  "Index used (k as `?`) | Date filter: recall@{k} | ...fewer than {k} rows | ...index used |"
                  .replace("{k}", str(k)),
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in results:
            lines.append(f"| {r['rows']:,} | {r['insert_s']:.0f} s | {r['index_s']:.1f} s | {r['exact_p50']:.1f} ms | "
                         f"{r['approx_p50']:.1f} ms | {r['recall']:.2f} | {_yes(r['index_used'])} | "
                         f"{_yes(r['index_used_param_k'])} | "
                         f"{r['recall_on']:.2f} | {r['short_on']} of {r['queries']} | {_yes(r['index_used_on'])} |")
        lines.append("")
    text = "\n".join(lines)
    return text + ("\n" + history if history else "")


def _print_clauses(label: str, r: dict[str, Any]) -> None:
    p, rc, u = r["p50"], r["recall"], r["index_used"]
    print(f"{label}: {r['versions']:,} versions, {r['in_force']:,.0f} in force  | any date: exact {p['exact_all']:.1f} ms, "
          f"approx {p['approx_all']:.1f} ms, recall {rc['approx_all']:.2f}, index {u['approx_all']}  | as of: exact "
          f"{p['exact_on']:.1f} ms, approx {p['approx_on']:.1f} ms, recall {rc['approx_on']:.2f} "
          f"(min {r['min_recall']['approx_on']:.1f}), short {r['short']['approx_on']}, index {u['approx_on']}  | forced: "
          + ", ".join(f"L={size} {p[n]:.1f} ms recall {rc[n]:.2f} short {r['short'][n]} index {u[n]}" for n, size in FORCED),
          flush=True)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m asof.vectorbench")
    p.add_argument("--sizes", default="1000,5000,20000", help="comma-separated row counts for the generic table, or 0")
    p.add_argument("--queries", type=int, default=20)
    p.add_argument("--clause-rows", type=int, default=100_000,
                   help="synthetic clause versions for the check's own query (0: the seeded corpus only)")
    p.add_argument("--host", default="", help="the machine, for the report (at most 400 characters)")
    p.add_argument("--keep", action="store_true", help="keep the ASOF_BENCH and ASOF_VBENCH schemas afterwards")
    args = p.parse_args(argv)
    sizes = [int(x) for x in args.sizes.split(",") if x.strip() and int(x) != 0]
    if (sizes and (min(sizes) < 100 or max(sizes) > 1_000_000)) or not 2 <= args.queries <= 200 \
            or not (args.clause_rows == 0 or 100 <= args.clause_rows <= 1_000_000) or len(args.host) > 400:
        p.error("sizes and clause rows must be between 100 and 1,000,000; queries between 2 and 200; --host at most 400 "
                "characters")
    try:
        settings = get_settings()
        conn = db.connect(settings, "admin")
    except (ConfigError, db.DatabaseError) as exc:
        print(f"cannot connect: {exc}")
        return 2
    from .explain import ensure_explain_tables  # explain imports this module for its statements

    container = find_db2_container(settings.db2_container) if shutil.which("docker") else None
    owner = db.ident(settings.db2_admin_user)
    results, clauses = [], []
    try:
        ensure_explain_tables(conn, settings, container)
        seeded = measure_clauses(conn, settings, container, db.SCHEMA, seeded_queries(conn, settings), owner)
        clauses.append((f"Seeded `{db.SCHEMA}` (dev-case drafts as queries)", seeded))
        _print_clauses("seeded", seeded)
        if args.clause_rows:
            built = (None if clause_corpus_ready(conn, args.clause_rows)
                     else build_clause_corpus(conn, settings, container, args.clause_rows))
            if built:
                print(f"built {CLAUSE_SCHEMA}: {built['rows']:,} versions of {built['clause_ids']:,} clauses, insert "
                      f"{built['insert_s']:.0f} s, vector index {built['index_s']:.1f} s, statistics {built['stats']}",
                      flush=True)
            plan = clause_plan(args.clause_rows)
            scaled = measure_clauses(conn, settings, container, CLAUSE_SCHEMA, clause_queries(plan, args.queries), owner)
            scaled["clause_ids"] = len(plan)
            if built:
                scaled.update(insert_s=built["insert_s"], index_s=built["index_s"])
            clauses.append((f"Synthetic, {len(plan):,} clause ids (`{CLAUSE_SCHEMA}`)", scaled))
            _print_clauses("synthetic", scaled)
        for n in sizes:
            r = bench_size(conn, settings, container, n, args.queries)
            results.append(r)
            print(f"{n:>8,} rows  insert {r['insert_s']:6.0f} s  index {r['index_s']:6.1f} s  exact {r['exact_p50']:7.1f} ms  "
                  f"approx {r['approx_p50']:7.1f} ms  recall {r['recall']:.2f}  index used {r['index_used']} "
                  f"(k as ? {r['index_used_param_k']})  "
                  f"| filtered recall {r['recall_on']:.2f}, short {r['short_on']}/{r['queries']}", flush=True)
    finally:
        if not args.keep:
            schema.drop(conn, BENCH_SCHEMA)
            schema.drop(conn, CLAUSE_SCHEMA)
        conn.close()
    host = args.host or ("Db2 12.1.5 Community Edition, linux/amd64 under Rosetta on an Apple Silicon MacBook Air"
                         if container == "asof-db2" else "Db2 12.1.5")
    old = REPORT.read_text(encoding="utf-8") if REPORT.exists() else ""
    REPORT.write_text(render(results, K, host, clauses, kept_history(old)), encoding="utf-8")
    print(f"wrote {REPORT.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
