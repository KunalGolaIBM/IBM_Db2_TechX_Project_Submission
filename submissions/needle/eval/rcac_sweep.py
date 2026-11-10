"""RCAC x DiskANN headline experiment (runs INSIDE the codespace, next to Db2).

Question: does row and column access control (CREATE PERMISSION) on a table with a DiskANN
vector index change (a) whether the optimizer uses the vector index for FETCH APPROX FIRST k,
and (b) recall@k of APPROX vs EXACT, as a function of the fraction of rows a user may see?
And does a per-user router (src/needle/rcac.py) restore recall?

Credentials are read from STDIN as KEY=VALUE lines (never from argv, never written to disk):
    grep -E '^(DB2_|NDL_)' needle/.env | gh codespace ssh -c $CS -- 'cd ~/ndl_rcac && python3 rcac_sweep.py <cmd>'

Commands
    synth-load      create NDL_DEV_RCAC.VEC_SYN, insert clustered random vectors, vector index, RUNSTATS
    explain         EXPLAIN the APPROX/EXACT statements as DB2INST1, print operators (+ db2exfmt text if asked)
    sweep           per-user recall@k / rows / latency for APPROX, EXACT, WHERE-baseline and router
Only integers validated with int() are interpolated into SQL (FETCH APPROX k must be a literal).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path

import ibm_db
import numpy as np

HERE = Path(__file__).resolve().parent
DIM = 768
SYN_SCHEMA = "NDL_DEV_RCAC"
SYN_TABLE = f"{SYN_SCHEMA}.VEC_SYN"


# ----------------------------------------------------------------------------- env / connections
def load_env_from_stdin() -> None:
    if sys.stdin is None or sys.stdin.isatty():
        return
    for line in sys.stdin.read().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()


def connect(user: str | None = None, password: str | None = None):
    user = user or os.environ["DB2_USER"]
    password = password or os.environ["DB2_PASSWORD"]
    db = os.environ.get("DB2_DATABASE", "VECDB")
    dsn = (f"DATABASE={db};HOSTNAME=localhost;PORT=50000;PROTOCOL=TCPIP;"
           f"UID={user};PWD={password};")
    return ibm_db.connect(dsn, "", "")


def user_password(authid: str) -> str:
    """NDL_P10 -> env NDL_P10_PASSWORD."""
    return os.environ[f"{authid.upper()}_PASSWORD"]


def rows(conn, sql: str, params: tuple | None = None) -> list[tuple]:
    if params:
        st = ibm_db.prepare(conn, sql)
        ibm_db.execute(st, params)
    else:
        st = ibm_db.exec_immediate(conn, sql)
    out = []
    r = ibm_db.fetch_tuple(st)
    while r:
        out.append(r)
        r = ibm_db.fetch_tuple(st)
    ibm_db.free_stmt(st)
    return out


def execute(conn, sql: str, ignore: tuple[str, ...] = ()) -> None:
    try:
        ibm_db.exec_immediate(conn, sql)
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if any(code in msg for code in ignore):
            print(f"  (ignored) {msg[:160]}")
            return
        raise


def vec_text(v: np.ndarray) -> str:
    return "[" + ",".join(f"{x:.6g}" for x in v.tolist()) + "]"


# ----------------------------------------------------------------------------- synthetic data
def make_clusters(n: int, n_clusters: int, seed: int, noise: float):
    rng = np.random.default_rng(seed)
    centers = rng.standard_normal((n_clusters, DIM)).astype(np.float32)
    centers /= np.linalg.norm(centers, axis=1, keepdims=True)
    cluster = rng.integers(0, n_clusters, size=n)
    pts = centers[cluster] + rng.standard_normal((n, DIM)).astype(np.float32) * (noise / np.sqrt(DIM))
    pts /= np.linalg.norm(pts, axis=1, keepdims=True)
    bucket = rng.integers(0, 100, size=n)  # independent of cluster, like a hash of the ID
    return centers, cluster, bucket, pts.astype(np.float32)


def make_queries(centers: np.ndarray, n_q: int, seed: int, noise: float):
    rng = np.random.default_rng(seed + 1000)
    cl = rng.integers(0, centers.shape[0], size=n_q)
    q = centers[cl] + rng.standard_normal((n_q, DIM)).astype(np.float32) * (noise / np.sqrt(DIM))
    q /= np.linalg.norm(q, axis=1, keepdims=True)
    return q.astype(np.float32)


def cmd_synth_load(args) -> None:
    centers, cluster, bucket, pts = make_clusters(args.n, args.clusters, args.seed, args.noise)
    queries = make_queries(centers, args.queries, args.seed, args.noise)
    np.save(HERE / "syn_points.npy", pts)
    np.save(HERE / "syn_bucket.npy", bucket)
    np.save(HERE / "syn_queries.npy", queries)
    conn = connect()
    try:
        execute(conn, f"CREATE SCHEMA {SYN_SCHEMA}", ignore=("SQL0601N",))
        if args.drop:
            execute(conn, f"DROP TABLE {SYN_TABLE}", ignore=("SQL0204N",))
        execute(conn, f"""CREATE TABLE {SYN_TABLE} (
                ID INTEGER NOT NULL PRIMARY KEY,
                ROW_BUCKET SMALLINT NOT NULL,
                CLUSTER_ID SMALLINT NOT NULL,
                EMB VECTOR({DIM}, FLOAT32) NOT NULL)""")
        ins = ibm_db.prepare(conn, f"INSERT INTO {SYN_TABLE} (ID, ROW_BUCKET, CLUSTER_ID, EMB) "
                                   f"VALUES (?, ?, ?, VECTOR(CAST(? AS CLOB(100K)), {DIM}, FLOAT32))")
        ibm_db.autocommit(conn, ibm_db.SQL_AUTOCOMMIT_OFF)
        t0 = time.time()
        for start in range(0, args.n, args.batch):
            end = min(start + args.batch, args.n)
            batch = tuple((i, int(bucket[i]), int(cluster[i]), vec_text(pts[i])) for i in range(start, end))
            ibm_db.execute_many(ins, batch)
            ibm_db.commit(conn)
            if (end // args.batch) % 10 == 0 or end == args.n:
                print(f"  inserted {end}/{args.n} in {time.time() - t0:.1f}s", flush=True)
        ibm_db.autocommit(conn, ibm_db.SQL_AUTOCOMMIT_ON)
        print("rows:", rows(conn, f"SELECT COUNT(*) FROM {SYN_TABLE}")[0][0])
        if args.index:
            t1 = time.time()
            execute(conn, f"CREATE VECTOR INDEX {SYN_SCHEMA}.VEC_SYN_VIX ON {SYN_TABLE} (EMB) WITH DISTANCE COSINE")
            print(f"vector index built in {time.time() - t1:.1f}s")
            execute(conn, f"CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE {SYN_TABLE} WITH DISTRIBUTION AND INDEXES ALL')")
            print("RUNSTATS done")
    finally:
        ibm_db.close(conn)


# ----------------------------------------------------------------------------- SQL builders
def knn_sql(table: str, k: int, approx: bool, where: str = "", sls: int | None = None) -> str:
    """k-NN statement; `sls` appends an inline optimization guideline IXSCAN SEARCH_LIST_SIZE (DiskANN L)."""
    k = int(k)
    mode = "APPROX" if approx else "EXACT"
    w = f"WHERE {where} " if where else ""
    g = (f" /* <OPTGUIDELINES><IXSCAN TABLE='T' SEARCH_LIST_SIZE='{int(sls)}'/></OPTGUIDELINES> */"
         if sls else "")
    return (f"SELECT ID, VECTOR_DISTANCE(EMB, VECTOR(CAST(? AS CLOB(100K)), {DIM}, FLOAT32), COSINE) AS D "
            f"FROM {table} T {w}"
            f"ORDER BY VECTOR_DISTANCE(EMB, VECTOR(CAST(? AS CLOB(100K)), {DIM}, FLOAT32), COSINE) "
            f"FETCH {mode} FIRST {k} ROWS ONLY{g}")


def explain_ops(conn, sql: str, params: tuple) -> list[tuple]:
    """EXPLAIN PLAN FOR <sql>; return operators of that explain instance."""
    st = ibm_db.prepare(conn, "EXPLAIN PLAN FOR " + sql)
    ibm_db.execute(st, params)
    return rows(conn, """
        SELECT O.OPERATOR_ID, O.OPERATOR_TYPE, CAST(O.TOTAL_COST AS DECIMAL(14,2)),
               COALESCE(S.OBJECT_SCHEMA, ''), COALESCE(S.OBJECT_NAME, '')
        FROM DB2INST1.EXPLAIN_OPERATOR O
        LEFT JOIN DB2INST1.EXPLAIN_STREAM S
          ON S.EXPLAIN_TIME = O.EXPLAIN_TIME AND S.SOURCE_NAME = O.SOURCE_NAME
         AND S.TARGET_ID = O.OPERATOR_ID AND S.OBJECT_NAME IS NOT NULL
        WHERE O.EXPLAIN_TIME = (SELECT MAX(EXPLAIN_TIME) FROM DB2INST1.EXPLAIN_INSTANCE)
        ORDER BY O.OPERATOR_ID""")


def cmd_explain(args) -> None:
    q = np.load(HERE / "syn_queries.npy")[0] if args.table == SYN_TABLE else None
    qt = vec_text(q)
    if not re.fullmatch(r"[A-Za-z0-9_]{1,30}", args.authid):
        raise SystemExit("authid must match [A-Za-z0-9_]{1,30}")
    conn = connect()
    k = int(args.k)
    stmts = [
        (f"APPROX k={k}", knn_sql(args.table, k, True)),
        (f"EXACT k={k}", knn_sql(args.table, k, False)),
        (f"APPROX k={k} WHERE ROW_BUCKET < {int(args.bucket)}",
         knn_sql(args.table, k, True, f"ROW_BUCKET < {int(args.bucket)}")),
        (f"APPROX k={k} WHERE ROW_BUCKET < (subquery on {SYN_ACCESS} for {args.authid})",
         knn_sql(args.table, k, True, f"ROW_BUCKET < (SELECT MAX_BUCKET FROM {SYN_ACCESS} "
                                      f"WHERE AUTHID = '{args.authid.upper()}')")),
    ]
    if args.sls:
        stmts.append((f"APPROX k={k} + guideline SEARCH_LIST_SIZE={int(args.sls)}",
                      knn_sql(args.table, k, True, sls=args.sls)))
    if args.only is not None:
        stmts = [stmts[args.only]]
    try:
        for label, sql in stmts:
            print(f"== {label}\n   {sql}")
            for r in explain_ops(conn, sql, (qt, qt)):
                print("   ", r)
    finally:
        ibm_db.close(conn)


# ----------------------------------------------------------------------------- RCAC on the synthetic table
SYN_ACCESS = f"{SYN_SCHEMA}.USER_ACCESS"
# AUTHID -> (MAX_BUCKET, SEES_EMBARGO). ROW_BUCKET is 0..99, so MAX_BUCKET = visible percent.
ACCESS_ROWS = {
    "DB2INST1": (100, 1), "NDL_SENIOR": (100, 1), "NDL_JUNIOR": (100, 0),
    "NDL_P10": (10, 0), "NDL_P25": (25, 0), "NDL_P50": (50, 0), "NDL_P75": (75, 0),
}
SWEEP_USERS = [("NDL_P10", 10), ("NDL_P25", 25), ("NDL_P50", 50), ("NDL_P75", 75), ("NDL_SENIOR", 100)]


def cmd_synth_rcac(args) -> None:
    conn = connect()
    try:
        if args.mode == "setup":
            execute(conn, f"""CREATE TABLE {SYN_ACCESS} (AUTHID VARCHAR(128) NOT NULL PRIMARY KEY,
                              MAX_BUCKET SMALLINT NOT NULL, SEES_EMBARGO SMALLINT NOT NULL DEFAULT 0)""",
                    ignore=("SQL0601N",))
            execute(conn, f"DELETE FROM {SYN_ACCESS}")
            ins = ibm_db.prepare(conn, f"INSERT INTO {SYN_ACCESS} VALUES (?, ?, ?)")
            for a, (mb, se) in ACCESS_ROWS.items():
                ibm_db.execute(ins, (a, mb, se))
            execute(conn, f"DROP PERMISSION {SYN_SCHEMA}.VEC_SYN_ROWS", ignore=("SQL0204N",))
            execute(conn, f"""CREATE PERMISSION {SYN_SCHEMA}.VEC_SYN_ROWS ON {SYN_TABLE}
                FOR ROWS WHERE ROW_BUCKET < (SELECT UA.MAX_BUCKET FROM {SYN_ACCESS} UA
                                             WHERE UA.AUTHID = SESSION_USER)
                ENFORCED FOR ALL ACCESS ENABLE""")
            for a in ACCESS_ROWS:
                if a != "DB2INST1":
                    execute(conn, f"GRANT CONNECT ON DATABASE TO USER {a}")
                    execute(conn, f"GRANT SELECT ON {SYN_TABLE} TO USER {a}")
            print("setup done:", rows(conn, f"SELECT * FROM {SYN_ACCESS} ORDER BY AUTHID"))
        elif args.mode == "activate":
            execute(conn, f"ALTER TABLE {SYN_TABLE} ACTIVATE ROW ACCESS CONTROL")
        elif args.mode == "deactivate":
            execute(conn, f"ALTER TABLE {SYN_TABLE} DEACTIVATE ROW ACCESS CONTROL")
        print("CONTROL column (R = row access control active):",
              rows(conn, "SELECT TABNAME, CONTROL FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TABNAME = 'VEC_SYN'",
                   (SYN_SCHEMA,)))
    finally:
        ibm_db.close(conn)


# ----------------------------------------------------------------------------- sweep
def exact_truth(pts: np.ndarray, bucket: np.ndarray, q: np.ndarray, max_bucket: int, k: int) -> list[set]:
    """Exact cosine top-k among rows with ROW_BUCKET < max_bucket (numpy cross-check of Db2 EXACT)."""
    idx = np.nonzero(bucket < max_bucket)[0]
    sims = q @ pts[idx].T  # all vectors unit-norm -> cosine similarity
    top = np.argsort(-sims, axis=1)[:, :k]
    return [set(int(idx[j]) for j in row) for row in top]


def timed_query(conn, sql: str, params_for, queries_text: list[str], k: int, warmup: int = 2):
    """Run one prepared statement for every query. Returns per-query (top-k ids, raw rows, ms)."""
    stmt = ibm_db.prepare(conn, sql)
    for qt in queries_text[:warmup]:
        ibm_db.execute(stmt, params_for(qt))
        while ibm_db.fetch_tuple(stmt):
            pass
    out = []
    for qt in queries_text:
        t0 = time.perf_counter()
        ibm_db.execute(stmt, params_for(qt))
        res = []
        r = ibm_db.fetch_tuple(stmt)
        while r:
            res.append(r)
            r = ibm_db.fetch_tuple(stmt)
        ms = (time.perf_counter() - t0) * 1000.0
        res.sort(key=lambda x: x[1])
        out.append(([int(x[0]) for x in res[:k]], len(res), ms))
    ibm_db.free_stmt(stmt)
    return out


def summarize(per_q, truth_db: list[set] | None, truth_np: list[set], k: int) -> dict:
    rec_np = [len(set(ids) & t) / k for (ids, _, _), t in zip(per_q, truth_np)]
    d = {
        "n_queries": len(per_q),
        "recall_vs_numpy_mean": round(statistics.fmean(rec_np), 4),
        "recall_vs_numpy_min": round(min(rec_np), 4),
        "rows_returned_mean": round(statistics.fmean(r for _, r, _ in per_q), 2),
        "rows_returned_min": min(r for _, r, _ in per_q),
        "queries_with_fewer_than_k_rows": sum(1 for ids, _, _ in per_q if len(ids) < k),
        "latency_ms_median": round(statistics.median(ms for _, _, ms in per_q), 2),
        "latency_ms_p95": round(float(np.percentile([ms for _, _, ms in per_q], 95)), 2),
        "per_query_recall_vs_numpy": [round(x, 2) for x in rec_np],
        "per_query_rows": [r for _, r, _ in per_q],
    }
    if truth_db is not None:
        rec_db = [len(set(ids) & t) / k for (ids, _, _), t in zip(per_q, truth_db)]
        d["recall_vs_db_exact_mean"] = round(statistics.fmean(rec_db), 4)
        d["recall_vs_db_exact_min"] = round(min(rec_db), 4)
    return d


def cmd_sweep(args) -> None:
    sys.path.insert(0, str(HERE))
    sys.path.insert(0, str(HERE.parent / "src"))
    try:
        from needle.rcac import Router, RouterConfig  # repo layout
    except ImportError:
        from rcac import Router, RouterConfig  # flat copy in the codespace

    k = int(args.k)
    depths = [int(x) for x in args.depths.split(",")]
    pts = np.load(HERE / "syn_points.npy")
    bucket = np.load(HERE / "syn_bucket.npy")
    queries = np.load(HERE / "syn_queries.npy")[: args.nq]
    qtexts = [vec_text(q) for q in queries]
    cfg = RouterConfig(exact_max_rows=args.exact_max_rows, overfetch=args.overfetch)
    out_path = HERE / args.out
    result = json.loads(out_path.read_text()) if out_path.exists() else {}
    result.setdefault("meta", {}).update({
        "table": SYN_TABLE, "rows": int(pts.shape[0]), "dim": DIM, "k": k, "n_queries": len(qtexts),
        "router_config": cfg.__dict__, "depths": depths,
        "note": "recall = |returned top-k  intersect  exact top-k over the user's visible rows| / k",
    })
    two = lambda qt: (qt, qt)  # noqa: E731

    if args.phase == "where":
        res = {}
        conn = connect()
        try:
            for user, m in SWEEP_USERS:
                truth_np = exact_truth(pts, bucket, queries, m, k)
                lit = f"ROW_BUCKET < {int(m)}"
                ex = timed_query(conn, knn_sql(SYN_TABLE, k, False, lit), two, qtexts, k)
                truth_db = [set(ids) for ids, _, _ in ex]
                r = {"exact": summarize(ex, None, truth_np, k)}
                for n in depths:
                    r[f"approx_depth{n}_literal"] = summarize(
                        timed_query(conn, knn_sql(SYN_TABLE, n, True, lit), two, qtexts, k), truth_db, truth_np, k)
                subq = (f"ROW_BUCKET < (SELECT UA.MAX_BUCKET FROM {SYN_ACCESS} UA "
                        f"WHERE UA.AUTHID = CAST(? AS VARCHAR(128)))")
                r[f"approx_depth{k}_subquery"] = summarize(
                    timed_query(conn, knn_sql(SYN_TABLE, k, True, subq), lambda qt, u=user: (qt, u, qt), qtexts, k),
                    truth_db, truth_np, k)
                res[f"{m}%"] = r
                print(f"[where] {m:3d}%  exact ms={r['exact']['latency_ms_median']}  "
                      f"approx10 literal recall={r[f'approx_depth{k}_literal']['recall_vs_db_exact_mean']} "
                      f"rows={r[f'approx_depth{k}_literal']['rows_returned_mean']}  "
                      f"subq recall={r[f'approx_depth{k}_subquery']['recall_vs_db_exact_mean']} "
                      f"rows={r[f'approx_depth{k}_subquery']['rows_returned_mean']}", flush=True)
        finally:
            ibm_db.close(conn)
        result["where_db2inst1_no_rcac"] = res

    elif args.phase == "rcac":
        res = {}
        for user, m in SWEEP_USERS:
            truth_np = exact_truth(pts, bucket, queries, m, k)
            conn = connect(user, user_password(user))
            try:
                router = Router(SYN_TABLE, cfg=cfg)
                strat = router.strategy(conn, k)
                ex = timed_query(conn, knn_sql(SYN_TABLE, k, False), two, qtexts, k)
                truth_db = [set(ids) for ids, _, _ in ex]
                agree = statistics.fmean(len(a & b) / k for a, b in zip(truth_db, truth_np))
                r = {"strategy": strat.as_dict(), "db_exact_vs_numpy_agreement": round(agree, 4),
                     "exact": summarize(ex, None, truth_np, k)}
                for n in depths:
                    r[f"approx_depth{n}"] = summarize(
                        timed_query(conn, knn_sql(SYN_TABLE, n, True), two, qtexts, k), truth_db, truth_np, k)
                r["router"] = summarize(
                    timed_query(conn, knn_sql(SYN_TABLE, strat.depth, strat.mode == "APPROX",
                                              sls=strat.search_list_size), two, qtexts, k),
                    truth_db, truth_np, k)
                res[user] = r
                print(f"[rcac] {user:10s} visible={strat.visible_rows}/{strat.total_rows} "
                      f"exact ms={r['exact']['latency_ms_median']} agree_np={r['db_exact_vs_numpy_agreement']}  "
                      f"approx{k} recall={r[f'approx_depth{k}']['recall_vs_db_exact_mean']} "
                      f"rows={r[f'approx_depth{k}']['rows_returned_mean']} "
                      f"lt_k={r[f'approx_depth{k}']['queries_with_fewer_than_k_rows']}  "
                      f"router={strat.mode}/{strat.depth} recall={r['router']['recall_vs_db_exact_mean']} "
                      f"ms={r['router']['latency_ms_median']}", flush=True)
            finally:
                ibm_db.close(conn)
        result["rcac"] = res
    out_path.write_text(json.dumps(result, indent=1))
    print("wrote", out_path)


# ============================================================================= REAL DATA (NEEDLE.ADV_DOC)
REAL_TABLE = "NEEDLE.ADV_DOC"
REAL_USERS = [("NDL_P10", 10), ("NDL_P25", 25), ("NDL_P50", 50), ("NDL_P75", 75), ("NDL_SENIOR", 100)]
REAL_DEPTHS = [10, 25, 50, 100, 200]
NOT_EMBARGOED = "(EMBARGO_UNTIL IS NULL OR EMBARGO_UNTIL <= CURRENT TIMESTAMP)"


def rsql(n: int, approx: bool, where: str = "", sls: int | None = None) -> str:
    """Real-data k-NN statement (same text shape as src/needle/rcac.knn_sql)."""
    g = (f" /* <OPTGUIDELINES><IXSCAN TABLE='T' SEARCH_LIST_SIZE='{int(sls)}'/></OPTGUIDELINES> */"
         if sls and approx else "")
    w = f"WHERE {where} " if where else ""
    qv = f"VECTOR(CAST(? AS CLOB(100K)), {DIM}, FLOAT32)"
    return (f"SELECT ADV_ID, VECTOR_DISTANCE(EMB, {qv}, COSINE) AS DIST FROM {REAL_TABLE} T {w}"
            f"ORDER BY VECTOR_DISTANCE(EMB, {qv}, COSINE) "
            f"FETCH {'APPROX' if approx else 'EXACT'} FIRST {int(n)} ROWS ONLY{g}")


def load_real_queries() -> list[dict]:
    return json.loads((HERE / "rcac_queries.json").read_text())


def run_cond(conn, sql: str, qs: list[dict], k: int, warmup: int = 2, pf=None) -> list[dict]:
    """Execute one fixed statement for every query (prepared once). Ties broken by (distance, id).
    `pf(q)` returns the bound parameters (default: the query vector twice)."""
    pf = pf or (lambda q: (q["vt"], q["vt"]))
    stmt = ibm_db.prepare(conn, sql)
    for q in qs[:warmup]:
        ibm_db.execute(stmt, pf(q))
        while ibm_db.fetch_tuple(stmt):
            pass
    out = []
    for q in qs:
        t0 = time.perf_counter()
        res, err = [], None
        try:
            ibm_db.execute(stmt, pf(q))
            r = ibm_db.fetch_tuple(stmt)
            while r:
                res.append((str(r[0]).strip(), float(r[1])))
                r = ibm_db.fetch_tuple(stmt)
        except Exception as e:  # noqa: BLE001  e.g. SQL0901N "Fetched nodes unexpectedly unsorted" (Db2 defect)
            m = re.search(r"SQL\d{4,5}[NWC]", str(e))
            err = m.group(0) if m else str(e)[:80]
            stmt = ibm_db.prepare(conn, sql)  # statement handle may be unusable after a severe error
        ms = (time.perf_counter() - t0) * 1000.0
        res.sort(key=lambda x: (x[1], x[0]))
        out.append({"ids": [x[0] for x in res[:k]], "n_ret": len(res), "ms": ms, "error": err})
    ibm_db.free_stmt(stmt)
    return out


def plan_info(conn, sql: str, params: tuple) -> dict:
    """EXPLAIN PLAN as the admin connection; read operators, DiskANN SRCHLSIZ, IXSCAN row estimate, filter factors."""
    st = ibm_db.prepare(conn, "EXPLAIN PLAN FOR " + sql)
    ibm_db.execute(st, params)
    t = rows(conn, "SELECT MAX(EXPLAIN_TIME) FROM DB2INST1.EXPLAIN_INSTANCE")[0][0]
    ops = rows(conn, "SELECT OPERATOR_ID, RTRIM(OPERATOR_TYPE), TOTAL_COST FROM DB2INST1.EXPLAIN_OPERATOR "
                     "WHERE EXPLAIN_TIME = ? ORDER BY OPERATOR_ID", (t,))
    objs = rows(conn, "SELECT DISTINCT S.TARGET_ID, RTRIM(S.OBJECT_SCHEMA) || '.' || RTRIM(S.OBJECT_NAME) "
                      "FROM DB2INST1.EXPLAIN_STREAM S WHERE S.EXPLAIN_TIME = ? AND S.OBJECT_NAME IS NOT NULL", (t,))
    args_ = rows(conn, "SELECT OPERATOR_ID, RTRIM(ARGUMENT_TYPE), RTRIM(ARGUMENT_VALUE) FROM DB2INST1.EXPLAIN_ARGUMENT "
                       "WHERE EXPLAIN_TIME = ? AND ARGUMENT_TYPE IN ('SRCHLSIZ', 'BEAMWDTH')", (t,))
    preds = rows(conn, "SELECT OPERATOR_ID, FILTER_FACTOR, VARCHAR(SUBSTR(PREDICATE_TEXT, 1, 200), 200) "
                       "FROM DB2INST1.EXPLAIN_PREDICATE WHERE EXPLAIN_TIME = ? ORDER BY OPERATOR_ID", (t,))
    obj_by_op = {}
    for op_id, name in objs:
        obj_by_op.setdefault(op_id, []).append(name)
    vix_ops = [op for op, typ, _ in ops if typ == "IXSCAN" and any(n.endswith("_VIX") for n in obj_by_op.get(op, []))]
    ix_rows = None
    if vix_ops:
        r = rows(conn, "SELECT STREAM_COUNT FROM DB2INST1.EXPLAIN_STREAM WHERE EXPLAIN_TIME = ? AND SOURCE_TYPE = 'O' "
                       "AND SOURCE_ID = ?", (t, vix_ops[0]))
        ix_rows = float(r[0][0]) if r else None
    return {
        "operators": [f"{op}:{typ}" for op, typ, _ in ops],
        "total_cost": round(float(ops[0][2]), 1) if ops else None,
        "uses_vector_index": bool(vix_ops),
        "srchlsiz": next((int(v) for _, a, v in args_ if a == "SRCHLSIZ"), None),
        "beamwdth": next((int(v) for _, a, v in args_ if a == "BEAMWDTH"), None),
        "vector_ixscan_est_rows": ix_rows,
        "predicates": [{"op": op, "ff": float(ff), "text": txt.strip()} for op, ff, txt in preds],
    }


def summarize_real(per_q: list[dict], qs: list[dict], truth: list[list[str]] | None, k: int,
                   allowed=None) -> dict:
    """Recall vs the caller's own EXACT top-k (|A & G| / |G|, under-filled answers count as misses)."""
    def agg(idx):
        if not idx:
            return {}
        d = {"n": len(idx),
             "errors": sum(1 for i in idx if per_q[i].get("error")),
             "returned_mean": round(statistics.fmean(per_q[i]["n_ret"] for i in idx), 2),
             "underfill_rate": round(sum(1 for i in idx if len(per_q[i]["ids"]) < k) / len(idx), 4),
             "p50_ms": round(statistics.median(per_q[i]["ms"] for i in idx), 2),
             "p95_ms": round(float(np.percentile([per_q[i]["ms"] for i in idx], 95)), 2)}
        if truth is not None:
            rec = [len(set(per_q[i]["ids"]) & set(truth[i])) / max(len(truth[i]), 1) for i in idx]
            d["recall_mean"] = round(statistics.fmean(rec), 4)
            d["recall_min"] = round(min(rec), 4)
        return d
    all_i = list(range(len(qs)))
    out = {"all": agg(all_i),
           "dev": agg([i for i in all_i if qs[i]["split"] == "dev"]),
           "heldout": agg([i for i in all_i if qs[i]["split"] == "heldout"]),
           "g1": agg([i for i in all_i if qs[i]["qid"].startswith("g1:")])}
    if allowed is not None:
        out["leaked_ids"] = sorted({x for q in per_q for x in q["ids"] if not allowed(x)})
    out["per_query"] = [{"n_ret": q["n_ret"], "ms": round(q["ms"], 2), "error": q.get("error"),
                         "recall": (round(len(set(q["ids"]) & set(truth[i])) / max(len(truth[i]), 1), 3)
                                    if truth is not None else None)} for i, q in enumerate(per_q)]
    return out


def real_acl_map(conn) -> dict:
    return {str(a).strip(): (int(b), int(e)) for a, b, e in rows(conn,
            "SELECT ADV_ID, ROW_BUCKET, CASE WHEN EMBARGO_UNTIL > CURRENT TIMESTAMP THEN 1 ELSE 0 END "
            f"FROM {REAL_TABLE}")}


def cmd_real(args) -> None:
    k = int(args.k)
    qs = load_real_queries()
    if args.nq:
        qs = qs[: args.nq]
    for q in qs:
        q["vt"] = "[" + ",".join(repr(float(x)) for x in q["vec"]) + "]"
    out_path = HERE / args.out
    result = json.loads(out_path.read_text()) if out_path.exists() else {}
    two = lambda q: (q, q)  # noqa: E731
    admin = connect()
    try:
        meta = result.setdefault("meta", {})
        meta.update({"table": REAL_TABLE, "k": k, "n_queries": len(qs),
                     "n_dev": sum(1 for q in qs if q["split"] == "dev"),
                     "n_heldout": sum(1 for q in qs if q["split"] == "heldout"),
                     "db2": rows(admin, "SELECT SERVICE_LEVEL FROM SYSIBMADM.ENV_INST_INFO")[0][0],
                     "stats": [list(map(str, r)) for r in rows(admin,
                               "SELECT TABNAME, CARD, STATS_TIME FROM SYSCAT.TABLES WHERE TABSCHEMA='NEEDLE' "
                               "AND TABNAME IN ('ADV_DOC','USER_ACCESS')")],
                     "auto_runstats": rows(admin, "SELECT VALUE FROM SYSIBMADM.DBCFG WHERE NAME='auto_runstats'")[0][0],
                     "control": rows(admin, "SELECT CONTROL FROM SYSCAT.TABLES WHERE TABSCHEMA='NEEDLE' "
                                            "AND TABNAME='ADV_DOC'")[0][0]})
        acl = real_acl_map(admin)

        if args.phase == "baseline":
            # Plain WHERE ROW_BUCKET < p as DB2INST1 BEFORE row access control is active (mechanism control).
            if meta["control"].strip():
                raise SystemExit("baseline must run before RCAC is activated on NEEDLE.ADV_DOC")
            res = {}
            for _, p in REAL_USERS:
                where = f"ROW_BUCKET < {int(p)}" if p < 100 else ""
                ex = run_cond(admin, rsql(k, False, where), qs, k)
                truth = [q["ids"] for q in ex]
                r = {"exact": summarize_real(ex, qs, truth, k) | {"plan": plan_info(admin, rsql(k, False, where),
                                                                                    (qs[0]["vt"],) * 2)}}
                for n in REAL_DEPTHS:
                    sql = rsql(n, True, where)
                    r[f"approx{n}"] = summarize_real(run_cond(admin, sql, qs, k), qs, truth, k) | {
                        "plan": plan_info(admin, sql, (qs[0]["vt"],) * 2)}
                if p < 100:
                    # Same filter, value hidden in a subquery with a bound AUTHID (what the permission looks like).
                    user = next(u for u, pp in REAL_USERS if pp == p)
                    subq = ("ROW_BUCKET < (SELECT UA.MAX_BUCKET FROM NEEDLE.USER_ACCESS UA "
                            "WHERE UA.AUTHID = CAST(? AS VARCHAR(128)))")
                    for n in (10, 100):
                        sql = rsql(n, True, subq)
                        pf = (lambda q, u=user: (q["vt"], u, q["vt"]))
                        r[f"approx{n}_subquery"] = summarize_real(run_cond(admin, sql, qs, k, pf=pf), qs, truth, k) | {
                            "plan": plan_info(admin, sql, (qs[0]["vt"], user, qs[0]["vt"]))}
                res[f"{p}"] = r
                a10 = r["approx10"]
                print(f"[baseline WHERE] p={p:3d} exact p50={r['exact']['all']['p50_ms']}ms  approx10 recall="
                      f"{a10['all']['recall_mean']} returned={a10['all']['returned_mean']} underfill="
                      f"{a10['all']['underfill_rate']} L={a10['plan']['srchlsiz']} ixrows="
                      f"{a10['plan']['vector_ixscan_est_rows']} index={a10['plan']['uses_vector_index']}"
                      + (f" | subquery approx10 recall={r['approx10_subquery']['all']['recall_mean']} returned="
                         f"{r['approx10_subquery']['all']['returned_mean']} ixrows="
                         f"{r['approx10_subquery']['plan']['vector_ixscan_est_rows']}" if p < 100 else ""),
                      flush=True)
            result["baseline_where_no_rcac"] = res

        elif args.phase == "rcac":
            if meta["control"].strip() == "":
                raise SystemExit("row access control is not active on NEEDLE.ADV_DOC")
            plans = {}
            for n in REAL_DEPTHS:  # plan shape under RCAC, explained by DB2INST1 (same SQL text every user runs)
                plans[f"approx{n}"] = plan_info(admin, rsql(n, True), (qs[0]["vt"],) * 2)
                plans[f"approx{n}_L{max(50, 3 * n)}"] = plan_info(admin, rsql(n, True, sls=max(50, 3 * n)),
                                                                  (qs[0]["vt"],) * 2)
            plans["approx10_L200"] = plan_info(admin, rsql(10, True, sls=200), (qs[0]["vt"],) * 2)
            plans["exact"] = plan_info(admin, rsql(k, False), (qs[0]["vt"],) * 2)
            res = {"plans_as_db2inst1": plans}
            order = REAL_USERS if not args.reverse else list(reversed(REAL_USERS))
            for user, p in order:
                sees = 1 if user == "NDL_SENIOR" else 0
                allowed = (lambda x, p=p, sees=sees: x in acl and acl[x][0] < p and (sees or acl[x][1] == 0))
                conn = connect(user, user_password(user))
                try:
                    who = rows(conn, "SELECT SESSION_USER, CURRENT USER FROM SYSIBM.SYSDUMMY1")[0]
                    visible = rows(conn, f"SELECT COUNT(*) FROM {REAL_TABLE}")[0][0]
                    ex = run_cond(conn, rsql(k, False), qs, k)
                    truth = [q["ids"] for q in ex]
                    # Oracle check: the caller's EXACT equals DB2INST1's EXACT with the permission written as WHERE.
                    w = f"ROW_BUCKET < {int(p)}" + ("" if sees else f" AND {NOT_EMBARGOED}")
                    adm = run_cond(admin, rsql(k, False, w), qs, k)
                    oracle_equal = sum(1 for a, b in zip(ex, adm) if set(a["ids"]) == set(b["ids"]))
                    r = {"session_user": [str(x).strip() for x in who], "visible_rows": int(visible),
                         "visible_fraction": round(int(visible) / len(acl), 4),
                         "oracle_equal_queries": oracle_equal, "exact": summarize_real(ex, qs, truth, k, allowed)}
                    for n in REAL_DEPTHS:
                        r[f"approx{n}"] = summarize_real(run_cond(conn, rsql(n, True), qs, k), qs, truth, k, allowed)
                        L = max(50, 3 * n)
                        r[f"approx{n}_L{L}"] = summarize_real(run_cond(conn, rsql(n, True, sls=L), qs, k),
                                                              qs, truth, k, allowed)
                    r["approx10_L200"] = summarize_real(run_cond(conn, rsql(10, True, sls=200), qs, k),
                                                        qs, truth, k, allowed)
                    res[user] = r
                    a = r["approx10"]["all"]
                    print(f"[rcac] {user:10s} session={r['session_user']} visible={visible} "
                          f"oracle_equal={oracle_equal}/{len(qs)} exact p50={r['exact']['all']['p50_ms']}ms | "
                          f"approx10 recall={a['recall_mean']} returned={a['returned_mean']} underfill="
                          f"{a['underfill_rate']} | approx100 recall={r['approx100']['all']['recall_mean']} "
                          f"underfill={r['approx100']['all']['underfill_rate']} | L200 recall="
                          f"{r['approx10_L200']['all']['recall_mean']} returned="
                          f"{r['approx10_L200']['all']['returned_mean']} | leaks="
                          f"{sum(len(v.get('leaked_ids', [])) for v in r.values() if isinstance(v, dict))}",
                          flush=True)
                finally:
                    ibm_db.close(conn)
            result["rcac" + ("_reverse" if args.reverse else "")] = res

        elif args.phase == "router":
            sys.path.insert(0, str(HERE))
            sys.path.insert(0, str(HERE.parent / "src"))
            try:
                from needle.rcac import Router, RouterConfig
            except ImportError:
                from rcac import Router, RouterConfig
            cfg = RouterConfig(exact_max_rows=args.T, overfetch=args.m)
            held = [q for q in qs if q["split"] == "heldout"]
            res = {"config": {"T": args.T, "m": args.m, "depths": list(cfg.depths), "guideline": cfg.use_guideline,
                              "fitted_on": "dev split only (see router_fit)", "evaluated_on": "heldout split"}}
            for user, p in REAL_USERS:
                sees = 1 if user == "NDL_SENIOR" else 0
                allowed = (lambda x, p=p, sees=sees: x in acl and acl[x][0] < p and (sees or acl[x][1] == 0))
                conn = connect(user, user_password(user))
                try:
                    router = Router(REAL_TABLE, id_col="ADV_ID")
                    router.cfg = cfg
                    s = router.strategy(conn, k)
                    truth = [q["ids"] for q in run_cond(conn, rsql(k, False), held, k)]
                    for q in held[:2]:
                        router.search(conn, q["vt"], k, s)  # warm-up
                    per_q, fb = [], 0
                    for q in held:
                        o = router.search(conn, q["vt"], k, s)
                        fb += o["fallback"]
                        per_q.append({"ids": [str(x[0]).strip() for x in o["rows"]],
                                      "n_ret": len(o["rows"]), "ms": o["ms"], "error": o["error"],
                                      "approx_returned": o["returned_by_approx"]})
                    summ = summarize_real(per_q, held, truth, k, allowed)
                    res[user] = {"strategy": s.as_dict(), "fallbacks": fb, "sql": router.sql_for(s), **summ}
                    print(f"[router] {user:10s} {s.mode}/{s.depth} L={s.search_list_size} recall="
                          f"{summ['all']['recall_mean']} underfill={summ['all']['underfill_rate']} fallbacks={fb} "
                          f"p50={summ['all']['p50_ms']}ms leaks={len(summ['leaked_ids'])}", flush=True)
                finally:
                    ibm_db.close(conn)
            result["router_heldout"] = res
    finally:
        ibm_db.close(admin)
    out_path.write_text(json.dumps(result, indent=1, default=str))
    print("wrote", out_path)


def cmd_plancache(args) -> None:
    """Plan-sharing evidence: flush the dynamic package cache, run ONE fixed statement as each user (both orders),
    read MON_GET_PKG_CACHE_STMT after each user, and format the executed section with EXPLAIN_FROM_SECTION."""
    import subprocess

    qs = load_real_queries()[: args.nq]
    for q in qs:
        q["vt"] = "[" + ",".join(repr(float(x)) for x in q["vec"]) + "]"
    sql = rsql(10, True)
    admin = connect()
    report = {"statement": sql, "runs": []}
    mon = ("SELECT HEX(EXECUTABLE_ID), NUM_EXECUTIONS, ROWS_READ, ROWS_RETURNED, STMT_EXEC_TIME, "
           "VARCHAR(SUBSTR(STMT_TEXT, 1, 60), 60) FROM TABLE(MON_GET_PKG_CACHE_STMT('D', NULL, NULL, -2)) AS T "
           "WHERE STMT_TEXT LIKE 'SELECT ADV_ID, VECTOR_DISTANCE(EMB%FETCH APPROX FIRST 10 ROWS ONLY'")
    try:
        for order_name, order in (("forward", REAL_USERS), ("reverse", list(reversed(REAL_USERS)))):
            execute(admin, "FLUSH PACKAGE CACHE DYNAMIC")
            run = {"order": order_name, "steps": []}
            prev = {}
            for user, _ in order:
                conn = connect(user, user_password(user))
                try:
                    st = ibm_db.prepare(conn, sql)
                    nret = []
                    for q in qs:
                        ibm_db.execute(st, (q["vt"], q["vt"]))
                        c = 0
                        while ibm_db.fetch_tuple(st):
                            c += 1
                        nret.append(c)
                    ibm_db.free_stmt(st)
                finally:
                    ibm_db.close(conn)
                cur = {r[0]: r for r in rows(admin, mon)}
                step = {"user": user, "rows_returned_per_query": nret, "cache_entries": []}
                for eid, r in cur.items():
                    p = prev.get(eid, (eid, 0, 0, 0, 0, ""))
                    step["cache_entries"].append({
                        "executable_id": eid, "num_executions": int(r[1]), "delta_executions": int(r[1]) - int(p[1]),
                        "delta_rows_read": int(r[2]) - int(p[2]), "delta_rows_returned": int(r[3]) - int(p[3]),
                        "delta_stmt_exec_time_ms": int(r[4]) - int(p[4])})
                prev = cur
                run["steps"].append(step)
                print(f"[plancache {order_name}] after {user}: {len(cur)} cache entr(y/ies): " + "; ".join(
                    f"{e['executable_id'][-16:]} execs={e['num_executions']} (+{e['delta_executions']}) "
                    f"+rows_read={e['delta_rows_read']} +rows_returned={e['delta_rows_returned']}"
                    for e in step["cache_entries"]), flush=True)
            run["distinct_executable_ids"] = sorted(prev.keys())
            report["runs"].append(run)
            for i, eid in enumerate(sorted(prev.keys())):
                outf = HERE / "ev" / f"section_{order_name}_{i}.txt"
                cmd = (f"db2 connect to VECDB >/dev/null && db2 \"CALL EXPLAIN_FROM_SECTION(x'{eid}', 'M', NULL, -1, "
                       f"'DB2INST1', ?, ?, ?, ?, ?)\" && db2exfmt -d VECDB -1 -t; db2 connect reset >/dev/null")
                if not re.fullmatch(r"[0-9A-F]+", eid):
                    raise SystemExit("unexpected executable id")
                txt = subprocess.run(["docker", "exec", "db2", "su", "-", "db2inst1", "-c", cmd],
                                     capture_output=True, text=True).stdout
                outf.write_text(txt)
                print(f"   EXPLAIN_FROM_SECTION -> {outf} ({len(txt)} chars)")
    finally:
        ibm_db.close(admin)
    (HERE / args.out).write_text(json.dumps(report, indent=1))
    print("wrote", HERE / args.out)


def triage_fused_sql(k: int, depth: int) -> str:
    """The HYBRID statement NEEDLE.TRIAGE_MODE prepares (sql/03_triage_proc.sql), rebuilt for EXPLAIN."""
    k, depth = int(k), int(depth)
    vec0 = ("SELECT ADV_ID, DOUBLE(VECTOR_DISTANCE(EMB, VECTOR(CAST(? AS CLOB(100K)), 768, FLOAT32), COSINE)) "
            "FROM NEEDLE.ADV_DOC ORDER BY VECTOR_DISTANCE(EMB, VECTOR(CAST(? AS CLOB(100K)), 768, FLOAT32), COSINE) "
            f"FETCH APPROX FIRST {depth} ROWS ONLY")
    kw = f"SELECT B.ADV_ID, B.KW_RANK FROM TABLE(NEEDLE.BM25_SEARCH(CAST(? AS CLOB(32K)), {depth})) AS B"
    return (f"WITH VEC0 (ADV_ID, VEC_DIST) AS ({vec0}), KW (ADV_ID, KW_RANK) AS ({kw}), "
            "VEC (ADV_ID, VEC_DIST, VEC_RANK) AS (  SELECT ADV_ID, VEC_DIST, RANK() OVER (ORDER BY VEC_DIST, ADV_ID) "
            "FROM VEC0), F (ADV_ID, RRF, KW_RANK, VEC_RANK, VEC_DIST) AS (  SELECT COALESCE(K.ADV_ID, V.ADV_ID), "
            "COALESCE(1E0 / (60 + K.KW_RANK), 0E0) + COALESCE(1E0 / (60 + V.VEC_RANK), 0E0), K.KW_RANK, V.VEC_RANK, "
            "V.VEC_DIST   FROM KW K FULL OUTER JOIN VEC V ON K.ADV_ID = V.ADV_ID) SELECT ADV_ID, RRF, "
            "INTEGER(KW_RANK) AS KW_RANK, INTEGER(VEC_RANK) AS VEC_RANK, VEC_DIST FROM F ORDER BY RRF DESC, ADV_ID "
            f"FETCH FIRST {k} ROWS ONLY")


def cmd_triage(args) -> None:
    """TRIAGE under RCAC: EXPLAIN the fused HYBRID statement (as DB2INST1) and count the vector-leg rows each user gets
    from CALL NEEDLE.TRIAGE_MODE(qvec, '[]', 10, depth, 'VEC') at depth 10 and at depth 100."""
    qs = [q for q in load_real_queries() if q["qid"].startswith("g1:")]
    for q in qs:
        q["vt"] = "[" + ",".join(repr(float(x)) for x in q["vec"]) + "]"
    admin = connect()
    out = {"plans_as_db2inst1": {}, "users": {}}
    try:
        for d in (10, 100):
            out["plans_as_db2inst1"][f"hybrid_depth{d}"] = plan_info(
                admin, triage_fused_sql(10, d), (qs[0]["vt"], qs[0]["vt"], json.dumps(["yaml", "loader"])))
            p = out["plans_as_db2inst1"][f"hybrid_depth{d}"]
            print(f"[triage plan] depth={d} vector_index={p['uses_vector_index']} L={p['srchlsiz']} "
                  f"vec_ixscan_est={p['vector_ixscan_est_rows']} ops={len(p['operators'])}", flush=True)
    finally:
        ibm_db.close(admin)
    for user, _ in REAL_USERS:
        conn = connect(user, user_password(user))
        try:
            r = {}
            for d in (10, 100):
                counts = []
                for q in qs:
                    res = ibm_db.callproc(conn, "NEEDLE.TRIAGE_MODE", (q["vt"], "[]", 10, d, "VEC"))
                    st = res[0] if isinstance(res, tuple) else res
                    c = 0
                    while ibm_db.fetch_tuple(st):
                        c += 1
                    ibm_db.free_stmt(st)
                    counts.append(c)
                r[f"vec_depth{d}"] = {"rows_mean": round(statistics.fmean(counts), 2),
                                      "underfill": sum(1 for c in counts if c < 10), "n": len(counts),
                                      "rows": counts}
            out["users"][user] = r
            print(f"[triage VEC k=10] {user:10s} depth10 rows={r['vec_depth10']['rows_mean']} "
                  f"(<10: {r['vec_depth10']['underfill']}/{len(qs)})  depth100 rows={r['vec_depth100']['rows_mean']} "
                  f"(<10: {r['vec_depth100']['underfill']}/{len(qs)})", flush=True)
        finally:
            ibm_db.close(conn)
    (HERE / args.out).write_text(json.dumps(out, indent=1))
    print("wrote", HERE / args.out)


def cmd_ffsource(args) -> None:
    """Where does the permission's filter factor 0.495 come from? Change the sweep users' MAX_BUCKET values,
    RUNSTATS USER_ACCESS, re-EXPLAIN the RCAC APPROX 10 statement, then restore and re-check."""
    qs = load_real_queries()[:1]
    vt = "[" + ",".join(repr(float(x)) for x in qs[0]["vec"]) + "]"
    admin = connect()
    out = {"steps": []}
    original = {"NDL_P10": 10, "NDL_P25": 25, "NDL_P50": 50, "NDL_P75": 75}
    runstats = ("CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE NEEDLE.USER_ACCESS WITH DISTRIBUTION AND INDEXES ALL')")

    def snap(label):
        p = plan_info(admin, rsql(10, True), (vt, vt))
        ua = rows(admin, "SELECT AUTHID, MAX_BUCKET FROM NEEDLE.USER_ACCESS ORDER BY AUTHID")
        st = rows(admin, "SELECT STATS_TIME FROM SYSCAT.TABLES WHERE TABSCHEMA='NEEDLE' AND TABNAME='USER_ACCESS'")
        colstats = rows(admin, "SELECT COLNAME, COLCARD, VARCHAR(LOW2KEY, 40), VARCHAR(HIGH2KEY, 40) FROM SYSCAT.COLUMNS "
                               "WHERE TABSCHEMA='NEEDLE' AND TABNAME IN ('USER_ACCESS') AND COLNAME='MAX_BUCKET'")
        step = {"label": label, "user_access": [[str(a).strip(), int(b)] for a, b in ua],
                "user_access_stats_time": str(st[0][0]), "max_bucket_colstats": [list(map(str, c)) for c in colstats],
                "permission_ff": sorted({x["ff"] for x in p["predicates"] if "MAX_BUCKET" in x["text"]}),
                "vector_ixscan_est_rows": p["vector_ixscan_est_rows"], "srchlsiz": p["srchlsiz"],
                "uses_vector_index": p["uses_vector_index"]}
        out["steps"].append(step)
        print(f"[ffsource] {label}: MAX_BUCKET={step['user_access']} colstats={step['max_bucket_colstats']} "
              f"FF={step['permission_ff']} IXSCAN est={step['vector_ixscan_est_rows']} L={step['srchlsiz']}", flush=True)

    try:
        snap("before (P10/P25/P50/P75 = 10/25/50/75)")
        upd = ibm_db.prepare(admin, "UPDATE NEEDLE.USER_ACCESS SET MAX_BUCKET = ? WHERE AUTHID = ?")
        for a in original:
            ibm_db.execute(upd, (10, a))
        execute(admin, runstats)
        snap("changed (P10/P25/P50/P75 = 10/10/10/10) + RUNSTATS")
    finally:
        upd = ibm_db.prepare(admin, "UPDATE NEEDLE.USER_ACCESS SET MAX_BUCKET = ? WHERE AUTHID = ?")
        for a, v in original.items():
            ibm_db.execute(upd, (v, a))
        execute(admin, runstats)
        snap("restored (10/25/50/75) + RUNSTATS")
        ibm_db.close(admin)
    (HERE / args.out).write_text(json.dumps(out, indent=1))
    print("wrote", HERE / args.out)


def cmd_actuals(args) -> None:
    """Section actuals for NDL_P10: activity event monitor + WLM_SET_CONN_ENV on that one connection, run the RCAC
    APPROX 10 statement with SEARCH_LIST_SIZE 50/200/1000, then EXPLAIN_FROM_ACTIVITY and read EXPLAIN_ACTUALS."""
    import subprocess

    evm = "NDL_RCAC_ACT"
    qs = load_real_queries()[: args.nq]
    for q in qs:
        q["vt"] = "[" + ",".join(repr(float(x)) for x in q["vec"]) + "]"
    admin = connect()
    out = {"runs": []}
    try:
        execute(admin, f"CREATE EVENT MONITOR {evm} FOR ACTIVITIES WRITE TO TABLE", ignore=("SQL0601N",))
        execute(admin, f"SET EVENT MONITOR {evm} STATE 1")
        user = args.user
        conn = connect(user, user_password(user))
        try:
            h = int(rows(conn, "VALUES MON_GET_APPLICATION_HANDLE()")[0][0])
            st = ibm_db.prepare(admin, "CALL SYSPROC.WLM_SET_CONN_ENV(?, ?)")
            ibm_db.execute(st, (h, "<collectactdata>WITH DETAILS, SECTION</collectactdata>"
                                   "<collectsectionactuals>BASE</collectsectionactuals>"))
            for L in (50, 200, 1000):
                sql = rsql(10, True, sls=L)
                for q in qs:
                    r = rows(conn, sql, (q["vt"], q["vt"]))
                    out["runs"].append({"L": L, "qid": q["qid"], "rows_returned": len(r)})
        finally:
            ibm_db.close(conn)
        execute(admin, f"SET EVENT MONITOR {evm} STATE 0")  # flushes the activity records to the tables
        acts = rows(admin, f"SELECT A.APPL_ID, A.UOW_ID, A.ACTIVITY_ID, VARCHAR(SUBSTR(S.STMT_TEXT, 1, 3000), 3000) "
                           f"FROM ACTIVITY_{evm} A JOIN ACTIVITYSTMT_{evm} S ON S.APPL_ID = A.APPL_ID "
                           f"AND S.UOW_ID = A.UOW_ID AND S.ACTIVITY_ID = A.ACTIVITY_ID "
                           f"WHERE A.APPL_ID = (SELECT APPL_ID FROM ACTIVITY_{evm} WHERE AGENT_ID = ? "
                           f"FETCH FIRST 1 ROW ONLY) AND S.STMT_TEXT LIKE 'SELECT ADV_ID, VECTOR_DISTANCE%' "
                           f"ORDER BY A.UOW_ID, A.ACTIVITY_ID", (h,))
        print(f"[actuals] captured {len(acts)} activities for {user} (application handle {h})", flush=True)
        for i, (appl, uow, act, text) in enumerate(acts):
            m = re.search(r"SEARCH_LIST_SIZE='(\d+)'", text)
            L = int(m.group(1)) if m else None
            if not re.fullmatch(r"[A-Za-z0-9.*_:-]+", str(appl).strip()):
                raise SystemExit(f"unexpected APPL_ID {str(appl)!r}")
            cmd = (f"db2 connect to VECDB >/dev/null && db2 \"CALL EXPLAIN_FROM_ACTIVITY('{str(appl).strip()}', "
                   f"{int(uow)}, {int(act)}, '{evm}', 'DB2INST1', ?, ?, ?, ?, ?)\" && db2exfmt -d VECDB -1 -t; "
                   f"db2 connect reset >/dev/null")
            txt = subprocess.run(["docker", "exec", "db2", "su", "-", "db2inst1", "-c", cmd],
                                 capture_output=True, text=True).stdout
            (HERE / "ev" / f"actuals_{user}_L{L}_{i}.txt").write_text(txt)
            t = rows(admin, "SELECT MAX(EXPLAIN_TIME) FROM DB2INST1.EXPLAIN_INSTANCE")[0][0]
            act_rows = rows(admin, "SELECT O.OPERATOR_ID, RTRIM(O.OPERATOR_TYPE), A.ACTUAL_VALUE "
                                   "FROM DB2INST1.EXPLAIN_ACTUALS A JOIN DB2INST1.EXPLAIN_OPERATOR O "
                                   "ON O.EXPLAIN_TIME = A.EXPLAIN_TIME AND O.OPERATOR_ID = A.OPERATOR_ID "
                                   "WHERE A.EXPLAIN_TIME = ? AND A.PREDICATE_ID IS NULL "
                                   "AND UPPER(A.ACTUAL_TYPE) = 'CARDINALITY' ORDER BY O.OPERATOR_ID", (t,))
            srch = rows(admin, "SELECT RTRIM(ARGUMENT_VALUE) FROM DB2INST1.EXPLAIN_ARGUMENT WHERE EXPLAIN_TIME = ? "
                               "AND ARGUMENT_TYPE = 'SRCHLSIZ'", (t,))
            ests = rows(admin, "SELECT S.SOURCE_ID, S.STREAM_COUNT FROM DB2INST1.EXPLAIN_STREAM S "
                               "WHERE S.EXPLAIN_TIME = ? AND S.SOURCE_TYPE = 'O'", (t,))
            rec = {"L_guideline": L, "srchlsiz": srch[0][0] if srch else None,
                   "actual_rows_by_operator": [[int(o), typ, float(v)] for o, typ, v in act_rows],
                   "estimated_rows_by_operator": {int(o): float(c) for o, c in ests},
                   "file": f"ev/actuals_{user}_L{L}_{i}.txt"}
            out.setdefault("activities", []).append(rec)
            print(f"[actuals] L={L} SRCHLSIZ={rec['srchlsiz']} actual rows per operator: "
                  f"{rec['actual_rows_by_operator']}", flush=True)
    finally:
        ibm_db.close(admin)
    (HERE / args.out).write_text(json.dumps(out, indent=1))
    print("wrote", HERE / args.out)


LIT = "NDL_DEV_RCAC.ADV_LIT"
LIT_PERMS = {
    # B: RCAC with a pure literal permission (applies to every user)
    "B_literal": [("ADV_LIT_B", "ROW_BUCKET < 10")],
    # A: per-user literal permission + a separate admin permission (permissions are OR'ed)
    "A_sessionuser_literal": [("ADV_LIT_A", "SESSION_USER = 'NDL_P10' AND ROW_BUCKET < 10"),
                              ("ADV_LIT_ADMIN", "SESSION_USER = 'DB2INST1'")],
}


def lit_sql(n: int, approx: bool) -> str:
    return rsql(n, approx).replace(f"FROM {REAL_TABLE} T", f"FROM {LIT} T")


def cmd_litcopy(args) -> None:
    """Causal control on a COPY of ADV_DOC: RCAC on, same 10 % authorized set for NDL_P10, permission written with a
    LITERAL threshold instead of the USER_ACCESS subquery. The frozen NEEDLE.ADV_DOC is only read."""
    admin = connect()
    out_path = HERE / args.out
    result = json.loads(out_path.read_text()) if out_path.exists() else {}
    try:
        if args.phase == "build":
            execute(admin, f"DROP TABLE {LIT}", ignore=("SQL0204N",))
            execute(admin, f"CREATE TABLE {LIT} (ADV_ID VARCHAR(64) NOT NULL PRIMARY KEY, "
                           f"ROW_BUCKET SMALLINT NOT NULL, EMB VECTOR({DIM}, FLOAT32) NOT NULL)")
            for lo in range(0, 100, 10):  # committed batches (autocommit), about 2,600 rows each
                execute(admin, f"INSERT INTO {LIT} SELECT ADV_ID, ROW_BUCKET, EMB FROM {REAL_TABLE} "
                               f"WHERE ROW_BUCKET BETWEEN {int(lo)} AND {int(lo) + 9}")
            n = rows(admin, f"SELECT COUNT(*) FROM {LIT}")[0][0]
            t0 = time.time()
            execute(admin, f"CREATE VECTOR INDEX {SYN_SCHEMA}.ADV_LIT_VIX ON {LIT} (EMB) WITH DISTANCE COSINE")
            execute(admin, f"CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE {LIT} WITH DISTRIBUTION AND INDEXES ALL')")
            execute(admin, f"GRANT SELECT ON {LIT} TO USER NDL_P10")
            result["build"] = {"rows": int(n), "index_build_s": round(time.time() - t0, 1)}
            print(f"[litcopy] built {LIT}: {n} rows, index+runstats {time.time() - t0:.1f}s", flush=True)
        elif args.phase == "measure":
            v = args.variant
            for ctl in rows(admin, f"SELECT CONTROLNAME FROM SYSCAT.CONTROLS WHERE TABSCHEMA = '{SYN_SCHEMA}' "
                                   "AND TABNAME = 'ADV_LIT' AND CONTROLNAME NOT LIKE 'SYS_DEFAULT%'"):
                execute(admin, f"DROP PERMISSION {SYN_SCHEMA}.{str(ctl[0]).strip()}")
            for name, pred in LIT_PERMS[v]:
                execute(admin, f"CREATE PERMISSION {SYN_SCHEMA}.{name} ON {LIT} FOR ROWS WHERE {pred} "
                               "ENFORCED FOR ALL ACCESS ENABLE")
            execute(admin, f"ALTER TABLE {LIT} ACTIVATE ROW ACCESS CONTROL")
            qs = load_real_queries()
            for q in qs:
                q["vt"] = "[" + ",".join(repr(float(x)) for x in q["vec"]) + "]"
            plans = {f"approx{n}": plan_info(admin, lit_sql(n, True), (qs[0]["vt"],) * 2) for n in (10, 25, 50)}
            plans["exact"] = plan_info(admin, lit_sql(10, False), (qs[0]["vt"],) * 2)
            conn = connect("NDL_P10", user_password("NDL_P10"))
            try:
                vis = rows(conn, f"SELECT COUNT(*), MAX(ROW_BUCKET) FROM {LIT}")[0]
                ex = run_cond(conn, lit_sql(10, False), qs, 10)
                truth = [q["ids"] for q in ex]
                r = {"permissions": LIT_PERMS[v], "visible_rows": int(vis[0]), "max_bucket_seen": vis[1],
                     "plans_as_db2inst1": plans, "exact": summarize_real(ex, qs, truth, 10)}
                for n in (10, 25, 50):
                    r[f"approx{n}"] = summarize_real(run_cond(conn, lit_sql(n, True), qs, 10), qs, truth, 10)
            finally:
                ibm_db.close(conn)
            result[v] = r
            a, p = r["approx10"]["all"], plans["approx10"]
            print(f"[litcopy {v}] P10 visible={vis[0]} maxbucket={vis[1]} | APPROX10 recall={a['recall_mean']} "
                  f"rows={a['returned_mean']} underfill={a['underfill_rate']} | plan index={p['uses_vector_index']} "
                  f"L={p['srchlsiz']} est={p['vector_ixscan_est_rows']} FF={[(x['ff'], x['text'][:60]) for x in p['predicates']]}"
                  f" | approx25 recall={r['approx25']['all']['recall_mean']} index={plans['approx25']['uses_vector_index']}"
                  f" | approx50 recall={r['approx50']['all']['recall_mean']} index={plans['approx50']['uses_vector_index']}",
                  flush=True)
        elif args.phase == "drop":
            execute(admin, f"DROP TABLE {LIT}", ignore=("SQL0204N",))
            print(f"[litcopy] dropped {LIT}")
    finally:
        ibm_db.close(admin)
    out_path.write_text(json.dumps(result, indent=1, default=str))
    print("wrote", out_path)


COR = "NDL_DEV_RCAC.ADV_COR"
COR_MAP = "NDL_DEV_RCAC.COR_MAP"
COR_USERS = [("NDL_P10", 10), ("NDL_P25", 25), ("NDL_P50", 50), ("NDL_SENIOR", 100)]


def cor_sql(n: int, approx: bool) -> str:
    return rsql(n, approx).replace(f"FROM {REAL_TABLE} T", f"FROM {COR} T")


def spherical_kmeans(x: np.ndarray, k: int, seed: int, iters: int = 25) -> np.ndarray:
    rng = np.random.default_rng(seed)
    c = x[rng.choice(x.shape[0], size=k, replace=False)].copy()
    lab = np.zeros(x.shape[0], dtype=np.int64)
    for _ in range(iters):
        lab = np.argmax(x @ c.T, axis=1)
        for j in range(k):
            m = x[lab == j]
            if len(m):
                v = m.sum(axis=0)
                c[j] = v / (np.linalg.norm(v) or 1.0)
    return lab


def cmd_correlated(args) -> None:
    """Correlated visibility on a COPY: COR_BUCKET from k-means clusters of the embeddings (users see whole topic
    clusters), same subquery-style permission (entitlements in NDL_DEV_RCAC.USER_ACCESS), same 170 queries."""
    sys.path.insert(0, str(HERE))
    sys.path.insert(0, str(HERE.parent / "src"))
    try:
        from needle.rcac import Router, RouterConfig
    except ImportError:
        from rcac import Router, RouterConfig
    admin = connect()
    out_path = HERE / args.out
    result = json.loads(out_path.read_text()) if out_path.exists() else {}
    try:
        if args.phase == "build":
            t0 = time.time()
            data = rows(admin, f"SELECT ADV_ID, VECTOR_SERIALIZE(EMB RETURNING CLOB(100K)) FROM {REAL_TABLE} ORDER BY ADV_ID")
            ids = [str(a).strip() for a, _ in data]
            x = np.array([json.loads(v) for _, v in data], dtype=np.float32)
            x /= np.linalg.norm(x, axis=1, keepdims=True)
            lab = spherical_kmeans(x, args.k, args.seed)
            sizes = np.bincount(lab, minlength=args.k)
            # clusters in id order; each cluster gets one bucket = cumulative share of rows before it (0..99)
            start, bucket_of = 0, {}
            for j in range(args.k):
                bucket_of[j] = min(99, int(100 * start / len(ids)))
                start += int(sizes[j])
            cb = [bucket_of[int(l)] for l in lab]
            print(f"[cor] fetched+kmeans {len(ids)} rows, k={args.k}, seed={args.seed} in {time.time() - t0:.1f}s; "
                  f"cluster sizes min/median/max = {sizes.min()}/{int(np.median(sizes))}/{sizes.max()}", flush=True)
            execute(admin, f"DROP TABLE {COR}", ignore=("SQL0204N",))
            execute(admin, f"DROP TABLE {COR_MAP}", ignore=("SQL0204N",))
            execute(admin, f"CREATE TABLE {COR_MAP} (ADV_ID VARCHAR(64) NOT NULL PRIMARY KEY, "
                           "COR_BUCKET SMALLINT NOT NULL, CLUSTER_ID SMALLINT NOT NULL)")
            ins = ibm_db.prepare(admin, f"INSERT INTO {COR_MAP} VALUES (?, ?, ?)")
            ibm_db.execute_many(ins, tuple((i, int(b), int(l)) for i, b, l in zip(ids, cb, lab)))
            execute(admin, f"CREATE TABLE {COR} (ADV_ID VARCHAR(64) NOT NULL PRIMARY KEY, "
                           f"COR_BUCKET SMALLINT NOT NULL, EMB VECTOR({DIM}, FLOAT32) NOT NULL)")
            for lo in range(0, 100, 10):  # committed batches (autocommit)
                execute(admin, f"INSERT INTO {COR} SELECT D.ADV_ID, M.COR_BUCKET, D.EMB FROM {REAL_TABLE} D "
                               f"JOIN {COR_MAP} M ON M.ADV_ID = D.ADV_ID "
                               f"WHERE M.COR_BUCKET BETWEEN {int(lo)} AND {int(lo) + 9}")
            n = rows(admin, f"SELECT COUNT(*) FROM {COR}")[0][0]
            t1 = time.time()
            execute(admin, f"CREATE VECTOR INDEX {SYN_SCHEMA}.ADV_COR_VIX ON {COR} (EMB) WITH DISTANCE COSINE")
            execute(admin, f"CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE {COR} WITH DISTRIBUTION AND INDEXES ALL')")
            execute(admin, f"""CREATE PERMISSION {SYN_SCHEMA}.ADV_COR_ROWS ON {COR}
                FOR ROWS WHERE COR_BUCKET < (SELECT UA.MAX_BUCKET FROM {SYN_ACCESS} UA WHERE UA.AUTHID = SESSION_USER)
                ENFORCED FOR ALL ACCESS ENABLE""")
            for u, _ in COR_USERS:
                execute(admin, f"GRANT SELECT ON {COR} TO USER {u}")
            execute(admin, f"ALTER TABLE {COR} ACTIVATE ROW ACCESS CONTROL")
            cover = {p: round(sum(1 for b in cb if b < p) / len(cb), 4) for p in (10, 25, 50, 100)}
            result["build"] = {"rows": int(n), "k": args.k, "seed": args.seed, "coverage_by_p": cover,
                               "cluster_size_min_median_max": [int(sizes.min()), int(np.median(sizes)),
                                                               int(sizes.max())],
                               "index_runstats_s": round(time.time() - t1, 1)}
            print(f"[cor] built {COR}: {n} rows, coverage {cover}, index+runstats {time.time() - t1:.1f}s", flush=True)
        elif args.phase == "measure":
            qs = load_real_queries()
            for q in qs:
                q["vt"] = "[" + ",".join(repr(float(x)) for x in q["vec"]) + "]"
            bmap = {str(a).strip(): int(b) for a, b in rows(admin, f"SELECT ADV_ID, COR_BUCKET FROM {COR_MAP}")}
            plans = {"approx10": plan_info(admin, cor_sql(10, True), (qs[0]["vt"],) * 2),
                     "approx50_L150": plan_info(admin, cor_sql(50, True).replace(
                         "ROWS ONLY", "ROWS ONLY /* <OPTGUIDELINES><IXSCAN TABLE='T' SEARCH_LIST_SIZE='150'/>"
                                      "</OPTGUIDELINES> */"), (qs[0]["vt"],) * 2)}
            res = {"plans_as_db2inst1": plans}
            held = [q for q in qs if q["split"] == "heldout"]
            for user, p in COR_USERS:
                allowed = (lambda x, p=p: x in bmap and bmap[x] < p)
                conn = connect(user, user_password(user))
                try:
                    visible = rows(conn, f"SELECT COUNT(*) FROM {COR}")[0][0]
                    ex = run_cond(conn, cor_sql(10, False), qs, 10)
                    truth = [q["ids"] for q in ex]
                    a10 = summarize_real(run_cond(conn, cor_sql(10, True), qs, 10), qs, truth, 10, allowed)
                    router = Router(COR, id_col="ADV_ID")
                    router.cfg = RouterConfig()  # frozen defaults fitted on the random-bucket dev split
                    s = router.strategy(conn, 10)
                    hidx = [i for i, q in enumerate(qs) if q["split"] == "heldout"]
                    per_q, fb = [], 0
                    for q in held:
                        o = router.search(conn, q["vt"], 10, s)
                        fb += o["fallback"]
                        per_q.append({"ids": [str(r[0]).strip() for r in o["rows"]], "n_ret": len(o["rows"]),
                                      "ms": o["ms"], "error": o["error"]})
                    rsum = summarize_real(per_q, held, [truth[i] for i in hidx], 10, allowed)
                    recs = [x["recall"] for x in a10["per_query"]]
                    hist = {"recall_0": sum(1 for r in recs if r == 0), "recall_0_to_0.5": sum(1 for r in recs if 0 < r < 0.5),
                            "recall_0.5_to_1": sum(1 for r in recs if 0.5 <= r < 1), "recall_1": sum(1 for r in recs if r == 1)}
                    rows_hist = {"0_rows": sum(1 for x in a10["per_query"] if x["n_ret"] == 0),
                                 "1_to_9_rows": sum(1 for x in a10["per_query"] if 0 < x["n_ret"] < 10),
                                 "10_rows": sum(1 for x in a10["per_query"] if x["n_ret"] >= 10)}
                    res[user] = {"visible_rows": int(visible), "visible_fraction": round(int(visible) / len(bmap), 4),
                                 "exact": summarize_real(ex, qs, truth, 10, allowed), "approx10": a10,
                                 "approx10_recall_histogram": hist, "approx10_rows_histogram": rows_hist,
                                 "router_strategy": s.as_dict(), "router_fallbacks": fb, "router_heldout": rsum}
                    print(f"[cor] {user:10s} visible={visible} | APPROX10 recall={a10['all']['recall_mean']} "
                          f"rows={a10['all']['returned_mean']} underfill={a10['all']['underfill_rate']} hist={hist} "
                          f"rows_hist={rows_hist} leaks={len(a10['leaked_ids'])} | router {s.mode}/{s.depth} heldout "
                          f"recall={rsum['all']['recall_mean']} underfill={rsum['all']['underfill_rate']} "
                          f"fallbacks={fb} leaks={len(rsum['leaked_ids'])} | APPROX10 heldout recall="
                          f"{a10['heldout']['recall_mean']}", flush=True)
                finally:
                    ibm_db.close(conn)
            p = plans["approx10"]
            print(f"[cor plan] approx10 index={p['uses_vector_index']} L={p['srchlsiz']} est={p['vector_ixscan_est_rows']} "
                  f"FF={[x['ff'] for x in p['predicates'] if 'COR_BUCKET' in x['text']]}", flush=True)
            result["measure"] = res
        elif args.phase == "plans":
            vt = "[" + ",".join(repr(float(x)) for x in load_real_queries()[0]["vec"]) + "]"
            pl = {}
            for n in (10, 25, 50, 100, 200):
                for L in (None, max(50, 3 * n)):
                    sql = cor_sql(n, True)
                    if L:
                        sql += f" /* <OPTGUIDELINES><IXSCAN TABLE='T' SEARCH_LIST_SIZE='{int(L)}'/></OPTGUIDELINES> */"
                    p = plan_info(admin, sql, (vt, vt))
                    key = f"approx{n}" + (f"_L{L}" if L else "")
                    pl[key] = p
                    print(f"[cor plan] {key:15s} index={p['uses_vector_index']} L={p['srchlsiz']} "
                          f"est={p['vector_ixscan_est_rows']}", flush=True)
            result["plans_by_depth"] = pl
        elif args.phase == "drop":
            execute(admin, f"DROP TABLE {COR}", ignore=("SQL0204N",))
            execute(admin, f"DROP TABLE {COR_MAP}", ignore=("SQL0204N",))
            print(f"[cor] dropped {COR} and {COR_MAP}")
    finally:
        ibm_db.close(admin)
    out_path.write_text(json.dumps(result, indent=1, default=str))
    print("wrote", out_path)


def cmd_run_as(args) -> None:
    """Run a few APPROX k-NN queries as one user (puts that user's section in the package cache)."""
    queries = np.load(HERE / "syn_queries.npy")[: args.nq]
    conn = connect(args.user, user_password(args.user))
    try:
        sql = knn_sql(SYN_TABLE, int(args.k), True, sls=args.sls)
        for q in queries:
            qt = vec_text(q)
            print(args.user, "rows returned:", len(rows(conn, sql, (qt, qt))))
    finally:
        ibm_db.close(conn)


def main() -> None:
    load_env_from_stdin()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("synth-load")
    p.add_argument("--n", type=int, default=30000)
    p.add_argument("--clusters", type=int, default=300)
    p.add_argument("--queries", type=int, default=50)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--noise", type=float, default=0.6)
    p.add_argument("--batch", type=int, default=500)
    p.add_argument("--drop", action="store_true")
    p.add_argument("--index", action="store_true")
    p = sub.add_parser("explain")
    p.add_argument("--table", default=SYN_TABLE)
    p.add_argument("--bucket", type=int, default=10)
    p.add_argument("--k", type=int, default=10)
    p.add_argument("--authid", default="NDL_P10")
    p.add_argument("--only", type=int, default=None)
    p.add_argument("--sls", type=int, default=None)
    p = sub.add_parser("synth-rcac")
    p.add_argument("mode", choices=["setup", "activate", "deactivate", "status"])
    p = sub.add_parser("sweep")
    p.add_argument("phase", choices=["where", "rcac"])
    p.add_argument("--k", type=int, default=10)
    p.add_argument("--nq", type=int, default=50)
    p.add_argument("--depths", default="10,20,50,100,200,500")
    p.add_argument("--out", default="rcac_synthetic_results.json")
    p.add_argument("--exact-max-rows", type=int, default=2000)
    p.add_argument("--exact-max-fraction", type=float, default=0.15)
    p.add_argument("--overfetch", type=float, default=2.0)
    p.add_argument("--max-depth", type=int, default=1000)
    p = sub.add_parser("run-as")
    p.add_argument("user")
    p.add_argument("--k", type=int, default=10)
    p.add_argument("--nq", type=int, default=3)
    p.add_argument("--sls", type=int, default=None)
    p = sub.add_parser("real")
    p.add_argument("phase", choices=["baseline", "rcac", "router"])
    p.add_argument("--k", type=int, default=10)
    p.add_argument("--nq", type=int, default=0)
    p.add_argument("--reverse", action="store_true")
    p.add_argument("--T", type=int, default=2000)
    p.add_argument("--m", type=float, default=1.0)
    p.add_argument("--out", default="rcac_real_results.json")
    p = sub.add_parser("plancache")
    p.add_argument("--nq", type=int, default=10)
    p.add_argument("--out", default="rcac_plancache.json")
    p = sub.add_parser("triage")
    p.add_argument("--out", default="rcac_triage.json")
    p = sub.add_parser("ffsource")
    p.add_argument("--out", default="rcac_ffsource.json")
    p = sub.add_parser("actuals")
    p.add_argument("--user", default="NDL_P10")
    p.add_argument("--nq", type=int, default=3)
    p.add_argument("--out", default="rcac_actuals.json")
    p = sub.add_parser("litcopy")
    p.add_argument("phase", choices=["build", "measure", "drop"])
    p.add_argument("--variant", choices=list(LIT_PERMS), default="B_literal")
    p.add_argument("--out", default="rcac_litcopy.json")
    p = sub.add_parser("correlated")
    p.add_argument("phase", choices=["build", "measure", "plans", "drop"])
    p.add_argument("--k", type=int, default=100)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--out", default="rcac_correlated.json")
    args = ap.parse_args()
    {"synth-load": cmd_synth_load, "explain": cmd_explain, "synth-rcac": cmd_synth_rcac,
     "sweep": cmd_sweep, "run-as": cmd_run_as, "real": cmd_real, "plancache": cmd_plancache,
     "triage": cmd_triage, "ffsource": cmd_ffsource, "actuals": cmd_actuals, "litcopy": cmd_litcopy,
     "correlated": cmd_correlated}[args.cmd](args)


if __name__ == "__main__":
    main()
