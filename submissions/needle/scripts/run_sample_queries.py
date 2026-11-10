#!/usr/bin/env python3
"""Sample mode, last step: run NEEDLE.TRIAGE for the frozen demo queries in eval/fixtures (no Ollama).

The query vectors in eval/fixtures/queries.jsonl.gz were computed once with Ollama nomic-embed-text; this script
only reads them. Run from the needle/ folder after the sample load (README, "Sample mode"):
    PYTHONPATH=src python scripts/run_sample_queries.py [--user NDL_JUNIOR] [--k 10] [--depth 50]

It prints, per query, the fused top hits (keyword rank, vector rank) as the analyst user (RCAC applies), whether a
ground-truth advisory is in the top k (queries taken from the frozen eval slices), the exposure join for the first
query, the visible row count per user, and the access path Db2 chose for the vector leg at this table size.
Connection settings and passwords come from needle/.env or the environment (DB2_*, NDL_*_PASSWORD).
Exit code 0 = every statement ran; retrieval misses are reported, not treated as errors.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from needle.sbom import _env, fetch_exposure, password_for  # noqa: E402
from needle.triage import call_triage, connect  # noqa: E402

FIXTURES = ROOT / "eval" / "fixtures"
VEC_LEG = ("SELECT ADV_ID FROM NEEDLE.ADV_DOC "
           "ORDER BY VECTOR_DISTANCE(EMB, VECTOR(CAST(? AS CLOB(100K)), 768, FLOAT32), COSINE) "
           "FETCH APPROX FIRST 10 ROWS ONLY")


def scalar(conn, sql, params=()):
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        return cur.fetchone()[0]
    finally:
        cur.close()


def packages(conn, ids):
    if not ids:
        return {}
    cur = conn.cursor()
    try:
        cur.execute("SELECT ADV_ID, PACKAGES FROM NEEDLE.ADV_DOC WHERE ADV_ID IN (%s)" % ",".join("?" * len(ids)),
                    tuple(ids))
        return {str(a).strip(): (p or "") for a, p in cur.fetchall()}
    finally:
        cur.close()


def vector_leg_plan(admin, qvec_json):
    """EXPLAIN the vector leg (k literal) and return the operators and the objects Db2 chose."""
    cur = admin.cursor()
    try:
        cur.execute("EXPLAIN PLAN FOR " + VEC_LEG, (qvec_json,))
        for schema in (str(_env().get("DB2_USER", "db2inst1")).upper(), "SYSTOOLS"):
            try:
                cur.execute(f"SELECT MAX(EXPLAIN_TIME) FROM {schema}.EXPLAIN_OPERATOR")
                t = cur.fetchone()[0]
            except Exception:  # noqa: BLE001  explain tables live in one of the two schemas
                continue
            cur.execute(f"SELECT OPERATOR_TYPE FROM {schema}.EXPLAIN_OPERATOR WHERE EXPLAIN_TIME = ? "
                        "ORDER BY OPERATOR_ID", (t,))
            ops = [r[0].strip() for r in cur.fetchall()]
            cur.execute(f"SELECT DISTINCT RTRIM(OBJECT_SCHEMA) || '.' || RTRIM(OBJECT_NAME) FROM {schema}.EXPLAIN_OBJECT "
                        "WHERE EXPLAIN_TIME = ? ORDER BY 1", (t,))
            objs = [r[0] for r in cur.fetchall()]
            return ops, objs
        return None, None
    finally:
        cur.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="NDL_JUNIOR", help="analyst user for TRIAGE (RCAC applies)")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--depth", type=int, default=50)
    a = ap.parse_args()

    with gzip.open(FIXTURES / "queries.jsonl.gz", "rt", encoding="utf-8") as f:
        queries = [json.loads(x) for x in f]
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    print(f"SAMPLE MODE: {len(queries)} queries from eval/fixtures/queries.jsonl.gz, precomputed with "
          f"{manifest['query_embedding']['model']} (no Ollama call); corpus sample = {manifest['advisories']} advisories")

    env = _env()
    admin_user = env.get("DB2_USER", "db2inst1")
    users = [admin_user.upper(), "NDL_SENIOR", "NDL_JUNIOR", "NDL_P10"]
    counts = {}
    for u in users:
        pw = password_for(u, env)
        if not pw:
            counts[u] = "no password in .env"
            continue
        c = connect(u, pw)
        try:
            counts[u] = scalar(c, "SELECT COUNT(*) FROM NEEDLE.ADV_DOC")
        finally:
            c.close()
    print("visible rows in NEEDLE.ADV_DOC per user (RCAC):", "  ".join(f"{u}={n}" for u, n in counts.items()))

    pw = password_for(a.user, env)
    if not pw:
        sys.exit(f"no password for {a.user} in .env ({a.user}_PASSWORD)")
    conn = connect(a.user, pw)
    hits_gt, n_gt = 0, 0
    try:
        for i, q in enumerate(queries):
            t = time.perf_counter()
            hits = call_triage(conn, q["vec"], q["terms"], k=a.k, depth=a.depth, mode="HYBRID")
            ms = (time.perf_counter() - t) * 1000
            pk = packages(conn, [h.adv_id for h in hits[:3]])
            print(f"\n[{q['qid']}] {q['query'][:110]}{'...' if len(q['query']) > 110 else ''}")
            print(f"  user={a.user} k={a.k} depth={a.depth} terms={len(q['terms'])} rows={len(hits)} db_call={ms:.0f} ms")
            for r, h in enumerate(hits[:3], 1):
                print(f"  {r:>2} {h.adv_id:<22} rrf={h.rrf:.5f} kw_rank={h.kw_rank} vec_rank={h.vec_rank} "
                      f"packages={pk.get(h.adv_id, '')[:60]}")
            if q.get("gt"):
                n_gt += 1
                ranks = [r for r, h in enumerate(hits, 1) if h.adv_id in set(q["gt"])]
                hits_gt += bool(ranks)
                print(f"  ground truth {q['gt']}: in top {a.k} = {'yes, rank ' + str(ranks[0]) if ranks else 'NO'}")
            if i == 0:
                exp = fetch_exposure(conn.conn_handler, [h.adv_id for h in hits])
                aff = [e for e in exp if e.get("STATUS") == "AFFECTED"]
                print(f"  exposure join on the top {len(hits)} ids: {len(exp)} rows, {len(aff)} AFFECTED, services "
                      f"{sorted({e['SERVICE_ID'] for e in aff})}")
                for e in aff[:3]:
                    print(f"    {e['SERVICE_ID']} {e['PACKAGE']}=={e.get('VERSION_NOW')} {e['ADV_ID']} "
                          f"exposed_since={e.get('EXPOSED_SINCE')}")
    finally:
        conn.close()

    admin = connect()
    try:
        ops, objs = vector_leg_plan(admin, json.dumps(queries[0]["vec"], separators=(",", ":")))
        n = scalar(admin, "SELECT COUNT(*) FROM NEEDLE.ADV_DOC")
    finally:
        admin.close()
    if ops is None:
        print("\nvector leg access path: EXPLAIN tables not found (skipped)")
    else:
        vix = any(o.endswith("ADV_DOC_VIX") for o in objs)
        print(f"\nvector leg access path at {n} rows (EXPLAIN, FETCH APPROX FIRST 10, literal k): operators={ops} "
              f"objects={objs} -> vector index {'USED' if vix else 'NOT used (cost-based choice at this size)'}")
    print(f"\nSAMPLE MODE OK: {len(queries)} queries ran; ground-truth queries with a hit in the top {a.k}: "
          f"{hits_gt}/{n_gt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
