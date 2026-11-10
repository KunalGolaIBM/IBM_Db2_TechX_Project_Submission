#!/usr/bin/env python3
"""Run the BM25 keyword leg and NEEDLE.TRIAGE_MODE for prepared cases INSIDE the codespace (no tunnel latency).

Pure python3 + ibm_db. Credentials from environment variables only (DB2_PASSWORD required; DB2_USER, DB2_DATABASE,
DB2_HOST, DB2_PORT default to db2inst1 / VECDB / localhost / 50000).
Input : --cases (default /tmp/needle/triage_cases.json) from `scripts/triage_check.py prepare`.
Output: --out   (default /tmp/needle/triage_check_out.json), compared locally by `scripts/triage_check.py compare`.
Every SQL value is a bound parameter; the procedure/function names come from a fixed whitelist.
"""
import argparse
import json
import os
import statistics
import sys
import time

import ibm_db

KW_FUNCS = {"NEEDLE.BM25_SEARCH"}
PROCS = {"NEEDLE.TRIAGE_MODE": 5, "NEEDLE.TRIAGE": 4}


def connect():
    pw = os.environ.get("DB2_PASSWORD")
    if not pw:
        sys.exit("DB2_PASSWORD is not set")
    dsn = (f"DATABASE={os.environ.get('DB2_DATABASE', 'VECDB')};HOSTNAME={os.environ.get('DB2_HOST', 'localhost')};"
           f"PORT={os.environ.get('DB2_PORT', '50000')};PROTOCOL=TCPIP;UID={os.environ.get('DB2_USER', 'db2inst1')};"
           f"PWD={pw};")
    return ibm_db.connect(dsn, "", "")


def fetch_all(stmt):
    rows, r = [], ibm_db.fetch_tuple(stmt)
    while r:
        rows.append(list(r))
        r = ibm_db.fetch_tuple(stmt)
    return rows


def kw_search(conn, func, terms_json, depth):
    assert func in KW_FUNCS
    st = ibm_db.prepare(conn, f"SELECT ADV_ID, KW_SCORE, KW_RANK FROM TABLE({func}(CAST(? AS CLOB(32K)), ?)) AS B "
                              "ORDER BY KW_RANK")
    t = time.perf_counter()
    ibm_db.execute(st, (terms_json, depth))
    rows = fetch_all(st)
    return rows, (time.perf_counter() - t) * 1000


def call(conn, proc, args):
    assert proc in PROCS and len(args) == PROCS[proc]
    t = time.perf_counter()
    res = ibm_db.callproc(conn, proc, tuple(args))
    stmt = res[0] if isinstance(res, tuple) else res
    rows = fetch_all(stmt)
    return rows, (time.perf_counter() - t) * 1000


def dbi_check(cases, recs, k, depth):
    """needle.triage.call_triage over ibm_db_dbi must return the same rows as the ibm_db CALL."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
    import ibm_db_dbi
    from needle.triage import call_triage

    pw = os.environ["DB2_PASSWORD"]
    dsn = (f"DATABASE={os.environ.get('DB2_DATABASE', 'VECDB')};HOSTNAME={os.environ.get('DB2_HOST', 'localhost')};"
           f"PORT={os.environ.get('DB2_PORT', '50000')};PROTOCOL=TCPIP;UID={os.environ.get('DB2_USER', 'db2inst1')};"
           f"PWD={pw};")
    conn = ibm_db_dbi.connect(dsn, "", "")
    same = 0
    try:
        for c, rec in zip(cases, recs):
            hits = call_triage(conn, c["vec"], c["terms"], k=k, depth=depth, mode="HYBRID")
            same += [h.adv_id for h in hits] == [r[0] for r in rec["triage_mode_HYBRID"]]
    finally:
        conn.close()
    return {"cases": len(cases), "same_ids_as_ibm_db": same}


def summary(ms):
    ms = sorted(ms)
    return {"n": len(ms), "median_ms": round(statistics.median(ms), 2),
            "p95_ms": round(ms[min(len(ms) - 1, int(0.95 * len(ms)))], 2), "max_ms": round(ms[-1], 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="/tmp/needle/triage_cases.json")
    ap.add_argument("--out", default="/tmp/needle/triage_check_out.json")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--depth", type=int, default=100)
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--dbi-check", action="store_true", help="also run needle.triage.call_triage (ibm_db_dbi)")
    a = ap.parse_args()
    cases = json.load(open(a.cases, encoding="utf-8"))
    k, depth = int(a.k), int(a.depth)
    conn = connect()
    out = {"k": k, "depth": depth, "repeat": a.repeat, "cases": [], "timing": {}}
    times = {}
    try:
        for c in cases:
            terms = json.dumps(c["terms"], ensure_ascii=False)
            vec = json.dumps(c["vec"], separators=(",", ":"))
            rec = {"q": c["q"]}
            for rep in range(a.repeat + 1):  # rep 0 = warm-up, not timed
                runs = {"kw": kw_search(conn, "NEEDLE.BM25_SEARCH", terms, 10),
                        "triage": call(conn, "NEEDLE.TRIAGE", [vec, terms, k, depth])}
                for mode in ("HYBRID", "KW", "VEC"):
                    runs[f"triage_mode_{mode}"] = call(conn, "NEEDLE.TRIAGE_MODE", [vec, terms, k, depth, mode])
                for name, (rows, ms) in runs.items():
                    if rep == 0:
                        rec[name] = [[str(r[0]).strip()] + [None if v is None else float(v) for v in r[1:]]
                                     for r in rows]
                    else:
                        times.setdefault(name, []).append(ms)
            out["cases"].append(rec)
            print(f"done: {c['q'][:60]}", flush=True)
        out["timing"] = {name: summary(ms) for name, ms in sorted(times.items())}
        if a.dbi_check:
            out["dbi_check"] = dbi_check(cases[:5], out["cases"][:5], k, depth)
    finally:
        ibm_db.close(conn)
    json.dump(out, open(a.out, "w", encoding="utf-8"), indent=1)
    for name, s in out["timing"].items():
        print(f"TIMING {name:<28} {s}", flush=True)
    if "dbi_check" in out:
        print(f"DBI_CHECK {out['dbi_check']}", flush=True)


if __name__ == "__main__":
    main()
