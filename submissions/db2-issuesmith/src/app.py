"""IssueSmith web UI.   Run:  streamlit run src/app.py"""
from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from issuesmith.agents.graph import build_graph  # noqa: E402
from issuesmith.config import KNOWLEDGE_DIR, SAMPLE_LOG_DIR, get_settings  # noqa: E402
from issuesmith.github_client import create_issue  # noqa: E402
from issuesmith.llm import LLMUnavailable  # noqa: E402
from issuesmith.sql_agent import UnsafeSQL, question_to_sql, validate_sql  # noqa: E402
from issuesmith.wiring import build_app  # noqa: E402

st.set_page_config(page_title="IssueSmith · Db2 issue assistant", page_icon="🛠️", layout="wide")
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono&display=swap');
html, body, [class*="css"], .stMarkdown, .stTextInput, .stButton button { font-family: 'IBM Plex Sans', system-ui, sans-serif; }
code, pre, .stCode { font-family: 'IBM Plex Mono', ui-monospace, monospace !important; }
.block-container { padding-top: 2rem; max-width: 1280px; }
h1 { font-weight: 600; letter-spacing: -0.01em; }
.trace-row { font-family: 'IBM Plex Mono', monospace; font-size: 0.85rem; padding: 2px 0; }
.lede { color: #525252; font-size: 1.05rem; max-width: 70ch; }
</style>
""",
    unsafe_allow_html=True,
)

SETTINGS = get_settings()


@st.cache_resource(show_spinner="Connecting to Db2…")
def get_app():
    return build_app(SETTINGS)


def df(rows: list[dict]) -> pd.DataFrame:
    clean = [{k: (float(v) if isinstance(v, Decimal) else v) for k, v in r.items()} for r in rows]
    return pd.DataFrame(clean)


st.title("IssueSmith")
st.markdown(
    '<p class="lede">Turn a messy Db2 Developer Extension log into a maintainer-ready GitHub issue. '
    "Agents redact secrets, extract evidence, search past incidents in Db2, write the report and check it "
    "against the community issue guide before you post.</p>",
    unsafe_allow_html=True,
)

try:
    app = get_app()
except Exception as exc:  # Db2 down / misconfigured
    st.error(f"Db2 is not reachable, so IssueSmith cannot start.\n\n{exc}")
    st.info("Start the Db2 container, wait for “Setup has completed”, check DB2_* in .env, then reload this page.")
    st.stop()

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.subheader("System")
    try:
        st.write(f"**Db2** {app.repo.db2_version()} · `{SETTINGS.db2_database}`")
    except Exception:
        st.write(f"**Db2** `{SETTINGS.db2_database}`")
    try:
        app.repo.check_vector_support()
        st.write("**VECTOR type** available")
    except Exception:
        st.warning("This Db2 build has no VECTOR type (needs 12.1.2+).")
    st.write(f"**Embeddings** {type(app.embeddings).__name__}")
    st.write(f"**LLM** {app.llm.name if app.llm.available else 'none (rule-based writer)'}")
    kb_count = None
    if app.kb is not None:
        try:
            kb_count = app.kb.count()
        except Exception:
            kb_count = None
    st.write(f"**Knowledge docs in Db2** {kb_count if kb_count is not None else 'not loaded'}")
    st.divider()
    if st.button("Set up database", help="Creates tables, views and the procedure, then loads the knowledge base"):
        with st.spinner("Creating schema and loading knowledge base…"):
            dim = len(app.embeddings.embed_query("dimension probe"))
            msgs = app.repo.init_schema(reset=False, dim=dim)
            get_app.clear()
            fresh = get_app()
            n = fresh.kb.seed(KNOWLEDGE_DIR) if fresh.kb else 0
        st.success(f"Schema ready ({len(msgs)} statements). {n} knowledge docs loaded.")
        st.rerun()

tab_analyze, tab_incidents, tab_insights, tab_ask = st.tabs(
    ["Analyze a log", "Incident history", "Insights", "Ask the data"]
)

# ---------------------------------------------------------------- analyze
with tab_analyze:
    left, right = st.columns([3, 2], gap="large")
    with left:
        source = st.radio("Log source", ["Sample log", "Upload a file", "Paste text"], horizontal=True)
        raw_log, source_name = "", "pasted-log"
        if source == "Sample log":
            samples = sorted(SAMPLE_LOG_DIR.glob("*.log"))
            pick = st.selectbox("Sample", samples, format_func=lambda p: p.stem.replace("_", " "))
            raw_log, source_name = pick.read_text(encoding="utf-8"), pick.name
            with st.expander("Show raw log (contains fake secrets on purpose)"):
                st.code(raw_log, language="text")
        elif source == "Upload a file":
            up = st.file_uploader("Db2 Extension log", type=["log", "txt"])
            if up:
                raw_log, source_name = up.getvalue().decode("utf-8", errors="replace"), up.name
        else:
            raw_log = st.text_area("Paste the log", height=220)
    with right:
        user_steps = st.text_area(
            "What were you doing? (optional, one step per line)", height=120,
            placeholder="Opened WSL Ubuntu\nClicked 'Restart Db2' in the extension",
        )
        repro = st.selectbox("Does it happen every time?", ["Not yet confirmed", "Every time", "Intermittently", "Only once"])
        run = st.button("Analyze log", type="primary", disabled=not raw_log.strip())

    if run:
        graph = build_graph(app.services())
        state: dict = {"raw_log": raw_log, "source_name": source_name, "user_steps": user_steps,
                       "reproducibility": "" if repro == "Not yet confirmed" else repro, "trace": []}
        with st.status("Agents at work…", expanded=True) as status:
            try:
                for chunk in graph.stream(state, stream_mode="updates"):
                    for node, update in chunk.items():
                        state.update(update)
                        t = update["trace"][-1]
                        st.markdown(
                            f'<div class="trace-row">✔ <b>{node}</b> · {t["ms"]} ms · {t["detail"]}</div>',
                            unsafe_allow_html=True,
                        )
                status.update(label=f"Incident #{state['incident_id']} drafted", state="complete", expanded=False)
                st.session_state["result"] = state
            except Exception as exc:
                status.update(label="An agent failed", state="error")
                st.exception(exc)

    res = st.session_state.get("result")
    if res:
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Category", res["category"].replace("_", " ").title())
        c2.metric("Confidence", f"{res['confidence']:.0%}")
        c3.metric("Secrets redacted", res["redaction_count"])
        c4.metric("Critic score", f"{res['critic']['score']:.0f}/100", f"{res['round']} round(s)", delta_color="off")
        if res.get("duplicate_of"):
            st.warning(f"This looks like a duplicate of incident #{res['duplicate_of']}. Consider commenting on that issue instead.")

        ev_col, ctx_col = st.columns([3, 2], gap="large")
        with ev_col:
            st.subheader("Evidence from the log")
            st.dataframe(df(res["evidence"])[["line_no", "kind", "label", "log_line"]], hide_index=True, width="stretch")
            st.subheader("Critic checks")
            for c in res["critic"]["checks"]:
                icon = "✅" if c["passed"] else ("❌" if c["blocking"] else "⚠️")
                st.markdown(f"{icon} **{c['name'].replace('_', ' ')}**: {c['message']}")
        with ctx_col:
            st.subheader("Context found")
            if res.get("similar"):
                st.caption("Similar incidents (Db2 VECTOR_DISTANCE via FIND_SIMILAR_INCIDENTS)")
                st.dataframe(df(res["similar"])[["INCIDENT_ID", "CATEGORY", "STATUS", "DISTANCE"]], hide_index=True)
            else:
                st.caption("No earlier incidents to compare yet.")
            for k in res.get("kb_context", []):
                with st.expander(f"📘 {k['title']} · distance {k['distance']:.3f}"):
                    st.write(k["text"])
            for g in res.get("github_matches", []):
                st.markdown(f"🔗 [#{g['number']} {g['title']}]({g['url']}) ({g['state']})")

        st.subheader("Draft issue")
        title = st.text_input("Title", res["title"], key=f"title_{res['incident_id']}")
        body = st.text_area("Body (Markdown)", res["body"], height=420, key=f"body_{res['incident_id']}")
        with st.expander("Preview"):
            st.markdown(f"### {title}\n\n{body}")
        b1, b2, b3 = st.columns(3)
        if b1.button("Save edits to Db2"):
            app.repo.update_final_draft(res["incident_id"], title, body)
            st.success("Saved.")
        b2.download_button("Download .md", f"# {title}\n\n{body}", file_name=f"issue-{res['incident_id']}.md")
        with b3:
            target = SETTINGS.github_target_repo
            if SETTINGS.github_token and target:
                ok = st.checkbox(f"I reviewed this draft. Post to {target}.")
                if st.button("Post to GitHub", disabled=not ok):
                    try:
                        url = create_issue(target, SETTINGS.github_token, title, body)
                        app.repo.mark_posted(res["incident_id"], url)
                        st.success(f"Posted: {url}")
                    except Exception as exc:
                        st.error(str(exc))
            else:
                st.caption("Set GITHUB_TOKEN and GITHUB_TARGET_REPO to post directly.")

# ---------------------------------------------------------------- incidents
with tab_incidents:
    rows = app.repo.recent_incidents()
    if not rows:
        st.info("No incidents yet. Analyze a log to create the first one.")
    else:
        st.dataframe(df(rows), hide_index=True, width="stretch")
        pick = st.selectbox("Open incident", [r["INCIDENT_ID"] for r in rows])
        detail = app.repo.incident_detail(int(pick))
        inc = detail["incident"] or {}
        st.write(f"**{inc.get('CATEGORY')}** · status {inc.get('STATUS')} · source {inc.get('SOURCE_NAME')}")
        if inc.get("ENV_JSON"):
            st.json(json.loads(inc["ENV_JSON"]))
        st.caption("Agent audit trail (AGENT_RUNS)")
        st.dataframe(df(detail["runs"]), hide_index=True, width="stretch")
        for d in detail["drafts"]:
            label = f"Round {d['ROUND_NO']} · score {float(d['CRITIC_SCORE']):.0f} · {d['GENERATED_BY']}" + (" · final" if d["IS_FINAL"] == "Y" else "")
            with st.expander(label):
                st.markdown(f"### {d['TITLE']}\n\n{d['BODY_MD']}")

# ---------------------------------------------------------------- insights
with tab_insights:
    stats = app.repo.category_stats()
    if not stats:
        st.info("Insights appear after the first analysed log.")
    else:
        a, b = st.columns(2, gap="large")
        with a:
            st.subheader("Incidents by category")
            st.bar_chart(df(stats).set_index("CATEGORY")["INCIDENTS"])
        with b:
            st.subheader("Average agent latency (ms)")
            perf = app.repo.agent_performance()
            if perf:
                st.bar_chart(df(perf).set_index("AGENT")["AVG_LATENCY_MS"])
        st.subheader("Most frequent error signatures")
        st.dataframe(df(app.repo.top_signatures()), hide_index=True, width="stretch")
        env_rows = app.repo.env_breakdown()
        if env_rows:
            st.subheader("Where failures happen (JSON_VALUE over ENV_JSON)")
            st.dataframe(df(env_rows), hide_index=True, width="stretch")
        st.subheader("Draft quality")
        st.dataframe(df(app.repo.draft_quality()), hide_index=True, width="stretch")

# ---------------------------------------------------------------- ask
with tab_ask:
    st.write("Ask about your incident data in plain English. The analyst agent writes read-only Db2 SQL, "
             "which is validated before it runs.")
    examples = [
        "Which error signatures appear in more than one incident?",
        "How many incidents per category were flagged as duplicates?",
        "What is the average critic score by generator?",
    ]
    q = st.text_input("Question", placeholder=examples[0])
    st.caption("Try: " + " · ".join(examples))
    if st.button("Ask", disabled=not q):
        try:
            st.session_state["sql"] = question_to_sql(app.llm, q, SETTINGS.db2_schema)
        except (LLMUnavailable, UnsafeSQL) as exc:
            st.warning(str(exc))
    sql = st.text_area("SQL (you can edit it)", st.session_state.get("sql", f"SELECT * FROM {SETTINGS.db2_schema}.V_CATEGORY_STATS"), height=120)
    if st.button("Run SQL"):
        try:
            safe = validate_sql(sql, SETTINGS.db2_schema)
            st.code(safe, language="sql")
            st.dataframe(df(app.repo.run_readonly(safe)), hide_index=True, width="stretch")
        except UnsafeSQL as exc:
            st.error(f"Blocked: {exc}")
        except Exception as exc:
            st.error(f"Db2 rejected the query: {exc}")
