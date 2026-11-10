"""Headline chart: recall@10 and rows returned vs the fraction of rows the Db2 user may see (RCAC).

Reads eval/results/rcac_real_results.json (written by eval/rcac_sweep.py in the codespace, copied here).
Writes eval/results/rcac_recall_vs_selectivity.png and eval/results/rcac_recall_vs_selectivity.json (plotted numbers).
Measured numbers only; every plotted value comes from the JSON. Palette validated with the dataviz validator
(light surface #fcfcfb: blue #2a78d6, orange #eb6834, aqua #1baf7a; aqua < 3:1 -> direct labels + table in the doc).

Run from needle/:  .venv\\Scripts\\python eval\\rcac_chart.py
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "eval" / "results"
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
USERS = [("NDL_P10", 10), ("NDL_P25", 25), ("NDL_P50", 50), ("NDL_P75", 75), ("NDL_SENIOR", 100)]
SPLIT = "heldout"


def main() -> None:
    d = json.loads((RES / "rcac_real_results.json").read_text())
    rc, base, router = d["rcac"], d["baseline_where_no_rcac"], d["router_heldout"]
    rc_plan = rc["plans_as_db2inst1"]["approx10"]
    series = {"rcac": [], "router": [], "where": []}
    for user, p in USERS:
        u = rc[user]
        x = 100.0 * u["visible_fraction"]
        a = u["approx10"][SPLIT]
        series["rcac"].append({"user": user, "x": x, "recall": a["recall_mean"], "rows": a["returned_mean"],
                               "underfill": a["underfill_rate"], "index": rc_plan["uses_vector_index"],
                               "L": rc_plan["srchlsiz"], "ixscan_est_rows": rc_plan["vector_ixscan_est_rows"]})
        r = router[user]
        s = r["strategy"]
        cond = "exact" if s["mode"] == "EXACT" else f"approx{s['depth']}_L{s['search_list_size']}"
        series["router"].append({"user": user, "x": x, "recall": r["all"]["recall_mean"],
                                 "rows": r["all"]["returned_mean"], "underfill": r["all"]["underfill_rate"],
                                 "index": rc["plans_as_db2inst1"][cond]["uses_vector_index"], "mode": s["mode"],
                                 "depth": s["depth"], "L": s["search_list_size"], "fallbacks": r["fallbacks"]})
        b = base[str(p)]["approx10"]
        series["where"].append({"user": f"WHERE ROW_BUCKET < {p}" if p < 100 else "no filter", "x": float(p),
                                "recall": b[SPLIT]["recall_mean"], "rows": b[SPLIT]["returned_mean"],
                                "underfill": b[SPLIT]["underfill_rate"], "index": b["plan"]["uses_vector_index"],
                                "L": b["plan"]["srchlsiz"], "ixscan_est_rows": b["plan"]["vector_ixscan_est_rows"]})
    meta = d["meta"]
    n_q = meta["n_heldout"]

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": INK2,
                         "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2})
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.2), facecolor=SURFACE)
    spec = [("where", AQUA, "s", "Plain WHERE ROW_BUCKET < p (literal, no RCAC)"),
            ("rcac", BLUE, "o", "RCAC user: FETCH APPROX FIRST 10"),
            ("router", ORANGE, "D", "RCAC user: router (EXACT or deeper APPROX)")]
    for ax, key, ylabel, ylim in ((axes[0], "recall", "recall@10 vs the user's own FETCH EXACT", (0, 1.05)),
                                  (axes[1], "rows", "rows returned (10 requested), mean", (0, 10.8))):
        ax.set_facecolor(SURFACE)
        for name, color, marker, label in spec:
            pts = series[name]
            xs, ys = [p["x"] for p in pts], [p[key] for p in pts]
            ax.plot(xs, ys, color=color, linewidth=2, zorder=2, label=label)
            for p in pts:  # filled = vector index in the plan, hollow = no vector index (exact scan)
                ax.plot(p["x"], p[key], marker=marker, markersize=8, color=color, zorder=3,
                        markerfacecolor=color if p["index"] else SURFACE, markeredgewidth=2,
                        markeredgecolor=SURFACE if p["index"] else color)
        for p in series["rcac"][:2]:  # label selectively: the two low-visibility users where the effect sits
            ax.annotate(f"{p[key]:.2f}" if key == "recall" else f"{p[key]:.1f}", (p["x"], p[key]),
                        textcoords="offset points", xytext=(0, -15), ha="center", fontsize=8.5, color=INK)
        ax.set_xlim(0, 105)
        ax.set_ylim(*ylim)
        ax.set_xticks([10, 25, 50, 75, 100])
        ax.set_xlabel("rows the user may see (% of NEEDLE.ADV_DOC)")
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axes[0].set_title("Recall@10 under row access control", color=INK, loc="left", fontsize=12)
    axes[1].set_title("Under-fill: rows actually returned", color=INK, loc="left", fontsize=12)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False, fontsize=9.5, bbox_to_anchor=(0.5, 0.95))
    rp = series["rcac"][0]
    fig.suptitle("Db2 RCAC + DiskANN: low-visibility users get under-filled, low-recall APPROX results; "
                 "the router restores them", color=INK, fontsize=12.5, x=0.01, ha="left", y=0.995)
    cap = (f"Measured on {meta['db2']} | NEEDLE.ADV_DOC {meta['stats'][0][1] if meta.get('stats') else ''} rows "
           f"(OSV PyPI advisories, nomic-embed-text 768-d, CREATE VECTOR INDEX ... DISTANCE COSINE) | {n_q} held-out "
           f"queries, k = 10 | filled marker = vector index (IXSCAN) in the plan, hollow = exact table scan | "
           f"RCAC plan (all users): permission filter factor fixed, IXSCAN est {rp['ixscan_est_rows']:.0f} rows, "
           f"SRCHLSIZ {rp['L']}")
    fig.text(0.01, 0.01, cap, fontsize=8, color=INK2, ha="left", wrap=True)
    fig.tight_layout(rect=(0, 0.05, 1, 0.9))
    out = RES / "rcac_recall_vs_selectivity.png"
    fig.savefig(out, dpi=160, facecolor=SURFACE)
    (RES / "rcac_recall_vs_selectivity.json").write_text(json.dumps(
        {"split": SPLIT, "n_queries": n_q, "db2": meta["db2"], "series": series}, indent=1))
    print("wrote", out)


if __name__ == "__main__":
    main()
