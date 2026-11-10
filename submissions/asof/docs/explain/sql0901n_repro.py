"""Standalone repro: on Db2 12.1.5.0 a forced vector-index scan under FOR BUSINESS_TIME AS OF fails with SQL0901N
("Fetched nodes unexpectedly unsorted.") once the search list is larger than 200.

    pip install ibm_db
    DB2_PASSWORD=... python sql0901n_repro.py --host localhost --port 50000 --database testdb --user db2inst1

Needs only ibm_db and a user who may create a buffer pool, a table space and a schema (the instance owner db2inst1
of IBM's Community Edition image works). It builds schema R901 with a bitemporal clause table shaped like AsOf's
POLICY_CLAUSE, 1,500 clustered 384-dimension unit vectors (clause versions with business-time periods), a B-tree index
on (DOC_ID, BUS_START, BUS_END), a cosine vector index and statistics; runs four queries; prints what each returned;
and drops everything it created. Deterministic (fixed seeds).

Seen on 12.1.5.0 (IBM's stock image icr.io/db2_community/db2:12.1.5.0, x86-64):
    search list 200, FOR BUSINESS_TIME AS OF   -> 10 rows
    search list 1000, no date predicate        -> 10 rows
    search list 210, FOR BUSINESS_TIME AS OF   -> SQL0901N ... "Fetched nodes unexpectedly unsorted."
    no guideline (the optimizer's own plan)    -> 10 rows
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from datetime import date, timedelta

import ibm_db

DIM, ROWS, DOC = 384, 1_500, "R901-DOC"
VERSIONS, RETIRED, TOPIC_SIZE = (1, 6), 0.1, 25
SPREAD_CLAUSE, SPREAD_VERSION, SPREAD_QUERY = 0.042, 0.02, 0.042
FIRST_START, OPEN_END = date(2019, 1, 1), date(9999, 12, 30)
QUERY_FROM, QUERY_TO = date(2021, 1, 1), date(2026, 11, 10)

SETUP = [
    "CREATE BUFFERPOOL R901_BP32K SIZE 4000 PAGESIZE 32K",
    "CREATE TABLESPACE R901_TS32K PAGESIZE 32K BUFFERPOOL R901_BP32K",
    "CREATE SCHEMA R901",
    """CREATE TABLE R901.CLAUSE (
         CLAUSE_ID VARCHAR(32) NOT NULL, DOC_ID VARCHAR(32) NOT NULL, TITLE VARCHAR(200) NOT NULL,
         CLAUSE_TEXT VARCHAR(4000) NOT NULL, RULE_JSON VARCHAR(2000) NOT NULL, EMBEDDING VECTOR(384, FLOAT32) NOT NULL,
         BUS_START DATE NOT NULL, BUS_END DATE NOT NULL,
         SYS_START TIMESTAMP(12) NOT NULL GENERATED ALWAYS AS ROW BEGIN,
         SYS_END TIMESTAMP(12) NOT NULL GENERATED ALWAYS AS ROW END,
         TRANS_ID TIMESTAMP(12) GENERATED ALWAYS AS TRANSACTION START ID,
         PERIOD BUSINESS_TIME (BUS_START, BUS_END), PERIOD SYSTEM_TIME (SYS_START, SYS_END),
         CONSTRAINT PK_R901 PRIMARY KEY (CLAUSE_ID, BUSINESS_TIME WITHOUT OVERLAPS)) IN R901_TS32K""",
    "CREATE TABLE R901.CLAUSE_HIST LIKE R901.CLAUSE IN R901_TS32K",
    "ALTER TABLE R901.CLAUSE ADD VERSIONING USE HISTORY TABLE R901.CLAUSE_HIST",
    "CREATE INDEX R901.IX_R901_DOC_ASOF ON R901.CLAUSE (DOC_ID, BUS_START, BUS_END)",
]
VECTOR_INDEX = "CREATE VECTOR INDEX R901.IX_R901_EMBEDDING ON R901.CLAUSE (EMBEDDING) WITH DISTANCE COSINE"
RUNSTATS = "CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE R901.CLAUSE WITH DISTRIBUTION AND INDEXES ALL')"
TEARDOWN = ["ALTER TABLE R901.CLAUSE DROP VERSIONING", "DROP TABLE R901.CLAUSE_HIST", "DROP TABLE R901.CLAUSE",
            "DROP SCHEMA R901 RESTRICT", "DROP TABLESPACE R901_TS32K", "DROP BUFFERPOOL R901_BP32K"]

SELECT = ("SELECT c.CLAUSE_ID, c.TITLE, c.CLAUSE_TEXT, c.RULE_JSON, c.BUS_START, c.BUS_END, "
          "VECTOR_DISTANCE(c.EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) AS DIST ")
AS_OF = SELECT + ("FROM R901.CLAUSE FOR BUSINESS_TIME AS OF ? AS c WHERE c.DOC_ID = ? "
                  "ORDER BY DIST FETCH APPROX FIRST 10 ROWS ONLY ")
ANY_DATE = SELECT + "FROM R901.CLAUSE AS c WHERE c.DOC_ID = ? ORDER BY DIST FETCH APPROX FIRST 10 ROWS ONLY "
# TABID 'Q1' is the clause table's quantifier: TABLE='C' is not found once Db2 rewrites the period (EXP0009W).
GUIDE = "/* <OPTGUIDELINES><IXSCAN TABID='Q1' INDEX='IX_R901_EMBEDDING' SEARCH_LIST_SIZE='{n}'/></OPTGUIDELINES> */"


def unit(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def lit(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def plan(rows: int, seed: int = 11) -> list[tuple[int, list[tuple[date, date]]]]:
    """Clause ids with 1 to 6 consecutive versions each, each version lasting 90 to 989 days."""
    rng = random.Random(f"{seed}:plan")
    out: list[tuple[int, list[tuple[date, date]]]] = []
    total = 0
    while total < rows:
        n = min(rng.randint(*VERSIONS), rows - total)
        start, retired, periods = FIRST_START + timedelta(days=rng.randrange(5 * 365)), rng.random() < RETIRED, []
        for v in range(n):
            end = start + timedelta(days=90 + rng.randrange(900))
            periods.append((start, OPEN_END if v == n - 1 and not retired else end))
            start = end
        out.append((len(out), periods))
        total += n
    return out


def base_vector(topics: list[list[float]], cid: int, seed: int = 11) -> tuple[random.Random, list[float]]:
    rng = random.Random(f"{seed}:clause:{cid}")
    return rng, unit([x + rng.gauss(0, SPREAD_CLAUSE) for x in topics[cid % len(topics)]])


def run(conn, label: str, sql: str, params: tuple) -> None:
    try:
        stmt = ibm_db.prepare(conn, sql)
        ibm_db.execute(stmt, params)
        rows = 0
        while ibm_db.fetch_tuple(stmt):
            rows += 1
        print(f"{label:42s} -> {rows} rows")
    except Exception as exc:  # the defect surfaces here as SQL0901N
        print(f"{label:42s} -> {' '.join(str(exc).split())[-170:]}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=50000)
    p.add_argument("--database", default="testdb")
    p.add_argument("--user", default="db2inst1")
    a = p.parse_args()
    if not os.environ.get("DB2_PASSWORD"):
        sys.exit("set DB2_PASSWORD")
    conn = ibm_db.connect(f"DATABASE={a.database};HOSTNAME={a.host};PORT={a.port};PROTOCOL=TCPIP;"
                          f"UID={a.user};PWD={os.environ['DB2_PASSWORD']};", "", "")
    info = ibm_db.server_info(conn)
    print(info.DBMS_NAME, info.DBMS_VER)
    clauses = plan(ROWS)
    topics_rng = random.Random("11:topics")
    topics = [unit([topics_rng.gauss(0, 1) for _ in range(DIM)]) for _ in range(max(4, len(clauses) // TOPIC_SIZE))]
    try:
        for sql in SETUP:
            ibm_db.exec_immediate(conn, sql)
        ins = ibm_db.prepare(conn, "INSERT INTO R901.CLAUSE (CLAUSE_ID, DOC_ID, TITLE, CLAUSE_TEXT, RULE_JSON, EMBEDDING, "
                                   "BUS_START, BUS_END) VALUES (?, ?, ?, ?, ?, VECTOR(?, 384, FLOAT32), ?, ?)")
        for cid, periods in clauses:
            rng, base = base_vector(topics, cid)
            for v, (start, end) in enumerate(periods, 1):
                vec = lit(unit([x + rng.gauss(0, SPREAD_VERSION) for x in base]))
                ibm_db.execute(ins, (f"SYN-{cid:06d}", DOC, f"Clause {cid}", f"Clause {cid}, version {v}.",
                                     json.dumps({"version": v}), vec, start.isoformat(), end.isoformat()))
        ibm_db.exec_immediate(conn, VECTOR_INDEX)
        ibm_db.exec_immediate(conn, RUNSTATS)
        q_rng = random.Random("11:queries")
        cid, _ = clauses[q_rng.randrange(len(clauses))]
        _, base = base_vector(topics, cid)
        on = (QUERY_FROM + timedelta(days=q_rng.randrange((QUERY_TO - QUERY_FROM).days))).isoformat()
        q = lit(unit([x + q_rng.gauss(0, SPREAD_QUERY) for x in base]))
        run(conn, "search list 200, FOR BUSINESS_TIME AS OF", AS_OF + GUIDE.format(n=200), (q, on, DOC))
        run(conn, "search list 1000, no date predicate", ANY_DATE + GUIDE.format(n=1000), (q, DOC))
        run(conn, "search list 210, FOR BUSINESS_TIME AS OF", AS_OF + GUIDE.format(n=210), (q, on, DOC))
        run(conn, "no guideline (the optimizer's own plan)", AS_OF, (q, on, DOC))
    finally:
        for sql in TEARDOWN:
            try:
                ibm_db.exec_immediate(conn, sql)
            except Exception:  # noqa: S110 - best-effort cleanup of what this script created
                pass
        ibm_db.close(conn)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
