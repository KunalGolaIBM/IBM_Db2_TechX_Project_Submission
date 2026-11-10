#!/usr/bin/env python3
"""Load NEEDLE.POSTING / TERM_DF / CORPUS_STATS. Runs INSIDE the codespace (python3 + ibm_db, localhost:50000).

Credentials from environment variables only: DB2_PASSWORD (required), DB2_USER (default db2inst1),
DB2_DATABASE (default VECDB), DB2_HOST (default localhost), DB2_PORT (default 50000).
Inputs in --dir (default /tmp/needle): 02_bm25.sql, postings.jsonl.gz, corpus_stats.json.

Steps: ddl (pre-load DDL), load (TRUNCATE + insert all postings, commit per batch),
post (indexes, TERM_DF, CORPUS_STATS, RUNSTATS), check (compare Db2 stats with corpus_stats.json).
Usage: python3 load_postings_in_codespace.py [--dir D] [--steps ddl,load,post,check]
       python3 load_postings_in_codespace.py --sample   # postings of the frozen sample in eval/fixtures
02_bm25.sql falls back to ../sql/ (repository layout) when it is not in --dir.
"""
import argparse
import gzip
import json
import os
import sys
import time

import ibm_db

BATCH = 5000
IGNORABLE = ("SQL0601N", "SQL0623N", "SQL0624N", "SQL0605W", "SQL20393N", "SQL0598W", "SQL0554N")
HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.normpath(os.path.join(HERE, "..", "eval", "fixtures"))


def connect():
    pw = os.environ.get("DB2_PASSWORD")
    if not pw:
        sys.exit("DB2_PASSWORD is not set")
    dsn = (
        f"DATABASE={os.environ.get('DB2_DATABASE', 'VECDB')};"
        f"HOSTNAME={os.environ.get('DB2_HOST', 'localhost')};"
        f"PORT={os.environ.get('DB2_PORT', '50000')};PROTOCOL=TCPIP;"
        f"UID={os.environ.get('DB2_USER', 'db2inst1')};PWD={pw};"
    )
    conn = ibm_db.connect(dsn, "", "")
    ibm_db.autocommit(conn, ibm_db.SQL_AUTOCOMMIT_OFF)
    return conn


def split_sql(text):
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def run_ddl(conn, text, label):
    for stmt in split_sql(text):
        t0 = time.time()
        head = " ".join(stmt.split())[:100]
        try:
            ibm_db.exec_immediate(conn, stmt)
            ibm_db.commit(conn)
            print(f"[{label}] OK {time.time()-t0:.1f}s: {head}", flush=True)
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            ibm_db.rollback(conn)
            if any(code in msg for code in IGNORABLE):
                print(f"[{label}] exists/skipped: {head} ({msg[msg.find('SQL'):msg.find('SQL')+9]})", flush=True)
            else:
                print(f"[{label}] FAILED: {head}\n  {msg[:500]}", flush=True)
                raise


def scalar(conn, sql):
    st = ibm_db.exec_immediate(conn, sql)
    return ibm_db.fetch_tuple(st)


def adv_doc_acl(conn):
    """{ADV_ID: (ROW_BUCKET, EMBARGO_UNTIL)} from NEEDLE.ADV_DOC, read as DB2INST1 (its RCAC row sees every row)."""
    acl, st = {}, ibm_db.exec_immediate(conn, "SELECT ADV_ID, ROW_BUCKET, VARCHAR(EMBARGO_UNTIL) FROM NEEDLE.ADV_DOC")
    r = ibm_db.fetch_tuple(st)
    while r:
        acl[r[0]] = (int(r[1]), r[2])
        r = ibm_db.fetch_tuple(st)
    return acl


def load(conn, d):
    # H2: ROW_BUCKET / EMBARGO_UNTIL come from NEEDLE.ADV_DOC at insert time (the build file has no embargo), so a
    # reload never exposes an embargoed posting, not even between the insert and the POST_LOAD MERGE.
    # Fail closed: a posting whose ADV_ID is not in ADV_DOC is not loaded.
    acl = adv_doc_acl(conn)
    embargoed = sum(1 for _, e in acl.values() if e is not None)
    print(f"[load] ADV_DOC rows={len(acl)} with EMBARGO_UNTIL set={embargoed}", flush=True)
    ibm_db.commit(conn)
    ibm_db.exec_immediate(conn, "TRUNCATE TABLE NEEDLE.POSTING IMMEDIATE")
    ibm_db.commit(conn)
    skipped = 0
    stmt = ibm_db.prepare(conn, "INSERT INTO NEEDLE.POSTING (TERM, ADV_ID, TF, BM25_DL, ROW_BUCKET, EMBARGO_UNTIL) "
                                "VALUES (?, ?, ?, ?, ?, ?)")
    t0, n, rows = time.time(), 0, []

    def flush():
        nonlocal n
        if rows:
            ibm_db.execute_many(stmt, tuple(rows))
            ibm_db.commit(conn)
            n += len(rows)
            rows.clear()
            if n % 200000 < BATCH:
                el = time.time() - t0
                print(f"[load] {n} rows {el:.0f}s ({n/max(el,1e-9):.0f} rows/s)", flush=True)

    with gzip.open(os.path.join(d, "postings.jsonl.gz"), "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            a = acl.get(r["adv_id"])
            if a is None:
                skipped += 1
                continue
            rows.append((r["term"], r["adv_id"], int(r["tf"]), int(r["dl"]), a[0], a[1]))
            if len(rows) >= BATCH:
                flush()
    flush()
    print(f"LOADED NEEDLE.POSTING rows={n} skipped_not_in_adv_doc={skipped} time={time.time()-t0:.1f}s", flush=True)


PUBLIC = "(EMBARGO_UNTIL IS NULL OR EMBARGO_UNTIL <= CURRENT TIMESTAMP)"


def check(conn, d):
    """Invariants after a load (run as DB2INST1). corpus_stats.json is the full corpus; the Db2 statistics cover
    public rows only, so they equal the Python numbers exactly only while no embargo is active."""
    exp = json.load(open(os.path.join(d, "corpus_stats.json"), encoding="utf-8"))
    cnt = scalar(conn, "SELECT COUNT(*) FROM NEEDLE.POSTING")[0]
    drift = scalar(conn, "SELECT COUNT(*) FROM NEEDLE.POSTING P JOIN NEEDLE.ADV_DOC D ON D.ADV_ID = P.ADV_ID "
                         "WHERE P.ROW_BUCKET <> D.ROW_BUCKET OR P.EMBARGO_UNTIL IS DISTINCT FROM D.EMBARGO_UNTIL")[0]
    voc = scalar(conn, "SELECT COUNT(*) FROM NEEDLE.TERM_DF")[0]
    pub_voc = scalar(conn, f"SELECT COUNT(DISTINCT TERM) FROM NEEDLE.POSTING WHERE {PUBLIC}")[0]
    df_bad = scalar(conn, "SELECT COUNT(*) FROM NEEDLE.TERM_DF T LEFT JOIN (SELECT TERM, COUNT(*) AS C FROM "
                          f"NEEDLE.POSTING WHERE {PUBLIC} GROUP BY TERM) V ON V.TERM = T.TERM "
                          "WHERE V.C IS NULL OR V.C <> T.DF")[0]
    n, avgdl, avg_idf = scalar(conn, "SELECT N, AVGDL, AVG_IDF FROM NEEDLE.CORPUS_STATS WHERE ID = 1")
    pub_docs = scalar(conn, f"SELECT COUNT(DISTINCT ADV_ID) FROM NEEDLE.POSTING WHERE {PUBLIC}")[0]
    emb_docs = scalar(conn, f"SELECT COUNT(*) FROM NEEDLE.ADV_DOC WHERE NOT {PUBLIC}")[0]
    ok = cnt == exp["postings"] and drift == 0 and voc == pub_voc and df_bad == 0 and n == pub_docs
    print(f"CHECK db: postings={cnt} acl_drift_vs_adv_doc={drift} TERM_DF={voc} public_terms={pub_voc} "
          f"df_not_public_count={df_bad} N={n} public_docs={pub_docs} embargoed_docs={emb_docs} "
          f"AVGDL={avgdl!r} AVG_IDF={avg_idf!r}", flush=True)
    print(f"CHECK py (full corpus): postings={exp['postings']} vocab={exp['vocab']} N={exp['n']} "
          f"AVGDL={exp['avgdl']!r} AVG_IDF={exp['avg_idf']!r}", flush=True)
    print("CHECK", "MATCH" if ok else "MISMATCH", flush=True)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="/tmp/needle")
    ap.add_argument("--steps", default="ddl,load,post,check")
    ap.add_argument("--sample", action="store_true",
                    help=f"load the postings of the frozen sample in {FIXTURES} (sets --dir)")
    a = ap.parse_args()
    if a.sample:
        a.dir = FIXTURES
        print(f"SAMPLE MODE: loading the frozen fixtures in {a.dir}", flush=True)
    steps = set(a.steps.split(","))
    sql_path = os.path.join(a.dir, "02_bm25.sql")
    if not os.path.exists(sql_path):
        sql_path = os.path.join(HERE, "..", "sql", "02_bm25.sql")
    pre, marker, post = open(sql_path, encoding="utf-8").read().partition("\n-- @POST_LOAD\n")
    if not marker:
        sys.exit("02_bm25.sql has no '-- @POST_LOAD' marker line")
    conn = connect()
    try:
        t = time.time()
        if "ddl" in steps:
            run_ddl(conn, pre, "ddl")
        if "load" in steps:
            load(conn, a.dir)
        if "post" in steps:
            run_ddl(conn, post, "post")
        if "check" in steps and not check(conn, a.dir):
            sys.exit(3)
        print(f"ALL DONE {time.time()-t:.1f}s", flush=True)
    finally:
        ibm_db.close(conn)


if __name__ == "__main__":
    main()
