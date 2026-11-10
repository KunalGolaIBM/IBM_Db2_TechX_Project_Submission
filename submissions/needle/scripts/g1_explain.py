#!/usr/bin/env python3
"""G1 evidence: does Db2 use NEEDLE.ADV_DOC_VIX for FETCH APPROX? Runs INSIDE the codespace.

python3 + ibm_db, credentials from env (DB2_PASSWORD required; see load_in_codespace.py).
Input : /tmp/needle/g1_queries.json  (20 query vectors embedded on the PC with "search_query: ")
Output: stdout (markdown) -- the PC wrapper saves it to docs/evidence/.
For each variant: EXPLAIN PLAN FOR -> operators from DB2INST1.EXPLAIN_OPERATOR / EXPLAIN_STREAM /
EXPLAIN_OBJECT for that explain instance, plus db2exfmt text from inside the db2 container.
Then times 20 queries per variant (k is a literal 10) and APPROX-vs-EXACT overlap@10.
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ibm_db  # noqa: E402
from load_in_codespace import connect  # noqa: E402

K = 10
BASE = "SELECT ADV_ID FROM NEEDLE.ADV_DOC ORDER BY VECTOR_DISTANCE(EMB, {qv}, COSINE) FETCH {mode} FIRST {k} ROWS ONLY"
BOUND = "VECTOR(CAST(? AS CLOB(100K)), 768, FLOAT32)"


def vec_text(v):
    # The literal-vector EXPLAIN variants inline this text into SQL, so every element is forced through float()
    # (a value with a quote or any non-number raises here) and NaN/Infinity are rejected (internal review finding 3).
    vals = [float(x) for x in v]
    if len(vals) != 768:
        raise ValueError(f"expected 768 floats, got {len(vals)}")
    return json.dumps(vals, separators=(",", ":"), allow_nan=False)


def literal(v):
    return f"VECTOR('{vec_text(v)}', 768, FLOAT32)"


def q(sql_text, conn, params=None):
    if params is None:
        st = ibm_db.exec_immediate(conn, sql_text)
    else:
        st = ibm_db.prepare(conn, sql_text)
        ibm_db.execute(st, tuple(params))
    out, row = [], ibm_db.fetch_tuple(st)
    while row:
        out.append(row)
        row = ibm_db.fetch_tuple(st)
    return out


def explain(conn, stmt_text, tag):
    ibm_db.exec_immediate(conn, "EXPLAIN PLAN SET QUERYTAG = '" + tag + "' FOR " + stmt_text)
    ibm_db.commit(conn)
    inst = q("SELECT EXPLAIN_TIME, SOURCE_NAME, SOURCE_SCHEMA, SOURCE_VERSION, EXPLAIN_LEVEL, STMTNO, SECTNO "
             "FROM DB2INST1.EXPLAIN_STATEMENT WHERE QUERYTAG = ? AND EXPLAIN_LEVEL = 'P' "
             "ORDER BY EXPLAIN_TIME DESC FETCH FIRST 1 ROW ONLY", conn, [tag.ljust(20)[:20]])
    if not inst:
        inst = q("SELECT EXPLAIN_TIME, SOURCE_NAME, SOURCE_SCHEMA, SOURCE_VERSION, EXPLAIN_LEVEL, STMTNO, SECTNO "
                 "FROM DB2INST1.EXPLAIN_STATEMENT WHERE EXPLAIN_LEVEL = 'P' ORDER BY EXPLAIN_TIME DESC "
                 "FETCH FIRST 1 ROW ONLY", conn)
    et = inst[0][0]
    ops = q("SELECT OPERATOR_ID, OPERATOR_TYPE, TOTAL_COST FROM DB2INST1.EXPLAIN_OPERATOR "
            "WHERE EXPLAIN_TIME = ? ORDER BY OPERATOR_ID", conn, [et])
    streams = q("SELECT SOURCE_ID, SOURCE_TYPE, TARGET_ID, TARGET_TYPE, OBJECT_SCHEMA, OBJECT_NAME, STREAM_COUNT "
                "FROM DB2INST1.EXPLAIN_STREAM WHERE EXPLAIN_TIME = ? AND OBJECT_NAME IS NOT NULL "
                "ORDER BY TARGET_ID", conn, [et])
    objs = q("SELECT OBJECT_SCHEMA, OBJECT_NAME, OBJECT_TYPE FROM DB2INST1.EXPLAIN_OBJECT "
             "WHERE EXPLAIN_TIME = ? ORDER BY OBJECT_NAME", conn, [et])
    total = q("SELECT TOTAL_COST FROM DB2INST1.EXPLAIN_STATEMENT WHERE EXPLAIN_TIME = ? AND EXPLAIN_LEVEL = 'P'",
              conn, [et])
    return et, ops, streams, objs, (total[0][0] if total else None)


def exfmt(et):
    """db2exfmt for one explain instance, run as db2inst1 inside the db2 container."""
    ts = et.strftime("%Y-%m-%d-%H.%M.%S.%f") if hasattr(et, "strftime") else str(et)
    cmd = ["docker", "exec", "-u", "db2inst1", "db2", "bash", "-lc",
           f"cd /tmp && rm -f /tmp/g1_exfmt.txt; db2exfmt -d VECDB -e DB2INST1 -w {ts} -n % -s % -# 0 -g TIC "
           f"-o /tmp/g1_exfmt.txt >/dev/null 2>&1; cat /tmp/g1_exfmt.txt"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return r.stdout
    except Exception as e:  # noqa: BLE001
        return f"db2exfmt failed: {e}"


def plan_section(text):
    """Keep the 'Access Plan:' graph and the operator/object summary of db2exfmt output."""
    if not text:
        return "(no db2exfmt output)"
    lines = text.splitlines()
    keep, on = [], False
    for ln in lines:
        if ln.startswith("Access Plan:"):
            on = True
        if on:
            keep.append(ln)
            if ln.startswith("Operator Symbols") or ln.startswith("Plan Details:"):
                break
    head = [ln for ln in lines if ln.startswith(("Original Statement", "Optimized Statement"))]
    return "\n".join(keep) if keep else "\n".join(lines[:200])


def time_variant(conn, stmt_text, vecs, bound):
    lat, results = [], []
    st = ibm_db.prepare(conn, stmt_text) if bound else None
    for v in vecs:
        t0 = time.perf_counter()
        if bound:
            ibm_db.execute(st, (vec_text(v),))
            rows, row = [], ibm_db.fetch_tuple(st)
            while row:
                rows.append(row[0])
                row = ibm_db.fetch_tuple(st)
        else:
            rows = [r[0] for r in q(stmt_text.format(qv=literal(v)), conn)]
        lat.append((time.perf_counter() - t0) * 1000)
        results.append(rows)
    return lat, results


def fmt_lat(lat):
    s = sorted(lat)
    p95 = s[min(len(s) - 1, int(round(0.95 * (len(s) - 1))))]
    return f"n={len(s)} median={statistics.median(s):.1f} ms p95={p95:.1f} ms min={s[0]:.1f} max={s[-1]:.1f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries", default="/tmp/needle/g1_queries.json")
    ap.add_argument("--label", default="baseline")
    ap.add_argument("--no-timing", action="store_true")
    ap.add_argument("--extra", action="store_true", help="k as parameter marker + filtered (ROW_BUCKET) variants")
    args = ap.parse_args()
    qs = json.load(open(args.queries, encoding="utf-8"))
    vecs = [x["vec"] for x in qs]
    conn = connect()
    try:
        print(f"## G1 run: {args.label}\n")
        print("```")
        for r in q("SELECT COUNT(*) FROM NEEDLE.ADV_DOC", conn):
            print("ADV_DOC rows:", r[0])
        for r in q("SELECT INDNAME, INDEXTYPE, COLNAMES, NLEAF, STATS_TIME FROM SYSCAT.INDEXES "
                   "WHERE TABSCHEMA='NEEDLE' AND TABNAME='ADV_DOC'", conn):
            print("index:", r)
        for r in q("SELECT CARD, NPAGES, STATS_TIME FROM SYSCAT.TABLES WHERE TABSCHEMA='NEEDLE' AND TABNAME='ADV_DOC'", conn):
            print("table stats CARD/NPAGES/STATS_TIME:", r)
        for r in q("SELECT NULLS FROM SYSCAT.COLUMNS WHERE TABSCHEMA='NEEDLE' AND TABNAME='ADV_DOC' AND COLNAME='EMB'", conn):
            print("EMB nullable:", r[0])
        print("```\n")

        variants = [
            ("APPROX_literal", BASE.format(qv=literal(vecs[0]), mode="APPROX", k=K)),
            ("EXACT_literal", BASE.format(qv=literal(vecs[0]), mode="EXACT", k=K)),
            ("APPROX_bound", BASE.format(qv=BOUND, mode="APPROX", k=K)),
            ("EXACT_bound", BASE.format(qv=BOUND, mode="EXACT", k=K)),
        ]
        if args.extra:
            filt = "SELECT ADV_ID FROM NEEDLE.ADV_DOC WHERE ROW_BUCKET < 25 ORDER BY VECTOR_DISTANCE(EMB, {qv}, COSINE) FETCH {mode} FIRST {k} ROWS ONLY"
            variants = [
                ("APPROX_k_param", "SELECT ADV_ID FROM NEEDLE.ADV_DOC ORDER BY VECTOR_DISTANCE(EMB, "
                 + BOUND + ", COSINE) FETCH APPROX FIRST ? ROWS ONLY"),
                ("APPROX_bound_where_bucket25", filt.format(qv=BOUND, mode="APPROX", k=K)),
                ("EXACT_bound_where_bucket25", filt.format(qv=BOUND, mode="EXACT", k=K)),
            ]
        verdict = {}
        for name, sql in variants:
            et, ops, streams, objs, total = explain(conn, sql, "G1" + name[:14])
            uses_vix = any((s[5] or "").strip() == "ADV_DOC_VIX" for s in streams) or \
                any((o[1] or "").strip() == "ADV_DOC_VIX" for o in objs)
            verdict[name] = uses_vix
            shown = sql if "?" in sql else sql.split("VECTOR('")[0] + "VECTOR('<768 floats>', 768, FLOAT32), COSINE) FETCH " + sql.split(" FETCH ")[1]
            print(f"### {name}\n\n```sql\n{shown}\n```\n")
            print(f"EXPLAIN_TIME {et}  total cost {total}  **uses ADV_DOC_VIX: {uses_vix}**\n")
            print("```\nOPERATOR_ID OPERATOR_TYPE TOTAL_COST")
            for o in ops:
                print(f"{o[0]:>11} {o[1].strip():<13} {o[2]}")
            print("\nEXPLAIN_STREAM rows with an object (SRC_ID SRC_TYPE -> TGT_ID TGT_TYPE OBJECT ROWS):")
            for s in streams:
                print(f"  {s[0]} {s[1]} -> {s[2]} {s[3]}  {(s[4] or '').strip()}.{(s[5] or '').strip()}  {s[6]}")
            print("\nEXPLAIN_OBJECT:")
            for o in objs:
                print(f"  {o[0].strip()}.{o[1].strip()} {o[2]}")
            print("```\n")
            print("db2exfmt access plan:\n\n```")
            print(plan_section(exfmt(et)))
            print("```\n")

        if args.extra and not args.no_timing:
            print("### Filtered ANN (WHERE ROW_BUCKET < b), 20 queries, k literal 10\n\n```")
            for b in (100, 50, 25, 10, 5):
                fs = ("SELECT ADV_ID FROM NEEDLE.ADV_DOC WHERE ROW_BUCKET < " + str(int(b)) +
                      " ORDER BY VECTOR_DISTANCE(EMB, " + BOUND + ", COSINE) FETCH {m} FIRST 10 ROWS ONLY")
                la, ra = time_variant(conn, fs.format(m="APPROX"), vecs, True)
                le, re_ = time_variant(conn, fs.format(m="EXACT"), vecs, True)
                rec = [len(set(a) & set(e)) / max(1, len(e)) for a, e in zip(ra, re_)]
                nret = [len(a) for a in ra]
                print(f"bucket<{b:<3} APPROX {fmt_lat(la)} | EXACT {fmt_lat(le)} | "
                      f"recall@10 mean={statistics.mean(rec):.3f} min={min(rec):.2f} | APPROX rows returned min={min(nret)}")
            print("```\n")
        elif not args.no_timing:
            print("### Timing (20 triage queries, k literal 10, wall clock from python3+ibm_db inside the codespace)\n")
            # warm-up
            time_variant(conn, BASE.format(qv=BOUND, mode="APPROX", k=K), vecs[:2], True)
            time_variant(conn, BASE.format(qv=BOUND, mode="EXACT", k=K), vecs[:2], True)
            res = {}
            print("```")
            for name, sql, bound in [
                ("APPROX_bound", BASE.format(qv=BOUND, mode="APPROX", k=K), True),
                ("EXACT_bound", BASE.format(qv=BOUND, mode="EXACT", k=K), True),
                ("APPROX_literal", BASE.replace("{mode}", "APPROX").replace("{k}", str(K)), False),
                ("EXACT_literal", BASE.replace("{mode}", "EXACT").replace("{k}", str(K)), False),
            ]:
                lat, rows = time_variant(conn, sql, vecs, bound)
                res[name] = rows
                print(f"{name:<15} {fmt_lat(lat)}")
            ov = [len(set(a) & set(b)) / K for a, b in zip(res["APPROX_bound"], res["EXACT_bound"])]
            print(f"overlap@10 APPROX_bound vs EXACT_bound: mean={statistics.mean(ov):.3f} min={min(ov):.2f}")
            ov2 = [len(set(a) & set(b)) / K for a, b in zip(res["APPROX_literal"], res["EXACT_literal"])]
            print(f"overlap@10 APPROX_literal vs EXACT_literal: mean={statistics.mean(ov2):.3f} min={min(ov2):.2f}")
            print("```\n")
        print("Verdict per variant (uses ADV_DOC_VIX):", json.dumps(verdict))
    finally:
        ibm_db.close(conn)


if __name__ == "__main__":
    main()
