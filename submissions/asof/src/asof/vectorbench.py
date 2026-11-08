"""Exact versus approximate vector search in Db2, measured.

    python -m asof.vectorbench                        # 1,000 / 5,000 / 20,000 rows
    python -m asof.vectorbench --sizes 2000,50000 --queries 30

AsOf's own table holds a few dozen clause versions, where an exact scan is the right plan and
the app asks for it (FETCH EXACT). This tool answers what happens at scale. For each size it
builds a throwaway table of clustered 384-dimension unit vectors in AsOf's 32K tablespace, adds
the same native vector index (CREATE VECTOR INDEX ... WITH DISTANCE COSINE, type VANN), collects
statistics, and runs the same queries three ways:

1. FETCH EXACT: the exact top-10, the reference.
2. FETCH APPROX: latency, recall@10 against the exact result, and whether Db2's plan used the index,
   with k as a constant and, for comparison, as a parameter marker.
3. FETCH APPROX with a date filter on half the rows, AsOf's situation: does an approximate top-k
   still return k rows, and the right ones?

Results go to docs/vector_benchmark.md. Every statement is a literal; values are bound. The
throwaway schema ASOF_BENCH is dropped at the end unless --keep is given.
"""

from __future__ import annotations

import argparse
import math
import random
import shutil
import statistics
import subprocess
import sys
import time
from datetime import date, datetime
from typing import Any

import ibm_db_dbi

from . import db, schema
from .config import PROJECT_ROOT, ConfigError, Settings, get_settings
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
                     "AND OBJECT_NAME = 'VEC_BENCH_ANN'")


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


def _index_used(conn: ibm_db_dbi.Connection, sql: str, params: tuple[Any, ...], owner: str) -> bool:
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
    used = bool(db.query(conn, SQL_INDEX_IN_PLAN)[0][0] > 0)
    db.use_schema(conn, BENCH_SCHEMA)
    return used


def _runstats(settings: Settings, container: str | None) -> str:
    cmd = f"RUNSTATS ON TABLE {db.ident(BENCH_SCHEMA)}.VEC_BENCH WITH DISTRIBUTION AND INDEXES ALL"
    if container:
        script = f'db2 connect to {db.ident(settings.db2_database)} > /dev/null && db2 "{cmd}" > /dev/null'
        done = subprocess.run(["docker", "exec", "-u", settings.db2_admin_user, container, "bash", "-lc", script],
                              capture_output=True, text=True, timeout=1800)
        if done.returncode == 0:
            return "CLP"
    return "none"


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
    used = _index_used(conn, SQL_APPROX, (qs[0],), owner)
    used_param_k = _index_used(conn, SQL_APPROX_PARAM_K, (qs[0], k), owner)
    used_on = _index_used(conn, SQL_APPROX_ON, (ON, ON, qs[0]), owner)
    return {
        "rows": rows, "insert_s": insert_s, "index_s": index_s, "stats": stats,
        "exact_p50": statistics.median(exact_ms), "approx_p50": statistics.median(approx_ms),
        "recall": statistics.fmean(recall), "index_used": used, "index_used_param_k": used_param_k,
        "recall_on": statistics.fmean(recall_on), "short_on": sum(short_on), "index_used_on": used_on,
        "queries": len(qs),
    }


def render(results: list[dict[str, Any]], k: int, host: str) -> str:
    lines = ["# Exact versus approximate vector search in Db2", "",
             f"Generated by `python -m asof.vectorbench` on {datetime.now():%Y-%m-%d} ({host}). Synthetic, clustered, "
             f"unit-length 384-dimension vectors in AsOf's 32K tablespace, with the same native index AsOf uses "
             f"(`CREATE VECTOR INDEX ... WITH DISTANCE COSINE`, type VANN), statistics collected, top-{k}.", "",
             "| Rows | Insert | Index build | Exact p50 | Approx p50 | Recall@{k} | Index used (constant k) | "
             "Index used (k as `?`) | Date filter: recall@{k} | ...fewer than {k} rows | ...index used |".replace("{k}", str(k)),
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        lines.append(f"| {r['rows']:,} | {r['insert_s']:.0f} s | {r['index_s']:.1f} s | {r['exact_p50']:.1f} ms | "
                     f"{r['approx_p50']:.1f} ms | {r['recall']:.2f} | {'yes' if r['index_used'] else 'no'} | "
                     f"{'yes' if r['index_used_param_k'] else 'no'} | "
                     f"{r['recall_on']:.2f} | {r['short_on']} of {r['queries']} | {'yes' if r['index_used_on'] else 'no'} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m asof.vectorbench")
    p.add_argument("--sizes", default="1000,5000,20000", help="comma-separated row counts")
    p.add_argument("--queries", type=int, default=20)
    p.add_argument("--keep", action="store_true", help="keep the ASOF_BENCH schema afterwards")
    args = p.parse_args(argv)
    sizes = [int(x) for x in args.sizes.split(",") if x.strip()]
    if not sizes or min(sizes) < 100 or max(sizes) > 1_000_000 or not 2 <= args.queries <= 200:
        p.error("sizes must be between 100 and 1,000,000; queries between 2 and 200")
    try:
        settings = get_settings()
        conn = db.connect(settings, "admin")
    except (ConfigError, db.DatabaseError) as exc:
        print(f"cannot connect: {exc}")
        return 2
    container = find_db2_container(settings.db2_container) if shutil.which("docker") else None
    results = []
    try:
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
        conn.close()
    host = "Db2 12.1.5 Community Edition, linux/amd64 under Rosetta on an Apple Silicon MacBook Air" \
        if container == "asof-db2" else "Db2 12.1.5"
    REPORT.write_text(render(results, K, host), encoding="utf-8")
    print(f"wrote {REPORT.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
