#!/usr/bin/env python3
"""Bulk-load NEEDLE.ADV_RAW / ADV_DOC / ADV_ALIAS / ADV_AFFECTED. Runs INSIDE the codespace.

Pure python3 + ibm_db. Connects to localhost:50000 (the db2 container port) with credentials
from environment variables only: DB2_PASSWORD (required), DB2_USER (default db2inst1),
DB2_DATABASE (default VECDB), DB2_HOST (default localhost), DB2_PORT (default 50000).

Inputs in --dir (default /tmp/needle): 01_schema.sql, docs.jsonl, emb.jsonl.gz, raw.jsonl.gz.

Re-runnable: insert-if-absent. Existing ADV_IDs are read first and skipped, so ids stay stable
and a second run inserts nothing. ADV_ALIAS / ADV_AFFECTED rows are batched per advisory, so an
advisory's rows always commit together. executemany in batches of ~500 rows, commit per batch.

Usage: python3 load_in_codespace.py [--dir D] [--steps ddl,raw,doc,alias,affected,post]
       python3 load_in_codespace.py --sample     # the frozen ~2,000-advisory sample in eval/fixtures (no Ollama)
A file missing from --dir is also looked for as <name>.gz, and SQL files fall back to ../sql/ (repository layout).
"""
import argparse
import gzip
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import ibm_db

BATCH = 500
IGNORABLE = ("SQL0601N", "SQL0624N", "SQL0605W", "SQL20393N")  # already exists / duplicate index
HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.normpath(os.path.join(HERE, "..", "eval", "fixtures"))


def find(d, name):
    """Path of ``name`` in ``d`` (or ``name``.gz); SQL files fall back to ../sql/ next to this script."""
    for cand in (os.path.join(d, name), os.path.join(d, name + ".gz"), os.path.join(HERE, "..", "sql", name)):
        if os.path.exists(cand):
            return cand
    sys.exit(f"{name} not found in {d}")


def open_text(path):
    return gzip.open(path, "rt", encoding="utf-8") if path.endswith(".gz") else open(path, encoding="utf-8")


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
    """Split a SQL file into statements; drop '--' comment lines."""
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("--")]
    body = "\n".join(lines)
    return [s.strip() for s in body.split(";") if s.strip()]


def run_ddl(conn, text, label):
    for stmt in split_sql(text):
        t0 = time.time()
        try:
            ibm_db.exec_immediate(conn, stmt)
            ibm_db.commit(conn)
            print(f"[{label}] OK {time.time()-t0:.1f}s: {stmt.splitlines()[0][:90]}", flush=True)
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            ibm_db.rollback(conn)
            if any(code in msg for code in IGNORABLE):
                print(f"[{label}] exists, skipped: {stmt.splitlines()[0][:90]}", flush=True)
            else:
                print(f"[{label}] FAILED: {stmt.splitlines()[0][:90]}\n  {msg[:400]}", flush=True)
                raise


def existing_ids(conn, sql):
    ids = set()
    stmt = ibm_db.exec_immediate(conn, sql)
    row = ibm_db.fetch_tuple(stmt)
    while row:
        ids.add(row[0])
        row = ibm_db.fetch_tuple(stmt)
    return ids


_TS = re.compile(r"^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2}):(\d{2})(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$")


def db2_ts(s):
    """OSV RFC3339 -> Db2 'YYYY-MM-DD-HH.MM.SS.ffffff' (UTC). None if empty/unparseable."""
    if not s:
        return None
    m = _TS.match(s.strip())
    if not m:
        return None
    date, hh, mi, ss, frac, tz = m.groups()
    us = int(((frac or ".0")[1:] + "000000")[:6])
    dt = datetime.strptime(f"{date} {hh}:{mi}:{ss}", "%Y-%m-%d %H:%M:%S").replace(microsecond=us)
    if tz and tz != "Z":
        sign = 1 if tz[0] == "+" else -1
        tzd = tz[1:].replace(":", "")
        off = sign * (int(tzd[:2]) * 60 + int(tzd[2:]))
        dt = dt.replace(tzinfo=timezone.utc).timestamp() - off * 60
        dt = datetime.fromtimestamp(dt, tz=timezone.utc).replace(tzinfo=None)
    return dt.strftime("%Y-%m-%d-%H.%M.%S.%f")


def trunc_bytes(s, n):
    if s is None:
        return None
    b = s.encode("utf-8")
    if len(b) <= n:
        return s
    return b[:n].decode("utf-8", errors="ignore")


def join_packages(pkgs, n=4000):
    out = ""
    for p in pkgs:
        cand = p if not out else out + ", " + p
        if len(cand.encode("utf-8")) > n:
            break
        out = cand
    return out or None


def flush(conn, stmt, rows, label, stats):
    if not rows:
        return
    try:
        ibm_db.execute_many(stmt, tuple(rows))
    except Exception as e:  # noqa: BLE001
        # Fallback for driver-side array binding issues: row-by-row in the same transaction.
        if not stats.get("fallback_logged"):
            print(f"[{label}] execute_many failed ({str(e)[:200]}); falling back to per-row execute", flush=True)
            stats["fallback_logged"] = True
        ibm_db.rollback(conn)
        for r in rows:
            ibm_db.execute(stmt, r)
    ibm_db.commit(conn)
    stats["rows"] += len(rows)
    stats["batches"] += 1
    if stats["batches"] % 50 == 0:
        el = time.time() - stats["t0"]
        print(f"[{label}] {stats['rows']} rows {el:.0f}s ({stats['rows']/max(el,1e-9):.0f} rows/s)", flush=True)
    rows.clear()


def new_stats():
    return {"rows": 0, "batches": 0, "t0": time.time()}


def load_raw(conn, d):
    have = existing_ids(conn, "SELECT ADV_ID FROM NEEDLE.ADV_RAW")
    stmt = ibm_db.prepare(conn, "INSERT INTO NEEDLE.ADV_RAW (ADV_ID, RAW, SHA256) VALUES (?, ?, ?)")
    st, rows = new_stats(), []
    with gzip.open(os.path.join(d, "raw.jsonl.gz"), "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["adv_id"] in have:
                continue
            rows.append((r["adv_id"], r["raw"], r["raw_sha256"]))
            if len(rows) >= BATCH:
                flush(conn, stmt, rows, "raw", st)
    flush(conn, stmt, rows, "raw", st)
    return st, len(have)


def load_docs_meta(d):
    docs = {}
    with open_text(find(d, "docs.jsonl")) as f:
        for line in f:
            x = json.loads(line)
            if x["withdrawn"]:
                continue
            docs[x["adv_id"]] = x
    return docs


def load_doc(conn, d, docs):
    have = existing_ids(conn, "SELECT ADV_ID FROM NEEDLE.ADV_DOC")
    stmt = ibm_db.prepare(conn, (
        "INSERT INTO NEEDLE.ADV_DOC (ADV_ID, CANON_ID, KIND, SUMMARY, DETAILS, PACKAGES, PUBLISHED, MODIFIED, "
        "CVSS, DOC_LEN, ROW_BUCKET, EMB) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
        "VECTOR(CAST(? AS CLOB(100K)), 768, FLOAT32))"))
    st, rows, missing_emb = new_stats(), [], 0
    embedded = set()
    with gzip.open(os.path.join(d, "emb.jsonl.gz"), "rt", encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            aid = e["adv_id"]
            embedded.add(aid)
            if aid in have or aid not in docs:
                continue
            x = docs[aid]
            rows.append((
                aid, x["canon_id"], x["kind"],
                trunc_bytes(x["summary"], 2000), x["details"], join_packages(x["packages"]),
                db2_ts(x["published"]), db2_ts(x["modified"]),
                trunc_bytes(x["cvss"], 200), int(x["doc_len"]), int(x["row_bucket"]),
                json.dumps(e["emb"], separators=(",", ":")),
            ))
            if len(rows) >= BATCH:
                flush(conn, stmt, rows, "doc", st)
    flush(conn, stmt, rows, "doc", st)
    missing_emb = sum(1 for a in docs if a not in embedded)
    return st, len(have), missing_emb


def load_child(conn, docs, table, sql, rows_of, label):
    have = existing_ids(conn, f"SELECT DISTINCT ADV_ID FROM {table}")
    stmt = ibm_db.prepare(conn, sql)
    st, rows = new_stats(), []
    for aid in sorted(docs):
        if aid in have:
            continue
        rows.extend(rows_of(docs[aid]))
        if len(rows) >= BATCH:  # whole advisory per commit
            flush(conn, stmt, rows, label, st)
    flush(conn, stmt, rows, label, st)
    return st, len(have)


def count(conn, table):
    stmt = ibm_db.exec_immediate(conn, f"SELECT COUNT(*) FROM {table}")
    return ibm_db.fetch_tuple(stmt)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="/tmp/needle")
    ap.add_argument("--steps", default="ddl,raw,doc,alias,affected,post")
    ap.add_argument("--sample", action="store_true",
                    help=f"load the frozen sample in {FIXTURES} (sets --dir; no Ollama, no data/ folder)")
    args = ap.parse_args()
    if args.sample:
        args.dir = FIXTURES
        print(f"SAMPLE MODE: loading the frozen fixtures in {args.dir}", flush=True)
    steps = set(args.steps.split(","))
    ddl_pre, _, ddl_post = open(find(args.dir, "01_schema.sql"), encoding="utf-8").read().partition("\n-- @POST_LOAD\n")

    conn = connect()
    try:
        t_all = time.time()
        if "ddl" in steps:
            run_ddl(conn, ddl_pre, "ddl")
        docs = load_docs_meta(args.dir) if steps & {"doc", "alias", "affected"} else {}
        for step in ("raw", "doc", "alias", "affected"):
            if step not in steps:
                continue
            t0 = time.time()
            extra = ""
            if step == "raw":
                st, had = load_raw(conn, args.dir)
                table = "NEEDLE.ADV_RAW"
            elif step == "doc":
                st, had, miss = load_doc(conn, args.dir, docs)
                table, extra = "NEEDLE.ADV_DOC", f" non_withdrawn_without_embedding={miss}"
            elif step == "alias":
                st, had = load_child(
                    conn, docs, "NEEDLE.ADV_ALIAS",
                    "INSERT INTO NEEDLE.ADV_ALIAS (ADV_ID, ALIAS) VALUES (?, ?)",
                    lambda x: [(x["adv_id"], a) for a in x["aliases"] if len(a.encode()) <= 64], "alias")
                table = "NEEDLE.ADV_ALIAS"
            else:
                st, had = load_child(
                    conn, docs, "NEEDLE.ADV_AFFECTED",
                    "INSERT INTO NEEDLE.ADV_AFFECTED (ADV_ID, ECOSYSTEM, PACKAGE, VERSION) VALUES (?, ?, ?, ?)",
                    lambda x: [(x["adv_id"], e, p, v) for e, p, v in x["affected"]], "affected")
                table = "NEEDLE.ADV_AFFECTED"
            print(f"LOADED {table}: inserted={st['rows']} skipped_existing_ids={had} "
                  f"time={time.time()-t0:.1f}s total_rows={count(conn, table)}{extra}", flush=True)
        if "post" in steps:
            t0 = time.time()
            run_ddl(conn, ddl_post, "post")
            print(f"POST_LOAD time={time.time()-t0:.1f}s", flush=True)
        print(f"ALL DONE {time.time()-t_all:.1f}s", flush=True)
    finally:
        ibm_db.close(conn)


if __name__ == "__main__":
    main()
