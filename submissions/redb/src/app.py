"""reDB Streamlit app: the AI agent that tunes IBM Db2 and proves every fix."""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from redb import seed, workload  # noqa: E402
from redb.agent import build_graph, graph_dot  # noqa: E402
from redb.llm import Brain  # noqa: E402
from redb.report import to_markdown  # noqa: E402
from redb.sqlguard import UnsafeSQL  # noqa: E402

st.set_page_config(page_title="reDB · Db2 tuning agent", page_icon="🛠️", layout="wide")
st.markdown("""<style>
.block-container{padding-top:1.5rem}
.badge{display:inline-block;padding:2px 10px;border-radius:12px;font-size:.8rem;font-weight:600;margin-right:6px}
.ok{background:#d1f2e0;color:#0b6b3a}.bad{background:#fde2e1;color:#a61b1b}.info{background:#e3ecfb;color:#1f4e8c}
</style>""", unsafe_allow_html=True)


@st.cache_resource(show_spinner="Connecting to Db2…")
def resources():
    from redb.toolkit import Toolkit
    brain = Brain()
    return Toolkit(embed=brain.embed), brain


def badge(text: str, kind: str = "info") -> str:
    return f'<span class="badge {kind}">{text}</span>'


try:
    tk, brain = resources()
    connected, conn_err = True, None
except Exception as e:  # noqa: BLE001
    connected, conn_err = False, str(e)

ss = st.session_state
ss.setdefault("thread", None)
ss.setdefault("state", None)

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.title("reDB")
    st.caption("re-index · re-write · re-plan")
    if connected:
        s = tk.s
        st.success(f"Db2 connected · {s.db2_database}@{s.db2_host}:{s.db2_port}")
    else:
        st.error("Db2 not reachable")
        st.code(conn_err[:400])
        st.stop()
    st.info(f"LLM: {brain.mode}" + ("" if brain.online else " (set GOOGLE_API_KEY for Gemini)"))
    if tk.memory.warning:
        st.warning(tk.memory.warning)
    reps = st.slider("Workload repetitions", 1, 20, 5)
    if st.button("▶ Run workload", use_container_width=True):
        with st.spinner("Running W1–W6…"):
            ss.last_workload = workload.run(tk.db, repeat=reps)
        st.toast("Workload done")
    if st.button("↺ Reset demo", use_container_width=True, help="Drop every REDB_IX_% index reDB created"):
        with st.spinner("Dropping reDB indexes…"):
            msgs = seed.reset_demo(tk.db)
        ss.thread, ss.state = None, None
        st.toast(f"Reset: {len(msgs)} indexes dropped")

graph = ss.setdefault("graph", build_graph(tk, brain, approver="streamlit"))
tabs = st.tabs(["📈 Workload", "🔬 Analyze", "🏁 Results", "📜 Change ledger", "💬 Ask reDB", "🧭 How it works"])

# ---------------------------------------------------------------- workload
with tabs[0]:
    stmts = tk.top_statements(10)
    h = tk.health()
    c = st.columns(4)
    c[0].metric("Total exec time", f"{sum(x['total_ms'] for x in stmts):,.0f} ms")
    c[1].metric("Top statement avg", f"{stmts[0]['avg_ms']:,.1f} ms" if stmts else "–")
    c[2].metric("Buffer pool hit", f"{h['bufferpool_hit_pct']:.1f} %")
    c[3].metric("Table scans", f"{h['table_scans']:,}")
    if not stmts:
        st.info("The package cache has no RETAIL statements yet. Click **Run workload** in the sidebar.")
    else:
        df = pd.DataFrame([{"Label": workload.label_for(x["sql"]) or "-", "Avg ms": round(x["avg_ms"], 2),
                            "Executions": x["executions"], "Rows read": x["rows_read"],
                            "Rows returned": x["rows_returned"], "Read/returned": round(x["read_per_returned"]),
                            "SQL": x["sql"]} for x in stmts])
        st.subheader("Top statements · MON_GET_PKG_CACHE_STMT")
        st.dataframe(df, use_container_width=True, hide_index=True)
    with st.expander("Table activity (MON_GET_TABLE) and index health (MON_GET_INDEX, SYSCAT)"):
        st.dataframe(pd.DataFrame(h["tables"]), hide_index=True, use_container_width=True)
        st.write("Unused non-unique indexes:", h["unused_indexes"] or "none")
        st.write("Tables with stale statistics:", h["stale_tables"] or "none")

# ---------------------------------------------------------------- analyze
with tabs[1]:
    left, right = st.columns([3, 1])
    left.markdown("Runs the LangGraph agent up to the **human approval** checkpoint. Nothing is changed in Db2 "
                  "until you approve.")
    if right.button("🔬 Analyze workload", type="primary", use_container_width=True):
        ss.thread = str(uuid.uuid4())
        cfg = {"configurable": {"thread_id": ss.thread}}
        with st.status("Agent running…", expanded=True) as status:
            for step in graph.stream({"limit": 8, "log": [], "approved": [], "applied": []}, cfg,
                                     stream_mode="updates"):
                for node, upd in step.items():
                    for line in (upd or {}).get("log", []):
                        st.write(f"**{node}** · {line}")
            status.update(label="Paused for approval", state="complete")
        ss.state = graph.get_state(cfg).values
    state = ss.state
    if state and state.get("cases"):
        props = state.get("proposals", [])
        approved = []
        for case in state["cases"]:
            d = case["diagnosis"]
            sev = {"high": "bad", "medium": "info", "low": "ok"}[d["severity"]]
            with st.container(border=True):
                st.markdown(f"### {case['case_id']} · {d['headline']}")
                st.markdown(badge(d["severity"].upper(), sev) + badge(f"{case['metrics']['avg_ms']:.1f} ms avg") +
                            badge(f"{case['plan_cost']:,.0f} timerons") + badge(f"diagnosis: {d['source']}"),
                            unsafe_allow_html=True)
                st.code(case["sql"], language="sql")
                a, b = st.columns([1, 1])
                with a:
                    st.markdown(d["plain_english"])
                    for rc in d["root_causes"]:
                        st.markdown(f"- {rc}")
                    for sim in case.get("similar", []):
                        st.caption(f"🧠 similar past case #{sim['case_id']} (cosine sim {sim['similarity']}): "
                                   f"{sim['fix_kind']} gave {sim['gain_pct']:.0f}% gain")
                with b:
                    after = case.get("plan_after")
                    if after:
                        now, then = st.columns(2)
                        now.caption(f"Plan now · {case['plan_cost']:,.0f} timerons")
                        now.graphviz_chart(case["dot"], use_container_width=True)
                        then.caption(f"With proposed indexes (virtual) · {after['cost']:,.0f} timerons")
                        then.graphviz_chart(after["dot"], use_container_width=True)
                    else:
                        st.graphviz_chart(case["dot"], use_container_width=True)
                served = [p for p in props if p["kind"] == "INDEX" and case["case_id"] in p.get("serves", [])
                          and p["case_id"] != case["case_id"]]
                for p in served:
                    st.caption(f"↪ also served by: {p['title']} (listed under {p['case_id']})")
                for p in [p for p in props if p["case_id"] == case["case_id"]]:
                    st.markdown(f"**{p['kind']}** · {p['title']}")
                    cols = st.columns(4)
                    if p["est_cost_after"] is not None:
                        cols[0].metric("Est. cost (virtual)", f"{p['est_cost_after']:,.0f}",
                                       f"{-p['est_gain_pct']:.0f}%" if p["est_gain_pct"] is not None else None,
                                       delta_color="inverse")
                    if p["kind"] == "REWRITE":
                        eqb = badge("EQUIVALENT ✓", "ok") if p.get("equivalent") else badge("NOT PROVEN", "bad")
                        if p.get("equivalent") and not p["verified"]:
                            eqb += badge("NO GAIN · REJECTED", "bad")
                        cols[1].markdown(eqb, unsafe_allow_html=True)
                        cols[2].metric("Measured", f"{p.get('ms_rewrite', 0):.1f} ms",
                                       f"{p.get('ms_rewrite', 0) - p.get('ms_before', 0):+.1f} ms", delta_color="inverse")
                    else:
                        cols[1].markdown(badge("PROVEN BY DB2 ✓", "ok") if p["verified"] else badge("NOT PROVEN", "bad"),
                                         unsafe_allow_html=True)
                        cols[2].metric("Measured now", f"{p.get('ms_before', 0):.1f} ms")
                    if cols[3].checkbox("Approve", key=f"ap_{p['id']}", disabled=not p["verified"]):
                        approved.append(p["id"])
                    if p["kind"] == "INDEX":
                        st.markdown(badge(f"est. size {p['size_mb']} MB") + badge(f"table writes {p['write_pct']:.0f}%")
                                    + "".join(badge("⚠ " + w, "bad") for w in p["warnings"]), unsafe_allow_html=True)
                    st.code("\n".join(p["ddl"]) or p["rewrite_sql"] or "", language="sql")
                    st.caption(p["evidence"])
        general = [p for p in props if p["case_id"] == "-"]
        if general:
            with st.container(border=True):
                st.markdown("### Housekeeping")
                for p in general:
                    st.markdown(f"**{p['kind']}** · {p['title']}")
                    if st.checkbox("Approve", key=f"ap_{p['id']}"):
                        approved.append(p["id"])
                    st.code("\n".join(p["ddl"]), language="sql")
                    st.caption(p["evidence"] + (f" · undo: `{p['undo'][0]}`" if p["undo"] else ""))
        if not state.get("report"):
            if st.button(f"✅ Apply {len(approved)} approved", type="primary", disabled=not approved):
                cfg = {"configurable": {"thread_id": ss.thread}}
                with st.spinner("Applying, re-running statistics and re-measuring…"):
                    graph.update_state(cfg, {"approved": approved})
                    graph.invoke(None, cfg)
                ss.state = graph.get_state(cfg).values
                st.rerun()
        else:
            st.success("Applied. See the **Results** and **Change ledger** tabs.")
    elif state:
        st.info("No candidate statements. Run the workload first.")

# ---------------------------------------------------------------- results
with tabs[2]:
    rep = (ss.state or {}).get("report")
    if not rep:
        st.info("Approve and apply proposals in **Analyze** to see measured results.")
    else:
        if rep.get("reduction_pct") is not None:
            c = st.columns(3)
            c[0].metric("Before", f"{rep['ms_before']:,.1f} ms")
            c[1].metric("After", f"{rep['ms_after']:,.1f} ms")
            c[2].metric("Workload time reduction", f"{rep['reduction_pct']:.1f} %")
        df = pd.DataFrame(rep["per_statement"]).set_index("case_id")
        st.bar_chart(df[["ms_before", "ms_after"]], stack=False, color=["#c0392b", "#1f8a4c"])
        st.dataframe(df, use_container_width=True)
        st.markdown(f"> {rep['narrative']}")
        st.download_button("⬇ Download tuning report (Markdown)", to_markdown(ss.state, brain.mode),
                           file_name="redb-tuning-report.md", mime="text/markdown")
        with st.expander("Agent log"):
            st.code("\n".join(ss.state.get("log", [])))

# ---------------------------------------------------------------- ledger
with tabs[3]:
    st.markdown("`REDB.CHANGES` is a **system-period temporal table**: every status change is versioned "
                "into `REDB.CHANGES_HISTORY` by Db2 itself.")
    cur = tk.ledger_current()
    if not cur:
        st.info("No changes yet.")
    else:
        st.subheader("Current state")
        for r in cur:
            cols = st.columns([1, 5, 2, 2])
            cols[0].markdown(f"**#{r['CHANGE_ID']}**")
            cols[1].markdown(f"{r['TITLE']}  \n`{r['KIND']}` · {r['SYS_START'][:19]}")
            ms = (f"{r['MS_BEFORE']:.1f} → {r['MS_AFTER']:.1f} ms"
                  if r["MS_BEFORE"] is not None and r["MS_AFTER"] is not None else "")
            cols[2].markdown(badge(r["STATUS"], {"APPLIED": "ok", "ADOPTED": "ok", "FAILED": "bad"}.get(r["STATUS"], "info"))
                             + f"<br>{ms}", unsafe_allow_html=True)
            if r["STATUS"] == "APPLIED" and r["UNDO_DDL"]:
                if cols[3].button("Roll back", key=f"rb_{r['CHANGE_ID']}"):
                    tk.rollback(r["CHANGE_ID"])
                    st.toast(f"Rolled back #{r['CHANGE_ID']}")
                    st.rerun()
        st.subheader("Full timeline · FOR SYSTEM_TIME FROM … TO …")
        tl = pd.DataFrame(tk.ledger_timeline())
        st.dataframe(tl[["CHANGE_ID", "KIND", "STATUS", "TITLE", "SYS_START", "SYS_END"]],
                     hide_index=True, use_container_width=True)
        st.subheader("Time travel · FOR SYSTEM_TIME AS OF")
        stamps = sorted(set(tl["SYS_START"]))
        ts = st.select_slider("Show the ledger as it was at", options=stamps, value=stamps[-1],
                              format_func=lambda x: x[:19].replace("-", " ", 3).replace(".", ":"))
        st.dataframe(pd.DataFrame(tk.ledger_as_of(ts))[["CHANGE_ID", "KIND", "STATUS", "TITLE"]],
                     hide_index=True, use_container_width=True)

# ---------------------------------------------------------------- ask
with tabs[4]:
    st.markdown("Ask about the workload, the change ledger or the tuning memory. The question becomes **one "
                "read-only SELECT**, which must pass the SQL guard before Db2 runs it (capped at 200 rows).")
    examples = ["What are the slowest statements?", "Which changes were applied and what did they gain?",
                "Show the full history of the ledger", "Which indexes exist on RETAIL?", "Which tables get scanned most?"]
    ex = st.pills("Examples", examples, label_visibility="collapsed")
    q = st.text_input("Question", value=ex or "", placeholder="e.g. Which changes were rolled back?")
    if q:
        ans = brain.ask(q)
        st.caption(f"{ans['explanation']} · source: {ans['source']}")
        st.code(ans["sql"], language="sql")
        try:
            st.dataframe(pd.DataFrame(tk.ask(ans["sql"])), hide_index=True, use_container_width=True)
        except UnsafeSQL as e:
            st.error(f"Blocked by the SQL guard: {e}")
        except Exception as e:  # noqa: BLE001
            st.error(f"Db2 rejected the query: {str(e)[:300]}")

# ---------------------------------------------------------------- how it works
with tabs[5]:
    st.markdown("""
**The LLM never writes DDL.** Index DDL comes only from Db2's own advisor (`ADVISE_INDEX`), rewrites must pass a
read-only SQL guard and be **proven equivalent inside Db2** (`EXCEPT ALL` both ways), and nothing is applied
without a human approving it at the LangGraph interrupt.""")
    st.graphviz_chart(graph_dot(graph))
    with st.expander("Mermaid source (graph.get_graph().draw_mermaid())"):
        st.code(graph.get_graph().draw_mermaid())
