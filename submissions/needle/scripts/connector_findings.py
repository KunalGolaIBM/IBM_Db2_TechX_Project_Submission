#!/usr/bin/env python3
"""Connector findings F1-F4: measured behaviour of the Db2 AI connectors on a live Db2 12.1.5.0.

Runs INSIDE the codespace (python3 + ibm_db + langchain-db2 1.0.0, localhost:50000), so latencies
exclude the PC tunnel. Credentials come from environment variables only (DB2_PASSWORD required;
DB2_USER/DB2_DATABASE/DB2_HOST/DB2_PORT default to db2inst1/VECDB/localhost/50000).
Wrapper: scripts/connector_findings.sh (password on stdin, never on a command line or in a file).

Steps (each prints its evidence to stdout and to <out>/connector_<step>.txt):
  setup    schema NDL_CONN (committed statement by statement):
           F1_NULLABLE (ADV_ID, EMB nullable, as langchain-db2 / ibm-db-haystack create the column) and
           F1_NOTNULL (ADV_ID, ROW_BUCKET, EMB NOT NULL) = copies of NEEDLE.ADV_DOC via INSERT ... SELECT;
           CREATE VECTOR INDEX on both; F1_NULLABLE gets RUNSTATS ... FOR INDEXES ALL exactly as
           langchain-ibm PR #342 create_index() runs it, F1_NOTNULL gets full RUNSTATS.
           (NEEDLE.ADV_DOC is not the control: RCAC is active on it.)
           DB2VS_ADV: created BY langchain-db2 DB2VS.__init__, filled with INSERT ... SELECT in committed
           ADV_ID-range batches of ~2,000 rows (metadata = {adv_id, kind, row_bucket}).
  f1       nullable vector column: EXPLAIN (PR #342 stats, then full RUNSTATS) + timing of FETCH APPROX
           with and without EMB IS NOT NULL, nullable vs NOT NULL.
  f2       k as a parameter marker, and the ibm-db-haystack 1.0.0 / PR #4086 query shapes.
  f3f4     DB2VS filtered search through the library (Python post-filter after FETCH FIRST k) vs
           SQL WHERE + FETCH APPROX with depth over-fetch on F1_NOTNULL; recall@10 against the exact
           filtered top-10. Writes db2vs_baseline.json.
  tempspace  system temporary space held by DB2VS searches in one open transaction, then after COMMIT.
  writes   INSERT / UPDATE / DELETE / TRUNCATE on a small table that has a vector index.
  cleanup  drop the NDL_CONN tables and the schema.
Every bulk statement runs with autocommit on (one statement = one transaction).

Only integers validated with int() are interpolated into SQL (literal FETCH APPROX k / depth);
query vectors are bound parameters, except where the point is to reproduce the library's own SQL.
"""
import argparse
import gzip
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone

import ibm_db
import ibm_db_dbi

K = 10
DIM = 768
BUCKET = 10                     # ROW_BUCKET is uniform 0-99, so ROW_BUCKET < 10 keeps ~10 % of rows
SCHEMA = "NDL_CONN"
BOUND = "VECTOR(CAST(? AS CLOB(100K)), 768, FLOAT32)"
NFY = "/database/config/db2inst1/sqllib/db2dump/DIAG0000/db2inst1.nfy"
T_NULL = f"{SCHEMA}.F1_NULLABLE"
T_NN = f"{SCHEMA}.F1_NOTNULL"     # NOT NULL control (+ ROW_BUCKET): no RCAC; NEEDLE.ADV_DOC has RCAC active
T_VS = f"{SCHEMA}.DB2VS_ADV"      # created by langchain-db2 DB2VS (id CHAR(16), text CLOB, metadata BLOB, embedding nullable)
NONCE = hashlib.sha256(str(time.time()).encode()).hexdigest()[:4].upper()
_tag_counter = [0]


class Tee:
    def __init__(self, path):
        self.f = open(path, "w", encoding="utf-8")

    def write(self, s):
        sys.__stdout__.write(s)
        self.f.write(s)

    def flush(self):
        sys.__stdout__.flush()
        self.f.flush()


def dsn():
    pw = os.environ.get("DB2_PASSWORD")
    if not pw:
        sys.exit("DB2_PASSWORD is not set")
    return (f"DATABASE={os.environ.get('DB2_DATABASE', 'VECDB')};"
            f"HOSTNAME={os.environ.get('DB2_HOST', 'localhost')};"
            f"PORT={os.environ.get('DB2_PORT', '50000')};PROTOCOL=TCPIP;"
            f"UID={os.environ.get('DB2_USER', 'db2inst1')};PWD={pw};")


def q(conn, sql, params=None):
    if params is None:
        st = ibm_db.exec_immediate(conn, sql)
    else:
        st = ibm_db.prepare(conn, sql)
        ibm_db.execute(st, tuple(params))
    out, row = [], ibm_db.fetch_tuple(st)
    while row:
        out.append(row)
        row = ibm_db.fetch_tuple(st)
    return out


def run(conn, sql, label=None, ignore=()):
    t0 = time.perf_counter()
    try:
        ibm_db.exec_immediate(conn, sql)
        ibm_db.commit(conn)
        print(f"OK   {time.perf_counter() - t0:7.1f}s  {label or sql[:140]}", flush=True)
        return True, None
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if any(code in msg for code in ignore):
            print(f"SKIP {time.perf_counter() - t0:7.1f}s  {label or sql[:140]}  ({msg[:120]})", flush=True)
            return True, msg
        print(f"FAIL {time.perf_counter() - t0:7.1f}s  {label or sql[:140]}\n     {msg[:600]}", flush=True)
        return False, msg


def vtext(v):
    return json.dumps([float(x) for x in v], separators=(",", ":"))


def fmt_lat(lat):
    s = sorted(lat)
    p95 = s[min(len(s) - 1, int(round(0.95 * (len(s) - 1))))]
    return f"n={len(s)} median={statistics.median(s):.1f} ms p95={p95:.1f} ms min={s[0]:.1f} max={s[-1]:.1f}"


def lat_stats(lat):
    s = sorted(lat)
    return {"median_ms": round(statistics.median(s), 2),
            "p95_ms": round(s[min(len(s) - 1, int(round(0.95 * (len(s) - 1))))], 2),
            "min_ms": round(s[0], 2), "max_ms": round(s[-1], 2)}


def nfy_count(code="ADM13500E"):
    r = subprocess.run(["docker", "exec", "db2", "bash", "-c", f"grep -c {code} {NFY} || true"],
                       capture_output=True, text=True, timeout=60)
    try:
        return int(r.stdout.strip() or 0)
    except ValueError:
        return -1


def nfy_tail(lines=40):
    r = subprocess.run(["docker", "exec", "db2", "bash", "-c", f"tail -n {int(lines)} {NFY}"],
                       capture_output=True, text=True, timeout=60)
    return r.stdout


# ---------------------------------------------------------------- EXPLAIN helpers
def explain(conn, stmt, params_note=""):
    _tag_counter[0] += 1
    tag = f"CF{NONCE}{_tag_counter[0]:03d}"
    ibm_db.exec_immediate(conn, f"EXPLAIN PLAN SET QUERYTAG = '{tag}' FOR " + stmt)
    ibm_db.commit(conn)
    inst = q(conn, "SELECT EXPLAIN_TIME, TOTAL_COST FROM DB2INST1.EXPLAIN_STATEMENT WHERE QUERYTAG = ? "
                   "AND EXPLAIN_LEVEL = 'P' ORDER BY EXPLAIN_TIME DESC FETCH FIRST 1 ROW ONLY", [tag.ljust(20)[:20]])
    et, total = inst[0]
    ops = q(conn, "SELECT OPERATOR_ID, OPERATOR_TYPE, TOTAL_COST FROM DB2INST1.EXPLAIN_OPERATOR "
                  "WHERE EXPLAIN_TIME = ? ORDER BY OPERATOR_ID", [et])
    streams = q(conn, "SELECT SOURCE_ID, SOURCE_TYPE, TARGET_ID, TARGET_TYPE, OBJECT_SCHEMA, OBJECT_NAME, STREAM_COUNT "
                      "FROM DB2INST1.EXPLAIN_STREAM WHERE EXPLAIN_TIME = ? AND OBJECT_NAME IS NOT NULL "
                      "ORDER BY TARGET_ID", [et])
    objs = q(conn, "SELECT OBJECT_SCHEMA, OBJECT_NAME, OBJECT_TYPE FROM DB2INST1.EXPLAIN_OBJECT "
                   "WHERE EXPLAIN_TIME = ? ORDER BY OBJECT_NAME", [et])
    # A vector index appears in EXPLAIN_OBJECT with OBJECT_TYPE 'VI'; it counts as used when a plan
    # stream reads from it (the IXSCAN input).
    vi = {f"{(o[0] or '').strip()}.{(o[1] or '').strip()}" for o in objs if (o[2] or "").strip() == "VI"}
    vix = sorted({f"{(x[4] or '').strip()}.{(x[5] or '').strip()}" for x in streams} & vi)
    return {"tag": tag, "explain_time": et, "total_cost": total, "ops": ops, "streams": streams,
            "objs": objs, "vector_index_used": vix}


def exfmt(et, tag):
    ts = et.strftime("%Y-%m-%d-%H.%M.%S.%f") if hasattr(et, "strftime") else str(et)
    out = f"/tmp/conn_exfmt_{tag}.txt"
    cmd = ["docker", "exec", "-u", "db2inst1", "db2", "bash", "-lc",
           f"cd /tmp && rm -f {out}; db2exfmt -d VECDB -e DB2INST1 -w {ts} -n % -s % -# 0 -g TIC "
           f"-o {out} >/dev/null 2>&1; cat {out}; rm -f {out}"]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=120).stdout
    except Exception as e:  # noqa: BLE001
        return f"db2exfmt failed: {e}"


def plan_graph(text):
    if not text:
        return "(no db2exfmt output)"
    keep, on = [], False
    for ln in text.splitlines():
        if ln.startswith("Access Plan:"):
            on = True
        if on:
            if ln.startswith("Operator Symbols") or ln.startswith("Plan Details:") or ln.startswith("Extended Diagnostic"):
                break
            keep.append(ln)
    return "\n".join(keep).rstrip() if keep else "(Access Plan section not found)"


def diag_section(text):
    """Extended Diagnostic Information (optimizer messages such as SQL0437W reason codes), if any."""
    if not text:
        return ""
    keep, on = [], False
    for ln in text.splitlines():
        if ln.startswith("Extended Diagnostic Information"):
            on = True
        elif on and ln.startswith("Plan Details:"):
            break
        if on:
            keep.append(ln)
    return "\n".join(keep).strip()


def show_sql(sql):
    if "VECTOR('[" in sql or "VECTOR('" in sql:
        head, rest = sql.split("VECTOR('", 1)
        tail = rest.split("'", 1)[1]
        return head + "VECTOR('<768 floats inlined>'" + tail
    return sql


def print_explain(conn, name, sql, with_exfmt=True):
    e = explain(conn, sql)
    print(f"\n### {name}\n\n```sql\n{' '.join(show_sql(sql).split())}\n```\n")
    print(f"EXPLAIN_TIME {e['explain_time']}  QUERYTAG {e['tag']}  total cost {e['total_cost']}  "
          f"**vector index used: {e['vector_index_used'] or 'NO'}**\n")
    print("```\nOPERATOR_ID OPERATOR_TYPE TOTAL_COST")
    for o in e["ops"]:
        print(f"{o[0]:>11} {o[1].strip():<13} {o[2]}")
    print("EXPLAIN_STREAM (SRC -> TGT  OBJECT  ROWS):")
    for s in e["streams"]:
        print(f"  {s[0]} {s[1]} -> {s[2]} {s[3]}  {(s[4] or '').strip()}.{(s[5] or '').strip()}  {s[6]}")
    print("EXPLAIN_OBJECT:")
    for o in e["objs"]:
        print(f"  {o[0].strip()}.{o[1].strip()} {o[2]}")
    print("```")
    if with_exfmt:
        txt = exfmt(e["explain_time"], e["tag"])
        print("\ndb2exfmt access plan:\n\n```")
        print(plan_graph(txt))
        print("```")
        d = diag_section(txt)
        if d:
            print("\n```\n" + d + "\n```")
    return e


# ---------------------------------------------------------------- data
def load_qvecs(path, prefix="paraphrase:"):
    d = json.load(gzip.open(path, "rt", encoding="utf-8"))
    items = sorted((k, v) for k, v in d["vectors"].items() if k.startswith(prefix))
    return items, d.get("embedding", {})


def ids(conn, sql, params):
    return [r[0].strip() if isinstance(r[0], str) else r[0] for r in q(conn, sql, params)]


# ---------------------------------------------------------------- langchain-db2 helpers
class CountingEmbeddings:
    """Stub embedding model (768-dim). Counts calls so the per-search embedding overhead is visible.
    The query vectors are passed to similarity_search_by_vector directly, so the stub's output is
    only used by DB2VS.get_embedding_dimension()."""

    def __init__(self):
        self.calls = {"embed_documents": 0, "embed_query": 0}

    def embed_documents(self, texts):
        self.calls["embed_documents"] += 1
        return [[0.0] * (DIM - 1) + [1.0] for _ in texts]

    def embed_query(self, text):
        self.calls["embed_query"] += 1
        return [0.0] * (DIM - 1) + [1.0]


class CursorProxy:
    def __init__(self, cur, log):
        self._c, self._log = cur, log

    def execute(self, sql, *a, **k):
        self._log.append(sql)
        return self._c.execute(sql, *a, **k)

    def __getattr__(self, n):
        return getattr(self._c, n)


class ConnProxy:
    """Wraps an ibm_db_dbi connection and records every SQL text DB2VS executes."""

    def __init__(self, conn):
        self._conn, self.log = conn, []

    def cursor(self):
        return CursorProxy(self._conn.cursor(), self.log)

    def __getattr__(self, n):
        return getattr(self._conn, n)


def make_store(proxy, emb):
    from langchain_community.vectorstores.utils import DistanceStrategy
    from langchain_db2 import DB2VS
    return DB2VS(embedding_function=emb, table_name=T_VS, client=proxy, distance_strategy=DistanceStrategy.COSINE)


# ---------------------------------------------------------------- steps
def adv_bounds(conn, size=2000):
    """ADV_ID lower bounds of consecutive ~size-row ranges of NEEDLE.ADV_DOC."""
    return [r[0] for r in q(conn, "SELECT ADV_ID FROM (SELECT ADV_ID, ROW_NUMBER() OVER (ORDER BY ADV_ID) AS RN "
                                  f"FROM NEEDLE.ADV_DOC) WHERE MOD(RN - 1, {int(size)}) = 0 ORDER BY ADV_ID")]


def batched_insert(conn, ins, bounds, label):
    """Run `ins` (an INSERT ... SELECT ... FROM NEEDLE.ADV_DOC WHERE ADV_ID >= ? AND ADV_ID < ?) once per ADV_ID
    range and COMMIT after each batch, so no transaction holds more than ~2,000 vector rows of log."""
    ins_last = ins.replace(" AND ADV_ID < ?", "")
    print(f"batched INSERT ({len(bounds)} batches, COMMIT per batch): {ins}")
    t0, total = time.perf_counter(), 0
    for i, lo in enumerate(bounds):
        hi = bounds[i + 1] if i + 1 < len(bounds) else None
        st = ibm_db.prepare(conn, ins if hi else ins_last)
        ibm_db.execute(st, (lo, hi) if hi else (lo,))
        total += ibm_db.num_rows(st)
        ibm_db.commit(conn)
    print(f"OK   {time.perf_counter() - t0:7.1f}s  {label}: {total} rows in {len(bounds)} committed batches", flush=True)


def step_setup(conn):
    print(f"## connector_findings setup  ({datetime.now(timezone.utc).isoformat(timespec='seconds')})\n")
    print("```")
    print("Db2:", q(conn, "SELECT SERVICE_LEVEL FROM TABLE(SYSPROC.ENV_GET_INST_INFO())")[0][0])
    print("autocommit:", ibm_db.autocommit(conn) == ibm_db.SQL_AUTOCOMMIT_ON)
    print("ADM13500E count in notify log before:", nfy_count())
    run(conn, f"CREATE SCHEMA {SCHEMA}", ignore=("SQL0601N",))
    for t in (T_NULL, T_NN, T_VS):
        run(conn, f"DROP TABLE {t}", ignore=("SQL0204N",))
    # Same column type as langchain-db2 1.0.0 _create_table (db2vs.py:118) and ibm-db-haystack 1.0.0
    # (document_store.py:277): VECTOR(dim, FLOAT32) with no NOT NULL.
    run(conn, f"CREATE TABLE {T_NULL} (ADV_ID VARCHAR(64) NOT NULL PRIMARY KEY, EMB VECTOR(768, FLOAT32))")
    run(conn, f"CREATE TABLE {T_NN} (ADV_ID VARCHAR(64) NOT NULL PRIMARY KEY, ROW_BUCKET SMALLINT NOT NULL, "
              "EMB VECTOR(768, FLOAT32) NOT NULL)")
    bounds = adv_bounds(conn)
    batched_insert(conn, f"INSERT INTO {T_NULL} (ADV_ID, EMB) SELECT ADV_ID, EMB FROM NEEDLE.ADV_DOC "
                         "WHERE ADV_ID >= ? AND ADV_ID < ?", bounds, T_NULL)
    batched_insert(conn, f"INSERT INTO {T_NN} (ADV_ID, ROW_BUCKET, EMB) SELECT ADV_ID, ROW_BUCKET, EMB "
                         "FROM NEEDLE.ADV_DOC WHERE ADV_ID >= ? AND ADV_ID < ?", bounds, T_NN)
    for t in (T_NULL, T_NN):
        name = t.split(".")[1] + "_VIX"
        before = nfy_count()
        # PR #342 create_index(): CREATE VECTOR INDEX {quoted name} ON {table} ("EMBEDDING") WITH DISTANCE {metric}
        run(conn, f'CREATE VECTOR INDEX {SCHEMA}."{name}" ON {t} ("EMB") WITH DISTANCE COSINE')
        print(f"     ADM13500E count after CREATE VECTOR INDEX {SCHEMA}.{name}: {nfy_count()} (before {before})")
    # PR #342 create_index() then runs exactly: RUNSTATS ON TABLE {table} FOR INDEXES ALL
    run(conn, f"CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE {T_NULL} FOR INDEXES ALL')")
    # The NOT NULL control gets the same full statistics the product table NEEDLE.ADV_DOC has.
    run(conn, f"CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE {T_NN} WITH DISTRIBUTION AND INDEXES ALL')")
    print("```\n")

    # DB2VS_ADV: the table is created by langchain-db2 itself (DB2VS.__init__ -> _create_table).
    dbi = ibm_db_dbi.connect(dsn(), "", "")
    try:
        proxy = ConnProxy(dbi)
        make_store(proxy, CountingEmbeddings())
        print("DB2VS.__init__ executed (captured SQL):\n```")
        for s in proxy.log:
            print("  " + " ".join(s.split()))
        print("```\n")
    finally:
        dbi.close()

    # Fill in committed batches of ~2,000 rows (ADV_ID ranges), one transaction per batch.
    # id = sha256(adv_id)[:16].upper(), the derivation DB2VS.add_texts uses for caller ids (db2vs.py:429-431).
    print("```")
    ins = (f"INSERT INTO {T_VS} (id, text, metadata, embedding) "
           "SELECT SUBSTR(HEX(HASH(ADV_ID, 2)), 1, 16), COALESCE(SUMMARY, ''), "
           "SYSTOOLS.JSON2BSON('{\"adv_id\":\"' || ADV_ID || '\",\"kind\":\"' || TRIM(KIND) || "
           "'\",\"row_bucket\":' || VARCHAR(ROW_BUCKET) || '}'), EMB FROM NEEDLE.ADV_DOC "
           "WHERE ADV_ID >= ? AND ADV_ID < ?")
    batched_insert(conn, ins, bounds, T_VS)
    sample = q(conn, f"SELECT id, SYSTOOLS.BSON2JSON(metadata) FROM {T_VS} ORDER BY id FETCH FIRST 3 ROWS ONLY")
    for rid, meta in sample:
        aid = json.loads(meta)["adv_id"]
        print(f"  id check {rid.strip()} == sha256({aid})[:16].upper(): "
              f"{rid.strip() == hashlib.sha256(aid.encode()).hexdigest()[:16].upper()}  metadata={meta}")
    print("```\n")
    catalog(conn)
    print("\nnotify log tail (last 25 lines):\n```")
    print(nfy_tail(25).rstrip())
    print("```")


T_W = f"{SCHEMA}.F5_WRITES"
TEMP_DIR = "/database/data/db2inst1/NODE0000/VECDB/T0000001"   # TEMPSPACE1 (SMS) container


def temp_usage(conn):
    pages, psize = q(conn, "SELECT TBSP_USED_PAGES, TBSP_PAGE_SIZE FROM TABLE(MON_GET_TABLESPACE('TEMPSPACE1', -2))")[0]
    r = subprocess.run(["docker", "exec", "db2", "bash", "-c", f"du -sb {TEMP_DIR} | cut -f1"],
                       capture_output=True, text=True, timeout=60)
    try:
        du = int(r.stdout.strip())
    except ValueError:
        du = -1
    return int(pages) * int(psize), du


def step_tempspace(conn, items, n=8):
    """System temporary space held by DB2VS searches inside one open transaction, then after COMMIT."""
    print(f"## F3b temporary space per DB2VS search  ({datetime.now(timezone.utc).isoformat(timespec='seconds')})\n")
    vecs = [v for _, v in items[:n]]
    dbi = ibm_db_dbi.connect(dsn(), "", "")
    handler = getattr(dbi, "conn_handler", None)
    print("```")
    print("ibm_db_dbi connection autocommit:",
          ibm_db.autocommit(handler) if handler is not None else "UNKNOWN", "(0 = off)")
    proxy = ConnProxy(dbi)
    store = make_store(proxy, CountingEmbeddings())
    b = temp_usage(conn)
    print(f"start: TEMPSPACE1 used bytes (MON_GET_TABLESPACE)={b[0]:,}  container du bytes={b[1]:,}")
    for i, v in enumerate(vecs):
        t0 = time.perf_counter()
        store.similarity_search_by_vector_with_relevance_scores(embedding=v, k=K, filter=None)
        ms = (time.perf_counter() - t0) * 1000
        u = temp_usage(conn)
        print(f"after DB2VS search {i + 1} (k=10, no commit): used={u[0]:,}  du={u[1]:,}  ({ms:.0f} ms)")
    dbi.commit()
    u = temp_usage(conn)
    print(f"after dbi.commit(): used={u[0]:,}  du={u[1]:,}")
    dbi.close()

    # Which part of the statement holds the space: same statement text, select list varied.
    sql = " ".join(next(s for s in proxy.log if "vector_distance" in s).split())
    head, tail = sql.split(" FROM ", 1)
    variants = [
        ("as executed by DB2VS (id, text, BSON2JSON(metadata), distance)", sql),
        ("id, text, metadata (raw BLOB), distance", sql.replace("SYSTOOLS.BSON2JSON(metadata)", "metadata")),
        ("id, distance only", "SELECT id, " + head.split(",", 3)[3].strip() + " FROM " + tail),
        ("BSON2JSON applied after the top-k (outer query over FETCH FIRST 10)",
         "SELECT id, text, SYSTOOLS.BSON2JSON(metadata), distance FROM ("
         + sql.replace("SYSTOOLS.BSON2JSON(metadata)", "metadata") + ") X ORDER BY distance"),
    ]
    c2 = ibm_db.connect(dsn(), "", "")
    ibm_db.autocommit(c2, ibm_db.SQL_AUTOCOMMIT_OFF)
    try:
        for name, s in variants:
            before = temp_usage(conn)
            for _ in range(4):
                st = ibm_db.exec_immediate(c2, s)
                r = ibm_db.fetch_tuple(st)
                while r:
                    r = ibm_db.fetch_tuple(st)
                ibm_db.free_stmt(st)
            mid = temp_usage(conn)
            ibm_db.commit(c2)
            after = temp_usage(conn)
            print(f"{name}: 4 executions in one transaction -> du +{mid[1] - before[1]:,} bytes; "
                  f"after COMMIT du {after[1]:,}")
    finally:
        ibm_db.close(c2)
    print("```")


def step_writes(conn):
    """Write path on a table that has a vector index, in the order the connectors use it:
    create_index() (PR #342) / create_vector_index=True (PR #4086) at setup, then add/delete documents,
    then langchain-db2 clear_table() = TRUNCATE TABLE ... IMMEDIATE (db2vs.py:202). Small 2,000-row table."""
    print(f"## F5 write path on an indexed table  ({datetime.now(timezone.utc).isoformat(timespec='seconds')})\n```")
    run(conn, f"DROP TABLE {T_W}", ignore=("SQL0204N",))
    run(conn, f"CREATE TABLE {T_W} (ADV_ID VARCHAR(64) NOT NULL PRIMARY KEY, EMB VECTOR(768, FLOAT32))")
    run(conn, f"INSERT INTO {T_W} SELECT ADV_ID, EMB FROM {T_NN} ORDER BY ADV_ID FETCH FIRST 2000 ROWS ONLY")
    before = nfy_count()
    run(conn, f'CREATE VECTOR INDEX {SCHEMA}."F5_WRITES_VIX" ON {T_W} ("EMB") WITH DISTANCE COSINE')
    print(f"     ADM13500E count: {nfy_count()} (before {before})")
    run(conn, f"CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE {T_W} FOR INDEXES ALL')")
    one = f"(SELECT EMB FROM {T_NN} ORDER BY ADV_ID DESC FETCH FIRST 1 ROW ONLY)"
    run(conn, f"INSERT INTO {T_W} (ADV_ID, EMB) VALUES ('NDL-CONN-W1', {one})", label="INSERT one row (add_texts)")
    run(conn, f"UPDATE {T_W} SET EMB = {one} WHERE ADV_ID = 'NDL-CONN-W1'", label="UPDATE the vector of that row")
    run(conn, f"DELETE FROM {T_W} WHERE ADV_ID = 'NDL-CONN-W1'", label="DELETE that row (delete(ids))")
    print("     rows:", q(conn, f"SELECT COUNT(*) FROM {T_W}")[0][0])
    run(conn, f"TRUNCATE TABLE {T_W} IMMEDIATE", label="TRUNCATE TABLE ... IMMEDIATE (clear_table, db2vs.py:202)")
    try:
        print("     after TRUNCATE, SELECT COUNT(*):", q(conn, f"SELECT COUNT(*) FROM {T_W}")[0][0])
    except Exception as e:  # noqa: BLE001
        print("     after TRUNCATE, SELECT COUNT(*) failed:", str(e)[:300])
    run(conn, f"INSERT INTO {T_W} (ADV_ID, EMB) VALUES ('NDL-CONN-W2', {one})", label="INSERT one row after TRUNCATE")
    run(conn, f"DROP INDEX {SCHEMA}.\"F5_WRITES_VIX\"", label="DROP INDEX F5_WRITES_VIX (drop_index, PR #342)")
    try:
        print("     after DROP INDEX, SELECT COUNT(*):", q(conn, f"SELECT COUNT(*) FROM {T_W}")[0][0])
    except Exception as e:  # noqa: BLE001
        print("     after DROP INDEX, SELECT COUNT(*) failed:", str(e)[:300])
    run(conn, f"DROP TABLE {T_W}", ignore=("SQL0204N",))
    print("```")


def step_cleanup(conn):
    print(f"## connector_findings cleanup  ({datetime.now(timezone.utc).isoformat(timespec='seconds')})\n```")
    for t in (T_NULL, T_NN, T_VS, T_W):
        run(conn, f"DROP TABLE {t}", ignore=("SQL0204N",))
    run(conn, f"DROP SCHEMA {SCHEMA} RESTRICT", ignore=("SQL0204N",))
    print("```")


def catalog(conn):
    print("Catalog:\n```")
    for s, t in (tuple(x.split(".")) for x in (T_NULL, T_NN, T_VS)):
        for r in q(conn, "SELECT TABSCHEMA, TABNAME, COLNAME, TYPENAME, LENGTH, NULLS FROM SYSCAT.COLUMNS "
                         "WHERE TABSCHEMA = ? AND TABNAME = ? AND TYPENAME = 'VECTOR'", [s, t]):
            print("  vector column", tuple(x.strip() if isinstance(x, str) else x for x in r))
        for r in q(conn, "SELECT TABSCHEMA, TABNAME, CARD, NPAGES, STATS_TIME FROM SYSCAT.TABLES "
                         "WHERE TABSCHEMA = ? AND TABNAME = ?", [s, t]):
            print("  table        ", tuple(x.strip() if isinstance(x, str) else x for x in r))
        for r in q(conn, "SELECT INDSCHEMA, INDNAME, INDEXTYPE, COLNAMES, NLEAF, STATS_TIME FROM SYSCAT.INDEXES "
                         "WHERE TABSCHEMA = ? AND TABNAME = ? ORDER BY INDNAME", [s, t]):
            print("  index        ", tuple(x.strip() if isinstance(x, str) else x for x in r))
        col = "embedding" if f"{s}.{t}" == T_VS else "EMB"
        try:
            n = q(conn, f"SELECT COUNT(*), SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END) FROM {s}.{t}")[0]
            print(f"  {s}.{t}: rows={n[0]} null_vectors={n[1]}")
        except Exception as e:  # noqa: BLE001
            print(f"  {s}.{t}: {str(e)[:120]}")
    print("```")


def time_ids(conn, sql, vecs, nbind=1, take=None):
    st = ibm_db.prepare(conn, sql)
    lat, res = [], []
    for v in vecs:
        t0 = time.perf_counter()
        ibm_db.execute(st, tuple([vtext(v)] * nbind))
        rows, row = [], ibm_db.fetch_tuple(st)
        while row:
            rows.append(row[0].strip())
            row = ibm_db.fetch_tuple(st)
        lat.append((time.perf_counter() - t0) * 1000)
        res.append(rows[:take] if take else rows)
    return lat, res


def step_f1(conn, vecs):
    print(f"## F1 nullable vector column  ({datetime.now(timezone.utc).isoformat(timespec='seconds')})\n")
    approx = "SELECT ADV_ID FROM {t}{w} ORDER BY VECTOR_DISTANCE(EMB, " + BOUND + ", COSINE) FETCH APPROX FIRST 10 ROWS ONLY"
    exact = "SELECT ADV_ID FROM {t}{w} ORDER BY VECTOR_DISTANCE(EMB, " + BOUND + ", COSINE) FETCH EXACT FIRST 10 ROWS ONLY"
    summary = []

    # Phase A: statistics exactly as PR #342 create_index() leaves them (RUNSTATS ... FOR INDEXES ALL).
    print("### Phase A: after RUNSTATS ON TABLE ... FOR INDEXES ALL (the statement PR #342 create_index() runs)\n")
    catalog(conn)
    for w in ("", " WHERE EMB IS NOT NULL"):
        name = f"A {T_NULL} APPROX k=10{' + EMB IS NOT NULL' if w else ''}"
        e = print_explain(conn, name, approx.format(t=T_NULL, w=w))
        summary.append(f"{name:<62} index={','.join(e['vector_index_used']) or 'NO':<26} cost={e['total_cost']:.1f}")

    # Phase B: full statistics, the same RUNSTATS the NOT NULL control F1_NOTNULL received.
    print("\n### Phase B: after RUNSTATS ON TABLE ... WITH DISTRIBUTION AND INDEXES ALL\n\n```")
    run(conn, f"CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE {T_NULL} WITH DISTRIBUTION AND INDEXES ALL')")
    print("```")
    catalog(conn)
    for t in (T_NULL, T_NN):
        for w in ("", " WHERE EMB IS NOT NULL"):
            name = f"B {t} APPROX k=10{' + EMB IS NOT NULL' if w else ''}"
            e = print_explain(conn, name, approx.format(t=t, w=w))
            la, ra = time_ids(conn, approx.format(t=t, w=w), vecs)
            le, re_ = time_ids(conn, exact.format(t=t, w=w), vecs)
            rec = [len(set(a) & set(b)) / K for a, b in zip(ra, re_)]
            line = (f"{name:<62} index={','.join(e['vector_index_used']) or 'NO':<26} cost={e['total_cost']:.1f} | "
                    f"APPROX {fmt_lat(la)} | EXACT {fmt_lat(le)} | APPROX-vs-EXACT overlap@10 mean={statistics.mean(rec):.3f}")
            summary.append(line)
            print(f"\n```\n{line}\n```")
    print("\n### F1 summary\n\n```")
    print("\n".join(summary))
    print("```")
    print(f"\nADM13500E count in notify log now: {nfy_count()}")


def step_f2(conn, vecs):
    print(f"## F2 k as a parameter marker  ({datetime.now(timezone.utc).isoformat(timespec='seconds')})\n")
    a = f"SELECT ADV_ID FROM {T_NN} ORDER BY VECTOR_DISTANCE(EMB, {BOUND}, COSINE) FETCH APPROX FIRST 10 ROWS ONLY"
    b = f"SELECT ADV_ID FROM {T_NN} ORDER BY VECTOR_DISTANCE(EMB, {BOUND}, COSINE) FETCH APPROX FIRST ? ROWS ONLY"
    # ibm-db-haystack 1.0.0 _embedding_retrieval shape (document_store.py:914-926), table/columns mapped to
    # ours; content/meta columns omitted because the F1 tables do not have them.
    hay = ("SELECT ADV_ID, EMB, VECTOR_DISTANCE(EMB, " + BOUND + ", COSINE) AS score FROM {t} {w}"
           "ORDER BY score ASC FETCH {m}FIRST {k} ROWS ONLY")
    variants = [
        ("a) APPROX, k literal 10", a),
        ("b) APPROX, k parameter marker ?", b),
        ("c1) ibm-db-haystack 1.0.0 default: nullable column, WHERE EMB IS NOT NULL, FETCH FIRST ?",
         hay.format(t=T_NULL, w="WHERE EMB IS NOT NULL ", m="", k="?")),
        ("c2) PR #4086 create_vector_index=True: NOT NULL column, no predicate, FETCH FIRST ?",
         hay.format(t=T_NN, w="", m="", k="?")),
        ("d) c2 with FETCH APPROX FIRST ? (k still a marker)", hay.format(t=T_NN, w="", m="APPROX ", k="?")),
        ("e) c2 with FETCH APPROX FIRST 10 (k literal), ORDER BY alias", hay.format(t=T_NN, w="", m="APPROX ", k="10")),
        ("f) c1 with FETCH APPROX FIRST 10 (nullable + IS NOT NULL, k literal)",
         hay.format(t=T_NULL, w="WHERE EMB IS NOT NULL ", m="APPROX ", k="10")),
    ]
    summary = []
    for name, sql in variants:
        e = print_explain(conn, name, sql)
        summary.append(f"{name:<95} index={','.join(e['vector_index_used']) or 'NO':<22} cost={e['total_cost']:.1f}")
    # timing a vs b (k bound to 10 for b)
    la, ra = time_ids(conn, a, vecs)
    st = ibm_db.prepare(conn, b)
    lb, rb = [], []
    for v in vecs:
        t0 = time.perf_counter()
        ibm_db.execute(st, (vtext(v), K))
        rows, row = [], ibm_db.fetch_tuple(st)
        while row:
            rows.append(row[0].strip())
            row = ibm_db.fetch_tuple(st)
        lb.append((time.perf_counter() - t0) * 1000)
        rb.append(rows)
    ov = [len(set(x) & set(y)) / K for x, y in zip(ra, rb)]
    summary.append(f"timing a) literal k: {fmt_lat(la)}")
    summary.append(f"timing b) k=? bound to 10: {fmt_lat(lb)}   rows returned min={min(len(x) for x in rb)}  "
                   f"overlap@10 with a) mean={statistics.mean(ov):.3f}")
    print("\n### F2 summary\n\n```")
    print("\n".join(summary))
    print("```")


def step_f3f4(conn, items, emb_meta, out_dir):
    print(f"## F3/F4 filtered search  ({datetime.now(timezone.utc).isoformat(timespec='seconds')})\n")
    total = q(conn, f"SELECT COUNT(*) FROM {T_NN}")[0][0]
    match = q(conn, f"SELECT COUNT(*) FROM {T_NN} WHERE ROW_BUCKET < {BUCKET}")[0][0]
    vs_rows = q(conn, f"SELECT COUNT(*) FROM {T_VS}")[0][0]
    vs_match = q(conn, f"SELECT COUNT(*) FROM {T_VS} WHERE JSON_VALUE(SYSTOOLS.BSON2JSON(metadata), "
                       f"'$.row_bucket' RETURNING INTEGER) < {BUCKET}")[0][0]
    sel = match / total
    print("```")
    print(f"{T_NN} rows={total}  ROW_BUCKET<{BUCKET} rows={match}  selectivity={sel:.4f}")
    print(f"{T_VS} rows={vs_rows}  metadata row_bucket<{BUCKET} rows={vs_match}")
    print(f"queries: {len(items)} paraphrase query vectors from data/eval_qvecs.json.gz, embedding={emb_meta}")
    print("```\n")

    flt = {"row_bucket": list(range(BUCKET))}   # DB2VS filter semantics: metadata.get(key) in value (db2vs.py:627)
    gt_f = (f"SELECT ADV_ID, VECTOR_DISTANCE(EMB, {BOUND}, COSINE) AS CF_D FROM {T_NN} "
            f"WHERE ROW_BUCKET < {BUCKET} ORDER BY CF_D FETCH EXACT FIRST 20 ROWS ONLY")
    gt_u = (f"SELECT ADV_ID, VECTOR_DISTANCE(EMB, {BOUND}, COSINE) AS CF_D FROM {T_NN} "
            f"ORDER BY CF_D FETCH EXACT FIRST 20 ROWS ONLY")
    f4a = (f"SELECT ADV_ID FROM {T_NN} WHERE ROW_BUCKET < {BUCKET} "
           f"ORDER BY VECTOR_DISTANCE(EMB, {BOUND}, COSINE) FETCH APPROX FIRST 10 ROWS ONLY")
    depth = int(round(K / sel / 10.0)) * 10       # k / selectivity, rounded to 10 -> 100
    depths = [depth, 2 * depth]
    f4b = {d: (f"SELECT ADV_ID FROM {T_NN} WHERE ROW_BUCKET < {BUCKET} "
               f"ORDER BY VECTOR_DISTANCE(EMB, {BOUND}, COSINE) FETCH APPROX FIRST {int(d)} ROWS ONLY") for d in depths}
    f4c = {d: (f"SELECT ADV_ID FROM (SELECT ADV_ID, ROW_BUCKET, VECTOR_DISTANCE(EMB, {BOUND}, COSINE) AS CF_D "
               f"FROM {T_NN} ORDER BY VECTOR_DISTANCE(EMB, {BOUND}, COSINE) FETCH APPROX FIRST {int(d)} ROWS ONLY) X "
               f"WHERE ROW_BUCKET < {BUCKET} ORDER BY CF_D FETCH FIRST 10 ROWS ONLY") for d in depths}

    print("### EXPLAIN of the F4 statements\n")
    plans = {"F4a": print_explain(conn, "F4a SQL WHERE + FETCH APPROX FIRST 10", f4a, with_exfmt=True)}
    for d in depths:
        plans[f"F4b_{d}"] = print_explain(conn, f"F4b SQL WHERE + FETCH APPROX FIRST {d}, take 10", f4b[d], with_exfmt=(d == depth))
        plans[f"F4c_{d}"] = print_explain(conn, f"F4c over-fetch FETCH APPROX FIRST {d}, then WHERE, take 10", f4c[d], with_exfmt=(d == depth))
    plans["GT_filtered_EXACT"] = print_explain(conn, "Ground truth, filtered (FETCH EXACT)", gt_f, with_exfmt=False)
    plans["GT_unfiltered_EXACT"] = print_explain(conn, "Ground truth, unfiltered (FETCH EXACT)", gt_u, with_exfmt=False)
    # The same statements without the APPROX/EXACT keyword (run 2 of this step used these as ground truth by mistake).
    plans["plain_FETCH_FIRST_filtered"] = print_explain(conn, "Same filtered statement with plain FETCH FIRST (no keyword)",
                                                        gt_f.replace("FETCH EXACT FIRST", "FETCH FIRST"), with_exfmt=False)
    plans["plain_FETCH_FIRST_unfiltered"] = print_explain(conn, "Same unfiltered statement with plain FETCH FIRST (no keyword)",
                                                          gt_u.replace("FETCH EXACT FIRST", "FETCH FIRST"), with_exfmt=False)

    # DB2VS store through the library
    dbi = ibm_db_dbi.connect(dsn(), "", "")
    proxy = ConnProxy(dbi)
    emb = CountingEmbeddings()
    store = make_store(proxy, emb)
    proxy.log.clear()
    emb.calls = {"embed_documents": 0, "embed_query": 0}

    st_gtf, st_gtu = ibm_db.prepare(conn, gt_f), ibm_db.prepare(conn, gt_u)

    def gt(st, v):
        ibm_db.execute(st, (vtext(v),))
        rows, row = [], ibm_db.fetch_tuple(st)
        while row:
            rows.append((row[0].strip(), float(row[1])))
            row = ibm_db.fetch_tuple(st)
        return rows

    def recalls(ret, g):
        top = [x[0] for x in g[:K]]
        d10 = g[K - 1][1]
        ext = {x[0] for x in g if x[1] <= d10 + 1e-6}
        strict = len(set(ret[:K]) & set(top)) / K
        tie = min(K, len(set(ret[:K]) & ext)) / K
        return strict, tie

    sql_stmts = {"F4a_where_approx10": (f4a, 1, None)}
    for d in depths:
        sql_stmts[f"F4b_where_approx{d}_top10"] = (f4b[d], 1, K)
        sql_stmts[f"F4c_postfilter_approx{d}_top10"] = (f4c[d], 2, None)
    prepared = {n: (ibm_db.prepare(conn, s), nb, tk) for n, (s, nb, tk) in sql_stmts.items()}

    methods = ["db2vs_k10_filter", "db2vs_k100_filter_top10", "db2vs_k10_nofilter"] + list(sql_stmts)
    per = {m: {"n": [], "strict": [], "tie": [], "lat": []} for m in methods}
    errors = {m: [] for m in methods}
    per_query = []
    embed_calls_per_search = []
    for i, (qid, v) in enumerate(items):
        gf, gu = gt(st_gtf, v), gt(st_gtu, v)
        row = {"qid": qid}
        for m, kk, f in (("db2vs_k10_filter", K, flt), ("db2vs_k100_filter_top10", 100, flt),
                         ("db2vs_k10_nofilter", K, None)):
            c0 = emb.calls["embed_documents"] + emb.calls["embed_query"]
            t0 = time.perf_counter()
            res = store.similarity_search_by_vector_with_relevance_scores(embedding=v, k=kk, filter=f)
            per[m]["lat"].append((time.perf_counter() - t0) * 1000)
            # Application-level COMMIT after every search (not part of the library call or its latency):
            # without it, temporary space held by the open transaction grows per search (see step tempspace).
            dbi.commit()
            embed_calls_per_search.append(emb.calls["embed_documents"] + emb.calls["embed_query"] - c0)
            got = [doc.metadata["adv_id"] for doc, _ in res][:K]
            if f is not None:
                assert all(doc.metadata["row_bucket"] < BUCKET for doc, _ in res)
            s, t = recalls(got, gf if f is not None else gu)
            per[m]["n"].append(len(got))
            per[m]["strict"].append(s)
            per[m]["tie"].append(t)
            row[m] = {"n": len(got), "recall": s}
        for m, (st, nb, tk) in prepared.items():
            t0 = time.perf_counter()
            got = []
            try:
                ibm_db.execute(st, tuple([vtext(v)] * nb))
                r = ibm_db.fetch_tuple(st)
                while r:
                    got.append(r[0].strip())
                    r = ibm_db.fetch_tuple(st)
            except Exception as e:  # noqa: BLE001  (e.g. SQL0901N, see docs/evidence/eval_sql0901n_fetch_approx.md)
                errors[m].append({"qid": qid, "error": str(e)[:300]})
                print(f"  ERROR {m} {qid}: {str(e)[:220]}", flush=True)
                got = []
                row[m + "_error"] = True
            per[m]["lat"].append((time.perf_counter() - t0) * 1000)
            got = got[:tk] if tk else got
            s, t = recalls(got, gf)
            per[m]["n"].append(len(got))
            per[m]["strict"].append(s)
            per[m]["tie"].append(t)
            row[m] = {"n": len(got), "recall": s}
        per_query.append(row)
        if (i + 1) % 25 == 0:
            print(f"  ... {i + 1}/{len(items)} queries", flush=True)

    # DB2VS SQL as executed (captured), and EXPLAIN of it
    vs_sqls = [s for s in proxy.log if "vector_distance" in s]
    distinct_texts = len(set(vs_sqls))
    print(f"\nDB2VS executed {len(vs_sqls)} search statements; distinct statement texts: {distinct_texts} "
          f"(the query vector is inlined, db2vs.py:605).")
    print(f"embedding-model calls per DB2VS search (stub counter): "
          f"min={min(embed_calls_per_search)} max={max(embed_calls_per_search)} "
          f"(get_embedding_dimension() at db2vs.py:599 embeds the probe text on every search)")
    sample_sql = next(s for s in vs_sqls if "FETCH FIRST 10 ROWS" in s)
    plans["DB2VS"] = print_explain(conn, "DB2VS 1.0.0 search statement as executed (captured from the cursor)",
                                   " ".join(sample_sql.split()))
    pc = None
    try:
        pc = q(conn, "SELECT COUNT(*), SUM(NUM_EXECUTIONS), SUM(PREP_TIME) FROM TABLE(MON_GET_PKG_CACHE_STMT('D', NULL, NULL, -2)) T "
                     "WHERE LOCATE('NDL_CONN.DB2VS_ADV', T.STMT_TEXT) > 0 AND LOCATE('vector_distance', T.STMT_TEXT) > 0")[0]
        pc_gt = q(conn, "SELECT COUNT(*), SUM(NUM_EXECUTIONS), SUM(PREP_TIME) FROM TABLE(MON_GET_PKG_CACHE_STMT('D', NULL, NULL, -2)) T "
                        f"WHERE LOCATE('AS CF_D FROM {T_NN} WHERE ROW_BUCKET', T.STMT_TEXT) > 0")[0]
        print(f"package cache (MON_GET_PKG_CACHE_STMT, dynamic): DB2VS statements entries={pc[0]} executions={pc[1]} "
              f"prep_time_ms_sum={pc[2]} | bound ground-truth statement entries={pc_gt[0]} executions={pc_gt[1]} "
              f"prep_time_ms_sum={pc_gt[2]}")
    except Exception as e:  # noqa: BLE001
        print("package cache query failed:", str(e)[:200])
    dbi.close()

    def summ(m):
        n = per[m]["n"]
        return {"mean_returned": round(statistics.mean(n), 3), "min_returned": min(n), "max_returned": max(n),
                "queries_lt_k": sum(1 for x in n if x < K), "queries_zero": sum(1 for x in n if x == 0),
                "recall_at_10_mean": round(statistics.mean(per[m]["strict"]), 4),
                "recall_at_10_min": round(min(per[m]["strict"]), 2),
                "recall_at_10_tie_aware_mean": round(statistics.mean(per[m]["tie"]), 4),
                "latency": lat_stats(per[m]["lat"]),
                "errors": len(errors[m]), "error_detail": errors[m]}

    res = {m: summ(m) for m in methods}
    hist = {}
    for x in per["db2vs_k10_filter"]["n"]:
        hist[x] = hist.get(x, 0) + 1
    print("\n### F3/F4 results\n")
    print(f"{len(items)} queries, k=10, filter ROW_BUCKET < {BUCKET} (selectivity {sel:.4f}); recall@10 vs exact filtered "
          f"top-10 on {T_NN}; tie-aware counts any row at distance <= the 10th exact distance + 1e-6.\n")
    print("```")
    print(f"{'method':<34} {'mean_n':>7} {'min_n':>5} {'q<k':>5} {'q=0':>4} {'recall':>7} {'rmin':>5} {'r_tie':>6} {'err':>4}  latency (in codespace)")
    for m in methods:
        r = res[m]
        print(f"{m:<34} {r['mean_returned']:>7.2f} {r['min_returned']:>5} {r['queries_lt_k']:>5} {r['queries_zero']:>4} "
              f"{r['recall_at_10_mean']:>7.3f} {r['recall_at_10_min']:>5.2f} {r['recall_at_10_tie_aware_mean']:>6.3f} {r['errors']:>4}  "
              f"median={r['latency']['median_ms']} ms p95={r['latency']['p95_ms']} ms")
    print(f"db2vs_k10_filter histogram of rows returned: {dict(sorted(hist.items()))}")
    print("(db2vs_k10_nofilter recall is against the exact UNFILTERED top-10: a correctness check of the copied table.)")
    print("(a statement that raised an error counts as 0 rows returned and recall 0 for that query; see 'err'.)")
    print("```")

    out = {
        "baseline": "langchain-db2 DB2VS",
        "library": {"langchain-db2": "1.0.0", "langchain-core": "1.7.6", "langchain-community": "0.4.2",
                    "file_sha256_db2vs_py": "c5259109a70c03f7e2ebb1f2d3e2caf5675a736d28ee1abe848af82c6d635191"},
        "db2": "v12.1.5.0 CE (container in GitHub Codespace)",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "producer": "scripts/connector_findings.py f3f4 (run inside the codespace; latency excludes the PC tunnel)",
        "table": T_VS, "table_rows": vs_rows, "distance": "COSINE",
        "table_ddl_source": "DB2VS.__init__ -> _create_table (db2vs.py:114-126); rows via INSERT ... SELECT from NEEDLE.ADV_DOC in committed 2,000-row batches",
        "query_set": "paraphrase slice, eval/queries/paraphrase.jsonl; vectors from data/eval_qvecs.json.gz",
        "n_queries": len(items), "k": K,
        "filter": {"db2vs": "filter={'row_bucket': [0..9]}", "sql": f"ROW_BUCKET < {BUCKET}",
                   "matching_rows": match, "selectivity": round(sel, 4)},
        "ground_truth": f"exact filtered top-10 (FETCH EXACT FIRST 20, ties within 1e-6 counted for r_tie) on {T_NN} (copy of NEEDLE.ADV_DOC ADV_ID/ROW_BUCKET/EMB), same vectors, COSINE",
        "sql_methods_table": f"{T_NN} (EMB NOT NULL, vector index, full RUNSTATS, no RCAC)",
        "methods": res,
        "db2vs_returned_histogram": {str(k): v for k, v in sorted(hist.items())},
        "db2vs_search_sql": {"fetch": "FETCH FIRST {k} ROWS ONLY (exact; db2vs.py:609)",
                             "query_vector": "inlined into the SQL text (db2vs.py:605)",
                             "filter": "applied in Python after the fetch (db2vs.py:621-633)",
                             "statements_executed": len(vs_sqls), "distinct_statement_texts": distinct_texts,
                             "embedding_calls_per_search": max(embed_calls_per_search),
                             "uses_vector_index": plans["DB2VS"]["vector_index_used"] or False},
        "plans": {k: {"vector_index_used": v["vector_index_used"] or False, "total_cost": v["total_cost"],
                      "operators": [o[1].strip() for o in v["ops"]]} for k, v in plans.items()},
        "per_query": per_query,
    }
    if pc:
        out["db2vs_search_sql"]["package_cache_entries"] = pc[0]
    path = os.path.join(out_dir, "db2vs_baseline.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=str)
    print(f"\nwrote {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["setup", "f1", "f2", "f3f4", "tempspace", "writes", "cleanup"])
    ap.add_argument("--qvecs", default="/tmp/needle/eval_qvecs.json.gz")
    ap.add_argument("--out", default="/tmp/needle/conn_out")
    ap.add_argument("--n-timing", type=int, default=20, help="queries used for F1/F2 timing")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    sys.stdout = Tee(os.path.join(args.out, f"connector_{args.step}.txt"))
    conn = ibm_db.connect(dsn(), "", "")
    try:
        if args.step == "setup":
            step_setup(conn)
        elif args.step == "cleanup":
            step_cleanup(conn)
        elif args.step == "writes":
            step_writes(conn)
        else:
            items, meta = load_qvecs(args.qvecs)
            if args.step == "f1":
                step_f1(conn, [v for _, v in items[:args.n_timing]])
            elif args.step == "f2":
                step_f2(conn, [v for _, v in items[:args.n_timing]])
            elif args.step == "tempspace":
                step_tempspace(conn, items)
            else:
                step_f3f4(conn, items, meta, args.out)
    finally:
        ibm_db.close(conn)
        sys.stdout.flush()


if __name__ == "__main__":
    main()
