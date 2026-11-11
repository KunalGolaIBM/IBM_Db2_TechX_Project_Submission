"""The reDB LangGraph agent: observe → explain → diagnose → prescribe → prove → recall → [human] → apply → report."""
from __future__ import annotations

import hashlib
import operator
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from .advisor import consolidate
from .memory import signature
from .sqlguard import UnsafeSQL, check_readonly
from .workload import label_for


class State(TypedDict, total=False):
    limit: int
    statements: list[dict]
    health: dict
    cases: list[dict]
    proposals: list[dict]
    approved: list[str]
    applied: list[dict]
    report: dict
    log: Annotated[list[str], operator.add]


MIN_COST = 100.0  # timerons; cheaper statements are not worth an index
WRITE_HEAVY_PCT = 20.0  # share of row activity that is writes above which an index gets a warning


def _pid(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:8]


def _gain(before: float | None, after: float | None) -> float | None:
    if before is None or after is None or before <= 0:
        return None
    return round(100 * (before - after) / before, 1)


def build_graph(tk, brain, approver: str = "human"):
    """tk: Toolkit (or a fake with the same methods); brain: llm.Brain."""

    def observe(state: State) -> dict:
        stmts = tk.top_statements(state.get("limit", 8))
        for i, s in enumerate(stmts):
            s["label"] = label_for(s["sql"]) or f"S{i + 1}"
        return {"statements": stmts, "health": tk.health(),
                "log": [f"observe: {len(stmts)} candidate statements from MON_GET_PKG_CACHE_STMT"]}

    def explain(state: State) -> dict:
        cases, log = [], []
        for s in state["statements"]:
            try:
                plan = tk.explain(s["sql"])
            except Exception as e:  # noqa: BLE001
                log.append(f"explain: {s['label']} skipped ({str(e)[:120]})")
                continue
            cat = tk.catalog(plan["tables"])
            cases.append({"case_id": s["label"], "sql": s["sql"], "metrics": s, "plan_cost": plan["total_cost"],
                          "plan_summary": plan["summary"], "dot": plan["dot"], "flags": plan["flags"],
                          "tables": plan["tables"], "operators": plan["operators"], "catalog": cat["text"],
                          "not_null": cat["not_null"],
                          "signature": signature(s["sql"], plan["tables"], plan["operators"])})
        return {"cases": cases, "log": log + [f"explain: {len(cases)} access plans read from EXPLAIN tables"]}

    def diagnose(state: State) -> dict:
        cases = []
        for c in state["cases"]:
            metrics = {k: c["metrics"][k] for k in ("executions", "avg_ms", "rows_read", "rows_returned",
                                                    "read_per_returned")}
            c = {**c, "diagnosis": brain.diagnose({"sql": c["sql"], "plan_summary": c["plan_summary"],
                                                    "metrics": metrics, "catalog": c["catalog"], "flags": c["flags"]})}
            cases.append(c)
        return {"cases": cases, "log": [f"diagnose: {len(cases)} diagnoses via {brain.mode}"]}

    def prescribe(state: State) -> dict:
        proposals, log = [], []
        cases = [dict(c) for c in state["cases"]]
        by_id = {c["case_id"]: c for c in cases}
        pool: dict[str, dict] = {}   # index name -> index advised by Db2 (deduplicated across statements)
        workload: list[tuple] = []   # (case_id, sql, current cost): what the consolidation prices
        tk.clear_advice()

        def advise(case, sql, cost):
            try:
                rec = tk.recommend_indexes(sql)
            except Exception as e:  # noqa: BLE001
                log.append(f"prescribe: advisor failed for {case['case_id']} ({str(e)[:120]})")
                return
            workload.append((case["case_id"], sql, cost))
            for i in rec["indexes"]:
                pool.setdefault(i["name"], i)

        for c in cases:
            if c["plan_cost"] < MIN_COST:
                log.append(f"prescribe: {c['case_id']} is already cheap ({c['plan_cost']:,.1f} timerons), left alone")
                continue
            advise(c, c["sql"], c["plan_cost"])
            rw = brain.rewrite({"sql": c["sql"], "plan_summary": c["plan_summary"], "catalog": c["catalog"],
                                "not_null_cols": set(c["not_null"])})
            if rw["should_rewrite"] and rw["sql"]:
                try:
                    safe = check_readonly(rw["sql"])
                    cost = tk.explain_cost(safe)
                except Exception as e:  # noqa: BLE001 - unsafe or uncompilable rewrite
                    log.append(f"prescribe: rewrite for {c['case_id']} rejected ({str(e)[:120]})")
                    continue
                proposals.append({
                    "id": _pid("REWRITE", c["case_id"], safe), "case_id": c["case_id"], "kind": "REWRITE",
                    "title": f"{c['case_id']}: adopt equivalent rewrite", "ddl": [], "undo": [], "tables": c["tables"],
                    "target_sql": safe, "est_cost_before": c["plan_cost"], "est_cost_after": cost,
                    "est_gain_pct": _gain(c["plan_cost"], cost), "verified": False, "evidence": "",
                    "rewrite_sql": safe, "rationale": rw["rationale"], "source": rw["source"]})
                advise(c, safe, cost)  # the rewrite may want a different index than the original

        if pool:
            # Workload-level what-if: price index subsets on virtual indexes and keep the smallest good set.
            baseline = sum(cost for *_, cost in workload)
            kept, dropped = consolidate(
                list(pool.values()), lambda ix: sum(tk.evaluate_plan(sql, ix)["total_cost"] for _, sql, _ in workload),
                baseline)
            served: dict[str, dict] = {i["name"]: {} for i in kept}
            for cid, sql, cost in workload:
                plan = tk.evaluate_plan(sql, kept)
                if sql == by_id[cid]["sql"]:
                    by_id[cid]["plan_after"] = {"cost": plan["total_cost"], "dot": plan["dot"],
                                                "summary": plan["summary"], "uses": plan["uses"]}
                for name in plan["uses"]:
                    served[name][sql] = (cid, cost, plan["total_cost"])
            writes = {f"{tk.schema}.{t['table']}": t.get("write_pct", 0.0) for t in state["health"].get("tables", [])}
            for i in kept:
                uses = served[i["name"]]
                if not uses:  # no final plan picks it: building it would be pure overhead
                    dropped.append(i)
                    continue
                serves = sorted({cid for cid, *_ in uses.values()})
                before, after = sum(u[1] for u in uses.values()), sum(u[2] for u in uses.values())
                first_sql, (first_case, *_rest) = next(iter(uses.items()))
                cols = ", ".join(c for c, _ in i["columns"])
                wp = writes.get(i["table"], 0.0)
                warnings = ([f"wide index ({len(i['columns'])} columns)"] if len(i["columns"]) > 4 else []) + \
                           ([f"write-heavy table ({wp:.0f}% of row activity is writes): every write must maintain it"]
                            if wp >= WRITE_HEAVY_PCT else [])
                proposals.append({
                    "id": _pid("INDEX", i["name"]), "case_id": first_case, "kind": "INDEX",
                    "title": f"Index on {i['table']} ({cols}) for {', '.join(serves)}",
                    "ddl": [i["ddl"]], "undo": [i["undo"]], "tables": [i["table"]], "target_sql": first_sql,
                    "serves": serves, "size_mb": i.get("size_mb"), "write_pct": wp, "warnings": warnings,
                    "est_cost_before": before, "est_cost_after": after, "est_gain_pct": _gain(before, after),
                    "verified": False, "evidence": "", "rewrite_sql": None,
                    "rationale": "; ".join(by_id[first_case]["diagnosis"]["root_causes"])})
            log.append(f"prescribe: Db2 advised {len(pool)} indexes; what-if consolidation kept "
                       f"{len(pool) - len(dropped)} and dropped {len(dropped)} (>=95% of the gain retained)")

        for u in state["health"].get("unused_indexes", []):
            try:
                drop, create = tk.drop_index_ddl(u["table"], u["index"], u["colnames"])
            except ValueError:
                continue
            proposals.append({
                "id": _pid("DROP_INDEX", u["index"]), "case_id": "-", "kind": "DROP_INDEX",
                "title": f"Drop unused index {tk.schema}.{u['index']} on {u['table']}", "ddl": [drop], "undo": [create],
                "tables": [f"{tk.schema}.{u['table']}"], "target_sql": None, "est_cost_before": None,
                "est_cost_after": None, "est_gain_pct": None, "verified": True, "rewrite_sql": None,
                "evidence": "MON_GET_INDEX: 0 index scans and 0 index-only scans since database activation "
                            "(counters reset on restart: confirm the window covers your full workload)",
                "rationale": "An index nothing reads still costs every insert, update and delete."})
        for t in state["health"].get("stale_tables", []):
            table = f"{tk.schema}.{t.strip()}"
            proposals.append({
                "id": _pid("RUNSTATS", table), "case_id": "-", "kind": "RUNSTATS",
                "title": f"Collect statistics on {table} (never collected)", "ddl": [tk.runstats_sql(table)],
                "undo": [], "tables": [table], "target_sql": None, "est_cost_before": None, "est_cost_after": None,
                "est_gain_pct": None, "verified": True, "evidence": "SYSCAT.TABLES.STATS_TIME is NULL",
                "rewrite_sql": None, "rationale": "The optimizer is guessing cardinalities without statistics."})
        return {"cases": cases, "proposals": proposals, "log": log + [f"prescribe: {len(proposals)} proposals"]}

    def prove(state: State) -> dict:
        cases = []
        for c in state["cases"]:
            cases.append({**c, "ms_before": tk.timed(c["sql"])})
        by_case = {c["case_id"]: c for c in cases}
        out = []
        for p in state["proposals"]:
            p = dict(p)
            c = by_case.get(p["case_id"])
            if p["kind"] == "INDEX":
                ok = p["est_cost_after"] is not None and p["est_cost_after"] < (p["est_cost_before"] or 0)
                p.update(verified=ok, evidence=(
                    f"Db2 optimizer on virtual indexes (EVALUATE INDEXES, nothing built): "
                    f"{p['est_cost_before']:,.1f} → {p['est_cost_after']:,.1f} timerons across {', '.join(p['serves'])}; "
                    f"est. size {p['size_mb']} MB; writes are {p['write_pct']:.0f}% of the table's row activity"
                    + "".join(f"; WARNING: {w}" for w in p["warnings"])))
            elif p["kind"] == "REWRITE":
                eq = tk.prove_equivalent(c["sql"], p["rewrite_sql"])
                cost, ms_rw = p["est_cost_after"], tk.timed(p["rewrite_sql"])
                # equivalent is not enough: a clearly cheaper plan that is not slower, or far faster measured
                # (25% is well outside timing noise on millisecond queries)
                faster = ms_rw <= c["ms_before"] * 0.75 or (cost < p["est_cost_before"] * 0.95
                                                            and ms_rw <= c["ms_before"] * 1.05)
                verdict = "" if faster else "; REJECTED: equivalent but no gain (Db2 already optimises the original)"
                p.update(equivalent=eq["proven"], verified=eq["proven"] and faster, ms_rewrite=ms_rw,
                         evidence=f"{eq['detail']}; EXPLAIN {p['est_cost_before']:,.1f} → {cost:,.1f}"
                                  f" timerons; measured {c['ms_before']:,.1f} → {ms_rw:,.1f} ms{verdict}")
            if c:
                p["ms_before"] = c["ms_before"]
            out.append(p)
        n = sum(p["verified"] for p in out)
        return {"cases": cases, "proposals": out, "log": [f"prove: {n}/{len(out)} proposals proven by Db2"]}

    def recall(state: State) -> dict:
        cases = [{**c, "similar": tk.recall(c["signature"])} for c in state["cases"]]
        return {"cases": cases, "approved": state.get("approved", []),
                "log": [f"recall: searched vector memory for {len(cases)} cases"]}

    def apply(state: State) -> dict:
        approved = set(state.get("approved") or [])
        order = {"RUNSTATS": 0, "INDEX": 1, "DROP_INDEX": 2, "REWRITE": 3}
        todo = sorted([p for p in state["proposals"] if p["id"] in approved and p["verified"]],
                      key=lambda p: order[p["kind"]])
        cases = {c["case_id"]: c for c in state["cases"]}
        applied, log = [], []
        for p in todo:
            c = cases.get(p["case_id"])
            cid = tk.ledger_record(kind=p["kind"], title=p["title"], stmt_text=(c or {}).get("sql", ""),
                                   ddl="\n".join(p["ddl"]) or (p["rewrite_sql"] or ""), undo_ddl="\n".join(p["undo"]),
                                   status="PROPOSED", cost_before=p["est_cost_before"], cost_after=p["est_cost_after"],
                                   ms_before=p.get("ms_before"), rationale=f"{p['rationale']} | {p['evidence']}",
                                   approved_by=approver)
            done = []
            try:
                for ddl in p["ddl"]:
                    try:
                        tk.run_ddl(ddl)
                        done.append(ddl)
                    except Exception as e:  # noqa: BLE001
                        if "SQL0605W" not in str(e) and "SQL0601N" not in str(e):  # already exists
                            raise
                if p["kind"] == "INDEX":
                    for t in p["tables"]:
                        tk.run_ddl(tk.runstats_sql(t))
                ms_after = tk.timed(p["target_sql"]) if p.get("target_sql") else None
                status = "ADOPTED" if p["kind"] == "REWRITE" else "APPLIED"
                tk.ledger_status(cid, status, ms_after)
                gain = _gain(p.get("ms_before"), ms_after)
                if c and gain is not None and gain > 0:  # only remember fixes that actually helped
                    tk.remember(c["signature"], c["sql"], p["kind"], "\n".join(p["ddl"]) or p["rewrite_sql"], gain)
                applied.append({**p, "change_id": cid, "status": status, "ms_after": ms_after, "gain_pct": gain})
                log.append(f"apply: #{cid} {p['title']} → {status}"
                           + (f" ({p.get('ms_before', 0):,.1f} → {ms_after:,.1f} ms)" if ms_after is not None else ""))
            except Exception as e:  # noqa: BLE001
                for ddl, undo in zip(p["ddl"], p["undo"]):
                    if ddl in done:
                        try:
                            tk.run_ddl(undo)
                        except Exception:  # noqa: BLE001
                            pass
                tk.ledger_status(cid, "FAILED")
                log.append(f"apply: #{cid} {p['title']} FAILED ({str(e)[:160]})")
        skipped = len(approved) - len(todo)
        return {"applied": applied, "log": log + ([f"apply: {skipped} approved but unproven proposals skipped"]
                                                  if skipped > 0 else [])}

    def report(state: State) -> dict:
        applied = state.get("applied") or []
        rows = []
        for c in state["cases"]:
            if not applied:
                rows.append({"case_id": c["case_id"], "ms_before": c.get("ms_before"), "ms_after": None})
                continue
            after = tk.timed(c["sql"])
            adopted = [p for p in applied if p["case_id"] == c["case_id"] and p["kind"] == "REWRITE"]
            if adopted:
                after = min(after, tk.timed(adopted[0]["rewrite_sql"]))
            rows.append({"case_id": c["case_id"], "ms_before": c.get("ms_before"), "ms_after": after,
                         "gain_pct": _gain(c.get("ms_before"), after)})
        b = sum(r["ms_before"] or 0 for r in rows)
        a = sum((r["ms_after"] if r["ms_after"] is not None else r["ms_before"] or 0) for r in rows)
        rep = {"statements": len(state["cases"]), "proposals": len(state["proposals"]), "applied": applied,
               "per_statement": rows, "ms_before": b, "ms_after": a, "reduction_pct": _gain(b, a) if applied else None}
        rep["narrative"] = brain.narrate({k: v for k, v in rep.items() if k != "applied"} |
                                         {"applied": [p["title"] for p in applied]})
        return {"report": rep, "log": ["report: done"]}

    def has_proposals(state: State) -> str:
        return "apply" if state.get("proposals") else "report"

    g = StateGraph(State)
    for name, fn in [("observe", observe), ("explain", explain), ("diagnose", diagnose), ("prescribe", prescribe),
                     ("prove", prove), ("recall", recall), ("apply", apply), ("report", report)]:
        g.add_node(name, fn)
    g.set_entry_point("observe")
    for a, b in [("observe", "explain"), ("explain", "diagnose"), ("diagnose", "prescribe"),
                 ("prescribe", "prove"), ("prove", "recall"), ("apply", "report")]:
        g.add_edge(a, b)
    g.add_conditional_edges("recall", has_proposals, {"apply": "apply", "report": "report"})
    g.add_edge("report", END)
    return g.compile(checkpointer=MemorySaver(), interrupt_before=["apply"])


def run_until_approval(graph, thread_id: str, limit: int = 8) -> dict:
    config = {"configurable": {"thread_id": thread_id}}
    graph.invoke({"limit": limit, "log": [], "approved": [], "applied": []}, config)
    return graph.get_state(config).values


def resume(graph, thread_id: str, approved: list[str]) -> dict:
    config = {"configurable": {"thread_id": thread_id}}
    graph.update_state(config, {"approved": list(approved)})
    graph.invoke(None, config)
    return graph.get_state(config).values


def graph_dot(graph) -> str:
    """Graphviz DOT of the compiled LangGraph (offline alternative to draw_mermaid)."""
    g = graph.get_graph()
    out = ['digraph agent {', 'rankdir=TB; node [shape=box, style="rounded,filled", fillcolor="#e8f0fe", '
           'color="#1f4e8c", fontname="Helvetica"];']
    for n in g.nodes:
        if n in ("__start__", "__end__"):
            out.append(f'"{n}" [shape=circle, label="", width=0.2, fillcolor="#333333"];')
        elif n == "apply":
            out.append(f'"{n}" [fillcolor="#fff3cd", label="✋ human approval\\napply"];')
    for e in g.edges:
        label = "proposals → wait for approval" if e.target == "apply" else "no proposals"
        style = f' [style=dashed, label="{label}"]' if e.conditional else ""
        out.append(f'"{e.source}" -> "{e.target}"{style};')
    return "\n".join(out + ["}"])
