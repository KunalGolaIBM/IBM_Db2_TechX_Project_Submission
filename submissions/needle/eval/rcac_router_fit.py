"""Fit the RCAC router thresholds (T, m) on the DEV split only, from measured per-query results.

Input : eval/results/rcac_real_results.json  ("rcac" section: per user, per condition, per query n_ret/ms/recall)
Output: eval/results/rcac_router_fit.json    (grid on dev + chosen T, m). The held-out split is NOT read here;
        the chosen config is then run live on the held-out split (rcac_sweep.py real router --T .. --m ..).

Policy simulated per user (src/needle/rcac.choose_strategy): visible_n <= T -> EXACT; else APPROX with the smallest
depth in {10,25,50,100,200} >= ceil(10 / s * m) and SEARCH_LIST_SIZE = max(50, 3 * depth); fewer than 10 rows ->
EXACT fallback (recall 1, latency = APPROX + EXACT of that query). Selection: highest pooled dev recall; among
configs within 0.005 of it, the lowest pooled mean latency.

Run from needle/:  PYTHONPATH=src .venv\\Scripts\\python eval\\rcac_router_fit.py
"""
import json
import statistics
from pathlib import Path

from needle.rcac import RouterConfig, choose_strategy

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "eval" / "results"
USERS = ["NDL_P10", "NDL_P25", "NDL_P50", "NDL_P75", "NDL_SENIOR"]
K = 10


def main() -> None:
    d = json.loads((RES / "rcac_real_results.json").read_text())
    rc = d["rcac"]
    n_total = int(next(int(r[1]) for r in d["meta"]["stats"] if r[0] == "ADV_DOC"))
    splits = [q["split"] for q in json.loads((ROOT / "data" / "rcac_queries.json").read_text())]
    dev = [i for i, s in enumerate(splits) if s == "dev"]
    grid = []
    for T in (0, 1000, 2000, 3000, 4000, 5000, 7000):
        for m in (1.0, 1.25, 1.5, 2.0, 3.0):
            cfg = RouterConfig(exact_max_rows=T, overfetch=m)
            rec, ms, fb, per_user = [], [], 0, {}
            for u in USERS:
                s = choose_strategy(rc[u]["visible_rows"], n_total, K, cfg)
                ex = rc[u]["exact"]["per_query"]
                cond = "exact" if s.mode == "EXACT" else f"approx{s.depth}_L{s.search_list_size}"
                pq = rc[u][cond]["per_query"]
                ur, um = [], []
                for i in dev:
                    if s.mode == "APPROX" and (pq[i]["n_ret"] < K or pq[i].get("error")):
                        fb += 1
                        ur.append(1.0)
                        um.append(pq[i]["ms"] + ex[i]["ms"])
                    else:
                        ur.append(1.0 if s.mode == "EXACT" else pq[i]["recall"])
                        um.append(pq[i]["ms"])
                rec += ur
                ms += um
                per_user[u] = {"choice": cond, "recall": round(statistics.fmean(ur), 4),
                               "mean_ms": round(statistics.fmean(um), 2)}
            grid.append({"T": T, "m": m, "dev_recall": round(statistics.fmean(rec), 4),
                         "dev_mean_ms": round(statistics.fmean(ms), 2), "dev_fallbacks": fb, "per_user": per_user})
    best_rec = max(g["dev_recall"] for g in grid)
    chosen = min((g for g in grid if g["dev_recall"] >= best_rec - 0.005), key=lambda g: (g["dev_mean_ms"], -g["m"]))
    out = {"n_dev_queries": len(dev), "selection": "max dev recall; within 0.005 of it, min dev mean latency",
           "chosen": chosen, "grid": grid}
    (RES / "rcac_router_fit.json").write_text(json.dumps(out, indent=1))
    print(f"dev queries={len(dev)}  chosen T={chosen['T']} m={chosen['m']} dev_recall={chosen['dev_recall']} "
          f"dev_mean_ms={chosen['dev_mean_ms']} fallbacks={chosen['dev_fallbacks']}")
    for u, v in chosen["per_user"].items():
        print(f"  {u:10s} {v['choice']:14s} recall={v['recall']} mean_ms={v['mean_ms']}")


if __name__ == "__main__":
    main()
