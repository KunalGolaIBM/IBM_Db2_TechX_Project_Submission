"""Custodian UI. Run: streamlit run src/app.py            (Groq -> Ollama -> scripted)
                      streamlit run src/app.py -- --no-llm (scripted agent plans, no model needed)"""
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
import agent  # noqa: E402
import gateway  # noqa: E402
import retrieval  # noqa: E402

st.set_page_config(page_title="Custodian: Db2 control plane for AI agents", page_icon="🛡️", layout="wide")
PERSONAS = {"Priya · Support agent": "PRIYA", "Arjun · Admin": "ARJUN"}
BADGE = {"ALLOW": "🟢 ALLOW", "EXECUTED": "🟢 EXECUTED", "APPROVE": "🟡 NEEDS APPROVAL",
         "DENY": "🔴 DENY", "ERROR": "⚠️ ERROR"}
st.cache_resource(show_spinner="Loading the local Granite embedding model…")(retrieval.embeddings)()
ss = st.session_state
ss.setdefault("turns", [])
ss.setdefault("result", None)

# ------------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.title("🛡️ Custodian")
    st.caption("The database is the agent's guardrail. Every statement runs through IBM Db2 as the human who asked.")
    persona = st.radio("Signed in as", list(PERSONAS), key="persona")
    user = PERSONAS[persona]
    role = gateway.role_of(user)
    st.markdown(f"Db2 authorization ID **`{user}`** · role **`{role}`**")
    offline_default = "--no-llm" in sys.argv or os.getenv("CUSTODIAN_LLM", "auto").lower() == "none"
    offline = st.toggle("Offline scripted agent (--no-llm)", value=offline_default,
                        help="Replays fixed agent plans for the demo prompts. Off = Groq, then local Ollama.")
    st.divider()
    st.caption("Demo prompts")
    for p in agent.DEMO_PROMPTS:
        if st.button(p, width="stretch"):
            ss.queued = p
    with st.expander("Db2 objects enforcing this"):
        st.code((Path(__file__).parent / "rcac.sql").read_text(), language="sql")

tab_agent, tab_appr, tab_ledger = st.tabs(["💬 Agent", "✅ Approvals", "🕰️ Ledger · Rewind · Replay"])


def render_step(i: int, s: dict):
    title = f"**{i}. {s['tool']}** · {BADGE.get(s['decision'], s['decision'])} · layer `{s['layer']}`"
    with st.container(border=True):
        st.markdown(title)
        if s["tool"] == "search_tickets":
            st.caption(f"VECTOR_DISTANCE(..., COSINE) over BANK.TICKET_EMBEDDINGS for: “{s['query']}”")
            for h in s["hits"]:
                st.markdown(f"- `#{h['ticket_id']}` (distance {h['distance']}): {h['text'][:300]}")
            return
        st.code(s["sql"], language="sql", wrap_lines=True)
        st.caption(s.get("reason", ""))
        if s.get("table_rows"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Rows touched (exact)", f"{s['rows']:,}")
            c2.metric("Share of visible table", f"{100 * s['rows'] / s['table_rows']:.1f}%")
            c3.metric("EXPLAIN cost (timerons)", f"{s['est_cost']:.0f}" if s.get("est_cost") is not None else "n/a")
            if s.get("count_sql"):
                st.caption(f"Measured as {s['user']}: `{s['count_sql']}`")
        if s.get("data"):
            st.dataframe(pd.DataFrame(s["data"], columns=s["columns"]), hide_index=True, width="stretch")


# ------------------------------------------------------------------------------- agent tab
with tab_agent:
    chat, panel = st.columns([3, 2])
    prompt = st.chat_input(f"Ask the support agent as {persona.split(' ·')[0]}…") or ss.pop("queued", None)
    if prompt:
        with st.spinner("Agent working through Custodian…"):
            ss.turns.append({"user": user, "prompt": prompt, **agent.ask(user, prompt, offline=offline)})
    with chat:
        for t in ss.turns:
            st.chat_message("user").markdown(f"**{t['user']}**: {t['prompt']}")
            if t.get("pending"):
                st.chat_message("assistant").warning(
                    f"⏸️ Paused: approval #{t['pending']['approval_id']} for {t['pending']['rows']} row(s) is waiting "
                    "in CUSTODIAN.APPROVALS. An admin must decide (Approvals tab).")
            else:
                st.chat_message("assistant").markdown(t.get("answer", ""))
                st.caption(f"model: {t.get('model', '?')}")
    with panel:
        st.subheader("Custodian decisions")
        if ss.turns:
            for i, s in enumerate(ss.turns[-1].get("steps", []), 1):
                render_step(i, s)
        else:
            st.info("Every statement the agent sends, and the Db2 layer that decided it, shows up here.")

# ------------------------------------------------------------------------------- approvals tab
with tab_appr:
    st.subheader("Pending approvals (stored in CUSTODIAN.APPROVALS)")
    pend = gateway.pending_approvals()
    if not pend:
        st.info("Nothing waiting.")
    for aid, req, sql, rows, thread, lid in pend:
        with st.container(border=True):
            st.markdown(f"**#{aid}** requested by `{req}` · {rows} row(s) · ledger entry {lid}")
            st.code(sql, language="sql", wrap_lines=True)
            if role != "ADMINS":
                st.caption("Only an ADMINS user can decide. Switch persona to Arjun.")
                continue
            c1, c2 = st.columns(2)
            for col, label, ok in ((c1, "Approve", True), (c2, "Reject", False)):
                if col.button(label, key=f"{label}{aid}", width="stretch"):
                    if agent.has_thread(thread):  # resume the paused LangGraph run
                        state = agent.resume(thread, user, ok)
                        for t in ss.turns:
                            if t.get("thread_id") == thread:
                                t.update(state)
                    else:  # app restarted: the approval still lives in Db2, execute it directly
                        gateway.decide_approval(aid, user, ok)
                    st.rerun()

# ------------------------------------------------------------------------------- ledger tab
with tab_ledger:
    st.subheader("CUSTODIAN.LEDGER: every statement the agent attempted")
    cols, rows = gateway.ledger_rows()
    df = pd.DataFrame(rows, columns=cols)
    st.dataframe(df.drop(columns=["ANSWER"]), hide_index=True, width="stretch", height=280)
    if not df.empty:
        entry = st.selectbox("Ledger entry", df["ENTRY_ID"].tolist(),
                             format_func=lambda e: f"#{e}: " + " · ".join(
                                 str(x) for x in df.loc[df.ENTRY_ID == e, ["DB_USER", "STATEMENT_TYPE", "DECISION"]].iloc[0]))
        r = df[df.ENTRY_ID == entry].iloc[0]
        c1, c2 = st.columns(2)
        can_rewind = (r.DECISION == "EXECUTED" and r.TABLE_NAME in gateway.TEMPORAL_PK
                      and pd.notna(r.TX_TS) and pd.isna(r.REWOUND_BY))
        if c1.button("⏪ Rewind this transaction", disabled=not can_rewind, width="stretch"):
            try:
                ss.result = ("rewind", gateway.rewind(int(entry), user))
            except Exception as e:
                ss.result = ("error", str(e))
            st.rerun()  # refresh the ledger table (REWOUND_BY)
        if c2.button("🔁 Replay as of then", disabled=r.REPLAYABLE != "Y", width="stretch"):
            try:
                ss.result = ("replay", gateway.replay(int(entry)))
            except Exception as e:
                ss.result = ("error", str(e))
    if ss.result:
        kind, res = ss.result
        if kind == "error":
            st.error(res)
        elif kind == "rewind":
            st.success(f"Rewound as {user}: restored {len(res['before'])} row(s) of {res['table']} "
                       f"to the version before transaction {res['tx_ts']}.")
            b, a = st.columns(2)
            b.markdown("**Before rewind (agent's version)**")
            b.dataframe(pd.DataFrame(res["before"], columns=res["columns"]), hide_index=True)
            a.markdown("**After rewind (restored from history)**")
            a.dataframe(pd.DataFrame(res["after"], columns=res["columns"]), hide_index=True)
            st.code(res["sql"], language="sql", wrap_lines=True)
        else:
            st.markdown(f"**Prompt:** {res['prompt']}  \n**AI answer at the time:** {res['answer']}")
            st.code(f"SET CURRENT TEMPORAL SYSTEM_TIME = TIMESTAMP('{res['as_of']}');  -- as {res['user']}\n{res['sql']};",
                    language="sql")
            then, now = st.columns(2)
            then.markdown(f"**What the AI saw ({res['as_of'][:19]})**")
            then.dataframe(pd.DataFrame(res["then"], columns=res["columns"]), hide_index=True)
            now.markdown("**Same query, same identity, now**")
            now.dataframe(pd.DataFrame(res["now"], columns=res["columns"]), hide_index=True)
            st.markdown("✅ Identical: the data has not changed since." if res["then"] == res["now"]
                        else "⚠️ The data changed since the AI answered. The left side is exactly what it saw.")
