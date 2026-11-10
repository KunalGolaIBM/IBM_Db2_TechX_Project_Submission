"""Print the real-data RCAC sweep tables (markdown) from eval/results/rcac_real_results.json (+ plan cache, triage, fit).

Every number is read from the JSON written by eval/rcac_sweep.py; nothing is typed by hand.
Run from needle/:  .venv\\Scripts\\python eval\\rcac_report.py > docs/evidence/rcac_real_tables.md
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "eval" / "results"
USERS = [("NDL_P10", 10), ("NDL_P25", 25), ("NDL_P50", 50), ("NDL_P75", 75), ("NDL_SENIOR", 100)]
DEPTHS = [10, 25, 50, 100, 200]


def f(x, nd=3):
    return "n/a" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


def plan_cell(p):
    if not p:
        return "n/a"
    idx = "IXSCAN VECIDX" if p["uses_vector_index"] else "no vector index (TBSCAN)"
    return f"{idx}; L={f(p['srchlsiz'])}; est={f(p['vector_ixscan_est_rows'], 0)}"


def ff_of(p, needle="ROW_BUCKET"):
    ffs = [x["ff"] for x in (p or {}).get("predicates", []) if needle in x["text"]]
    return ", ".join(f"{v:.4g}" for v in sorted(set(ffs))) if ffs else "n/a"


def main() -> None:
    d = json.loads((RES / "rcac_real_results.json").read_text())
    m = d["meta"]
    split = "all"
    print(f"Db2 {m['db2']} | {m['table']} | k={m['k']} | queries={m['n_queries']} (dev {m['n_dev']}, heldout "
          f"{m['n_heldout']}) | stats {m['stats']} | auto_runstats={m['auto_runstats']}\n")

    rc, base = d.get("rcac", {}), d.get("baseline_where_no_rcac", {})
    print(f"### Line-for-line: plain WHERE (DB2INST1, before RCAC) vs RCAC user, FETCH APPROX FIRST 10 ({split} queries)\n")
    print("| visible | WHERE literal: recall / rows / under-fill | plan (literal) | FF literal | WHERE subquery: recall / rows "
          "| plan (subquery) | RCAC user | RCAC: recall / rows / under-fill | RCAC plan (shared text) | FF permission | leaks |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    rplan = rc.get("plans_as_db2inst1", {})
    for user, p in USERS:
        b = base.get(str(p), {})
        bl, bs = b.get("approx10", {}), b.get("approx10_subquery", {})
        r = rc.get(user, {})
        a = r.get("approx10", {})
        leaks = sum(len(v.get("leaked_ids", [])) for v in r.values() if isinstance(v, dict))
        print(f"| {p}% ({f(r.get('visible_rows'))} rows) "
              f"| {f(bl.get(split, {}).get('recall_mean'))} / {f(bl.get(split, {}).get('returned_mean'), 2)} / "
              f"{f(bl.get(split, {}).get('underfill_rate'), 2)} | {plan_cell(bl.get('plan'))} | {ff_of(bl.get('plan'))} "
              f"| {f(bs.get(split, {}).get('recall_mean'))} / {f(bs.get(split, {}).get('returned_mean'), 2)} "
              f"| {plan_cell(bs.get('plan'))} | {user} "
              f"| {f(a.get(split, {}).get('recall_mean'))} / {f(a.get(split, {}).get('returned_mean'), 2)} / "
              f"{f(a.get(split, {}).get('underfill_rate'), 2)} | {plan_cell(rplan.get('approx10'))} "
              f"| {ff_of(rplan.get('approx10'))} | {leaks} |")

    print(f"\n### RCAC users: depth and search-list levers (recall / mean rows / under-fill rate / p50 ms; {split} queries)\n")
    conds = [f"approx{n}" for n in DEPTHS] + [f"approx{n}_L{max(50, 3 * n)}" for n in DEPTHS] + ["approx10_L200", "exact"]
    print("| condition | plan as DB2INST1 | " + " | ".join(u for u, _ in USERS) + " |")
    print("|---|---|" + "---|" * len(USERS))
    for c in conds:
        cells = []
        for u, _ in USERS:
            s = rc.get(u, {}).get(c, {}).get(split, {})
            err = s.get("errors", 0)
            cells.append(f"{f(s.get('recall_mean'))} / {f(s.get('returned_mean'), 1)} / {f(s.get('underfill_rate'), 2)} / "
                         f"{f(s.get('p50_ms'), 1)}" + (f" / {err} err" if err else ""))
        print(f"| {c} | {plan_cell(rplan.get(c))} | " + " | ".join(cells) + " |")

    print("\n### Oracle and identity checks\n")
    print("| user | SESSION_USER, CURRENT USER | visible rows | visible fraction | user EXACT == admin EXACT + explicit WHERE |")
    print("|---|---|---|---|---|")
    for u, _ in USERS:
        r = rc.get(u, {})
        print(f"| {u} | {r.get('session_user')} | {r.get('visible_rows')} | {r.get('visible_fraction')} | "
              f"{r.get('oracle_equal_queries')} / {m['n_queries']} |")

    if "router_heldout" in d:
        rh = d["router_heldout"]
        print(f"\n### Router on the held-out split only (config fitted on dev: {rh['config']})\n")
        print("| user | choice | recall@10 | mean rows | under-fill | EXACT fallbacks | errors | p50 ms | p95 ms | leaks | "
              "APPROX 10 on the same queries: recall / rows |")
        print("|---|---|---|---|---|---|---|---|---|---|---|")
        for u, _ in USERS:
            r = rh[u]
            s = r["strategy"]
            a = rc.get(u, {}).get("approx10", {}).get("heldout", {})
            print(f"| {u} | {s['mode']} {s['depth']}" + (f", L={s['search_list_size']}" if s.get("search_list_size") else "")
                  + f" | {f(r['all']['recall_mean'])} | {f(r['all']['returned_mean'], 2)} | {f(r['all']['underfill_rate'], 2)} "
                  f"| {r['fallbacks']} | {r['all'].get('errors', 0)} | {f(r['all']['p50_ms'], 1)} | {f(r['all']['p95_ms'], 1)} "
                  f"| {len(r['leaked_ids'])} | {f(a.get('recall_mean'))} / {f(a.get('returned_mean'), 2)} |")

    pc = RES / "rcac_plancache.json"
    if pc.exists():
        p = json.loads(pc.read_text())
        print("\n### Package cache after each user (FLUSH PACKAGE CACHE DYNAMIC before each order)\n")
        print("| order | after user | cache entries | executable_id (last 16 hex) | executions | +rows_read | +rows_returned |")
        print("|---|---|---|---|---|---|---|")
        for run in p["runs"]:
            for st in run["steps"]:
                for e in st["cache_entries"]:
                    print(f"| {run['order']} | {st['user']} | {len(st['cache_entries'])} | {e['executable_id'][-16:]} | "
                          f"{e['num_executions']} (+{e['delta_executions']}) | {e['delta_rows_read']} | "
                          f"{e['delta_rows_returned']} |")
            print(f"| {run['order']} | distinct executable ids | {len(run['distinct_executable_ids'])} | | | | |")

    tr = RES / "rcac_triage.json"
    if tr.exists():
        t = json.loads(tr.read_text())
        print("\n### NEEDLE.TRIAGE_MODE(..., 'VEC') as each user, k = 10, 20 G1 queries\n")
        print("| user | depth 10: mean rows / queries < 10 | depth 100: mean rows / queries < 10 |")
        print("|---|---|---|")
        for u, _ in USERS:
            r = t["users"].get(u, {})
            a, b = r.get("vec_depth10", {}), r.get("vec_depth100", {})
            print(f"| {u} | {a.get('rows_mean')} / {a.get('underfill')} | {b.get('rows_mean')} / {b.get('underfill')} |")
        for k, p in t["plans_as_db2inst1"].items():
            print(f"\nTRIAGE fused HYBRID statement, {k}: {plan_cell(p)}; operators {p['operators']}")


if __name__ == "__main__":
    main()
