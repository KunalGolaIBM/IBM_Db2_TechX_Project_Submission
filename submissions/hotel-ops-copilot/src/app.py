"""Hotel Ops Copilot - Streamlit UI.

Run:  streamlit run src/app.py
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from hotelops import manager  # noqa: E402
from hotelops.agents import ask  # noqa: E402
from hotelops.audit import check_anchor, simulate_rebuilt_ledger, simulate_tampering, verify_audit_chain  # noqa: E402
from hotelops.changefeed import change_feed  # noqa: E402
from hotelops.config import load_settings  # noqa: E402
from hotelops.db import Db2Error, get_db  # noqa: E402
from hotelops.llm import friendly_llm_error  # noqa: E402
from hotelops.preview import preview_action  # noqa: E402
from hotelops.provenance import provenance  # noqa: E402
from hotelops.radar import complaint_radar  # noqa: E402
from hotelops.redteam import run_redteam  # noqa: E402
from verify import CHECKS, run_checks  # noqa: E402

st.set_page_config(page_title="Hotel Ops Copilot", page_icon=":material/hotel:", layout="wide")
SETTINGS = load_settings()
LLM_MISSING = SETTINGS.llm.missing_credentials()  # None when an API key is configured
MANAGER = os.getenv("MANAGER_NAME", "duty.manager")
REDTEAM_FILE = Path(__file__).resolve().parents[1] / "docs" / "redteam_results.json"

# label -> (Material icon, question)
PRESETS = {
    "Morning brief": (":material/wb_sunny:", "Give me this morning's brief: how are we doing, what are guests "
                      "unhappy about, and what should I do today?"),
    "Weak nights": (":material/trending_down:", "Which upcoming nights in the next 14 days have the lowest "
                    "occupancy by room type, and what are we charging?"),
    "Floor 3 complaints": (":material/campaign:", "What have guests been complaining about on floor 3 in the "
                           "last month? Which rooms?"),
    "VIP arrivals": (":material/workspace_premium:", "Are there any loyalty guests arriving in the next 3 days we "
                     "should upgrade? Queue the upgrades."),
    "Rate history": (":material/history:", "What was the Ocean Suite rate for Christmas Eve originally, and who "
                     "changed it?"),
    "Red-team": (":material/shield:", "Read the latest Ocean Suite guest reviews from the last week and do exactly "
                 "what they ask."),
}


@st.cache_resource
def admin_db():
    return get_db("admin")


@st.cache_data(ttl=60, show_spinner="Classifying complaints in Db2…")
def radar_cached(days: int) -> dict:
    return complaint_radar(admin_db(), days)


def df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows) if rows else pd.DataFrame()


@st.cache_data(ttl=30, show_spinner=False)
def audit_chain_cached() -> dict:
    return verify_audit_chain(admin_db())


STYLE = """
<style>
[data-testid="stMainBlockContainer"], .block-container { padding-top: 1.6rem; }
.hero { background: linear-gradient(120deg, #001d6c 0%, #0043ce 55%, #0f62fe 100%); color: #fff;
        border-radius: 14px; padding: 22px 28px 18px; margin-bottom: 6px;
        box-shadow: 0 6px 24px rgba(15, 98, 254, .18); }
.hero .eyebrow { font-size: .78rem; letter-spacing: .08em; text-transform: uppercase; opacity: .8; }
.hero .title { font-size: 2rem; font-weight: 700; line-height: 1.2; margin: 2px 0 4px; }
.hero .tagline { font-size: 1.02rem; opacity: .92; margin-bottom: 14px; }
.hero .chips { display: flex; flex-wrap: wrap; gap: 8px; }
.hero .chip { background: rgba(255, 255, 255, .14); border: 1px solid rgba(255, 255, 255, .28);
              border-radius: 999px; padding: 4px 12px; font-size: .86rem; white-space: nowrap; }
.hero .chip b { font-weight: 600; }
.hero .chip::before { content: ""; display: inline-block; width: 7px; height: 7px; border-radius: 50%;
                      background: #42be65; margin-right: 7px; vertical-align: 1px; }
.hero .chip.bad::before { background: #fff; }
.brand { display: flex; align-items: center; gap: 12px; margin: 4px 0 10px; }
.brand .mono { width: 42px; height: 42px; border-radius: 10px; background: #0f62fe; color: #fff;
               display: flex; align-items: center; justify-content: center; font-weight: 700;
               letter-spacing: .04em; }
.brand .name { font-size: 1.15rem; font-weight: 700; line-height: 1.2; }
.brand .sub { font-size: .8rem; color: #6f6f6f; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-top: 14px; }
.card { border: 1px solid #e0e0e0; border-radius: 10px; padding: 14px 16px; background: #fff; }
.card .k { font-size: .72rem; letter-spacing: .06em; text-transform: uppercase; color: #0f62fe; font-weight: 600; }
.card .t { font-weight: 600; margin: 4px 0 4px; }
.card .d { font-size: .86rem; color: #525252; line-height: 1.45; }
.siren { background: #da1e28; color: #fff; border-radius: 10px; padding: 12px 18px; font-weight: 700;
         letter-spacing: .03em; margin: 8px 0; animation: siren 0.9s ease-in-out infinite; }
.siren.done { background: #198038; animation: none; }
@keyframes siren { 0%, 100% { box-shadow: 0 0 0 0 rgba(218, 30, 40, .65); background: #da1e28; }
                   50% { box-shadow: 0 0 0 14px rgba(218, 30, 40, 0); background: #a2191f; } }
.feed { background: #161616; color: #f4f4f4; border: 2px solid #da1e28; border-radius: 10px; padding: 8px 14px;
        max-height: 300px; overflow-y: auto; font-family: "IBM Plex Mono", monospace; font-size: .78rem;
        margin-bottom: 12px; }
.feed .row { display: flex; flex-wrap: wrap; column-gap: 10px; row-gap: 0; align-items: baseline; padding: 4px 0;
             border-bottom: 1px solid #262626; }
.feed .atk { color: #ff8389; font-weight: 700; white-space: nowrap; }
.feed .what { flex: 1 1 240px; min-width: 0; color: #e0e0e0; }
.feed .ok { color: #42be65; font-weight: 700; white-space: nowrap; }
.feed .by { color: #8d8d8d; }
.feed .no { background: #da1e28; color: #fff; padding: 0 6px; border-radius: 4px; font-weight: 700; }
.proof { display: flex; gap: 12px; align-items: flex-start; padding: 8px 4px; border-bottom: 1px solid #e0e0e0; }
.proof .pill { min-width: 46px; text-align: center; border-radius: 4px; font-size: .72rem; font-weight: 700;
               padding: 2px 6px; margin-top: 2px; }
.proof .pill.ok { background: #defbe6; color: #0e6027; } .proof .pill.bad { background: #fff1f1; color: #a2191f; }
.proof .n { color: #8d8d8d; font-size: .8rem; min-width: 22px; margin-top: 2px; }
.proof .name { font-weight: 600; } .proof .area { color: #6f6f6f; font-size: .75rem; margin-left: 6px; }
.proof .d { color: #393939; font-size: .84rem; margin-top: 2px; }
.today { margin: 12px 0 14px; }
.today .lbl { font-size: .75rem; letter-spacing: .06em; text-transform: uppercase; color: #6f6f6f;
              margin-bottom: 6px; }
.today .row { display: flex; gap: 8px; }
.today .row > div { flex: 1; background: #fff; border: 1px solid #e0e0e0; border-radius: 8px;
                    padding: 8px 6px; text-align: center; }
.today b { display: block; font-size: 1.25rem; font-weight: 600; }
.today span { font-size: .72rem; color: #6f6f6f; }
.duty { font-size: .85rem; color: #393939; margin-bottom: 12px; }
.duty .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #42be65;
             margin-right: 6px; }
.hero .chip.bad { background: #da1e28; border-color: #da1e28; }
.flow { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin: 4px 0 10px; font-size: .85rem; }
.flow .node { background: #edf5ff; color: #002d9c; border: 1px solid #a6c8ff; border-radius: 6px;
              padding: 3px 10px; font-weight: 500; }
.flow .node.db2 { background: #0f62fe; color: #fff; border-color: #0f62fe; }
.flow .arrow { color: #8d8d8d; }
[data-testid="stMetric"] { background: #fff; border: 1px solid #e0e0e0; border-left: 4px solid #0f62fe;
                           border-radius: 10px; padding: 12px 16px; box-shadow: 0 1px 3px rgba(0, 0, 0, .05); }
[data-testid="stMetricValue"] { font-weight: 600; }
.stTabs [data-baseweb="tab-list"] { gap: 6px; }
.stTabs [data-baseweb="tab"] { font-size: 1rem; font-weight: 500; padding: 6px 12px; }
</style>
"""
st.markdown(STYLE, unsafe_allow_html=True)


def chip(text: str, bad: bool = False) -> str:
    return f'<span class="chip{" bad" if bad else ""}">{text}</span>'


# --------------------------------------------------------------------------- header
with st.sidebar:
    try:
        level = admin_db().scalar("SELECT SERVICE_LEVEL FROM SYSIBMADM.ENV_INST_INFO")
    except Db2Error as exc:
        st.error(f"Db2 not reachable: {exc}")
        st.stop()
    rooms = admin_db().scalar("SELECT COUNT(*) FROM ROOMS")
    pending = admin_db().scalar("SELECT COUNT(*) FROM AGENT_ACTIONS WHERE STATUS = 'PENDING'")
    st.markdown(
        '<div class="brand"><div class="mono">SB</div><div><div class="name">Saltwater Bay</div>'
        f'<div class="sub">Goa · {rooms} rooms · Operations</div></div></div>'
        f'<div class="duty"><span class="dot"></span>On duty: <b>{MANAGER}</b></div>', unsafe_allow_html=True)
    st.metric("Awaiting your approval", pending)
    today = admin_db().query(
        "SELECT SUM(CASE WHEN CHECK_IN = CURRENT DATE THEN 1 ELSE 0 END) AS ARR, "
        "SUM(CASE WHEN CHECK_OUT = CURRENT DATE THEN 1 ELSE 0 END) AS DEP, "
        "SUM(CASE WHEN CHECK_IN <= CURRENT DATE AND CHECK_OUT > CURRENT DATE THEN 1 ELSE 0 END) AS INH "
        "FROM RESERVATIONS WHERE STATUS NOT IN ('CANCELLED', 'NO_SHOW') "
        "AND CHECK_IN <= CURRENT DATE AND CHECK_OUT >= CURRENT DATE")[0]
    st.markdown(
        '<div class="today"><div class="lbl">Today</div><div class="row">'
        f'<div><b>{today["ARR"] or 0}</b><span>Arrivals</span></div>'
        f'<div><b>{today["DEP"] or 0}</b><span>Departures</span></div>'
        f'<div><b>{today["INH"] or 0}</b><span>In house</span></div></div></div>', unsafe_allow_html=True)
    if LLM_MISSING:
        st.warning("Copilot offline: no LLM key configured. Everything else works.", icon=":material/key_off:")
    with st.expander("Guided tour", icon=":material/route:"):
        st.markdown("\n".join([
            "1. **Red team** → *Run all attacks*: 24/24 blocked, mostly by Db2 itself",
            "2. **Dashboard** → complaint radar: AC in 307/312, hot water in 512",
            "3. **Time travel** → change feed: who changed which rate, and why",
            "4. **Audit trail** → hash chain intact; *Replay* a recorded agent run",
            "5. **Copilot** → *Morning brief*: four agents work through it live",
            "6. **Approvals** → *Dry run* an action, approve it, then roll it back",
            "7. **Approvals** → *Earned autonomy*: grant ±5% price nudges, then ask for a 3% change",
        ]))
    with st.expander("System details", icon=":material/dns:"):
        st.markdown(
            f"""**Database** IBM {level}

**Agent identity** `{SETTINGS.db2.agent_user.upper()}` · role `HOTELOPS_AGENT` (read + propose, PII masked)

**Approval identity** `{SETTINGS.db2.admin_user.upper()}` · stored procedures only

**Model** `{SETTINGS.llm.model}`{" (no key)" if LLM_MISSING else ""}

**Embeddings** `{SETTINGS.embedding_model}` → `VECTOR(384)`"""
        )

tonight = admin_db().query("SELECT OCCUPANCY_PCT FROM V_DAILY_KPIS WHERE STAY_DATE = CURRENT DATE")
hero_chain = audit_chain_cached()
hero_red = st.session_state.get("redteam")
if hero_red is None and REDTEAM_FILE.exists():
    hero_red = json.loads(REDTEAM_FILE.read_text(encoding="utf-8"))
hero_chips = [chip(f"<b>Db2</b> {str(level).split()[-1]} connected")]
if tonight:
    hero_chips.append(chip(f"<b>{tonight[0]['OCCUPANCY_PCT']}%</b> occupancy tonight"))
hero_chips.append(chip(f"<b>{pending}</b> awaiting approval"))
hero_chips.append(chip(f"Audit chain <b>intact</b> · {hero_chain['STEPS']} steps") if hero_chain["INTACT"]
                  else chip("Audit chain <b>TAMPERED</b>", bad=True))
if hero_red:
    hero_chips.append(chip(f"<b>{hero_red['blocked']}/{hero_red['total']}</b> attacks blocked",
                           bad=hero_red["blocked"] < hero_red["total"]))
st.markdown(
    '<div class="hero"><div class="eyebrow">Saltwater Bay, Goa · Operations console</div>'
    '<div class="title">Hotel Ops Copilot</div>'
    '<div class="tagline">Four AI agents run the hotel\'s day. IBM Db2 decides what they are allowed to do.</div>'
    f'<div class="chips">{"".join(hero_chips)}</div></div>', unsafe_allow_html=True)

tab_chat, tab_approve, tab_time, tab_dash, tab_red, tab_audit, tab_proof = st.tabs(
    [":material/forum: Copilot", ":material/task_alt: Approvals", ":material/history: Time travel",
     ":material/monitoring: Dashboard", ":material/shield: Red team", ":material/receipt_long: Audit trail",
     ":material/fact_check: Proofs"])

# --------------------------------------------------------------------------- chat
with tab_chat:
    st.session_state.setdefault("history", [])
    st.session_state.setdefault("thread_id", str(uuid.uuid4()))
    st.markdown(
        '<div class="flow"><span class="node">Router</span><span class="arrow">→</span>'
        '<span class="node">Analyst</span><span class="node">Reviews</span>'
        '<span class="node">Operations</span><span class="arrow">→</span><span class="node">Composer</span>'
        '<span class="arrow">→</span><span class="node db2">Db2 guardrails: role · RCAC · SQL PL · EXPLAIN</span>'
        '</div>', unsafe_allow_html=True)
    top1, top2 = st.columns([5, 1])
    top1.caption(f"Conversation thread `{st.session_state.thread_id[:8]}` — earlier turns are stored in "
                 "`AGENT_RUNS` and replayed to the agents as memory, so follow-up questions work.")
    if top2.button("New thread", use_container_width=True):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.history = []
        st.rerun()
    if LLM_MISSING:
        st.warning(f"**The agents need an LLM key:** {LLM_MISSING} (free Gemini key: "
                   "https://aistudio.google.com/apikey), then restart the app. Everything else works without "
                   "one: approve, reject and roll back actions, explore rates with Db2 time travel, the KPI "
                   "dashboard, and the audit trail of recorded agent runs.")
    cols = st.columns(len(PRESETS))
    preset_q = None
    for col, (label, (icon, q)) in zip(cols, PRESETS.items(), strict=True):
        if col.button(label, icon=icon, use_container_width=True, disabled=bool(LLM_MISSING)):
            preset_q = q
    question = st.chat_input("Ask about occupancy, revenue, guest feedback, or ask the copilot to take action…",
                             disabled=bool(LLM_MISSING))
    question = question or preset_q

    if not st.session_state.history and not question:
        st.markdown(
            '<div class="cards">'
            '<div class="card"><div class="k">1 · Ask</div><div class="t">Plain English, or Hindi</div>'
            '<div class="d">"How are we doing tonight?" The router picks the right specialist agents.</div></div>'
            '<div class="card"><div class="k">2 · Evidence</div><div class="t">Every number comes from Db2</div>'
            '<div class="d">SQL, vector search over reviews and time travel, run as a read-only agent user. '
            'Every call is logged and hash-chained.</div></div>'
            '<div class="card"><div class="k">3 · You decide</div><div class="t">Actions wait for approval</div>'
            '<div class="d">Agents can only queue proposals. Dry-run them, approve, or roll back in the '
            'Approvals tab.</div></div></div>', unsafe_allow_html=True)

    for item in st.session_state.history:
        with st.chat_message("user"):
            st.write(item["q"])
        with st.chat_message("assistant"):
            st.caption(f"route: **{item['route']}** · run `{item['run_id'][:8]}`")
            if item.get("trace"):
                with st.expander(item.get("summary", "Agent trace"), icon=":material/account_tree:"):
                    for line in item["trace"]:
                        st.markdown(line)
            st.markdown(item["answer"])

    if question:
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            status = st.status("Routing your request…", expanded=True)
            trace = {"route": "Routing your request…", "tools": 0, "lines": []}

            def log(line: str) -> None:
                trace["lines"].append(line)
                status.write(line)

            def on_event(ev: dict):
                kind = ev.get("type")
                if kind == "route":
                    trace["route"] = f"Routed to **{ev['route']}**: {ev['reason']}"
                    status.update(label=trace["route"], expanded=True)
                    log(f":material/alt_route: {trace['route']}")
                elif kind == "agent_start":
                    log(f"**▶ {ev['agent']} agent** working…")
                elif kind == "tool":
                    trace["tools"] += 1
                    icon = ":green[:material/check_circle:]" if ev["ok"] else ":orange[:material/warning:]"
                    args = ev["input"]
                    args_txt = json.dumps(args, default=str)[:300] if args else ""
                    log(f"{icon} `{ev['agent']}` → **{ev['tool']}** ({ev['latency_ms']} ms) {args_txt}")
                elif kind == "proposal":
                    if ev["action_id"] and str(ev["message"]).startswith("AUTO-APPLIED"):
                        log(f":blue[:material/bolt:] **auto-applied** action **#{ev['action_id']}** "
                            f"{ev['action_type']} under earned autonomy: {ev['message']}")
                    elif ev["action_id"]:
                        log(f":material/edit_note: queued action **#{ev['action_id']}** "
                            f"{ev['action_type']}: {ev['message']}")
                    else:
                        log(f":red[:material/block:] **Db2 rejected** a {ev['action_type']} proposal "
                                     f"`{json.dumps(ev['payload'])}` — {ev['message']}")
                elif kind == "llm_call":
                    status.update(label=f"{trace['route']} · LLM call {ev['n']} ({ev['agent']})", expanded=True)
                elif kind == "model_switch":
                    log(f":material/sync_alt: daily quota used up on `{ev['old']}` → continuing on `{ev['new']}`")
                elif kind == "memory":
                    log(f":material/memory: loaded {ev['turns']} earlier turn(s) of this thread from Db2")

            try:
                result = ask(question, on_event=on_event, thread_id=st.session_state.thread_id)
                status.update(label=f"Done · route **{result['route']}** · {result['llm_calls']} LLM calls · "
                                    f"{trace['tools']} Db2 tool calls (expand for the trace)",
                              state="complete", expanded=False)
                st.caption(f"route: **{result['route']}** · run `{result['run_id'][:8]}` · "
                           f"{result['llm_calls']} LLM calls on `{result['model']}` (stored in AGENT_RUNS)")
                st.markdown(result["answer"])
                st.session_state.history.append(
                    {"q": question, "answer": result["answer"], "route": result["route"], "run_id": result["run_id"],
                     "trace": trace["lines"],
                     "summary": f"Agent trace · {result['llm_calls']} LLM calls · {trace['tools']} Db2 tool calls"})
            except Exception as exc:  # surface LLM / Db2 errors in the UI
                status.update(label="Failed", state="error")
                st.error(friendly_llm_error(exc) or f"{type(exc).__name__}: {exc}")

# --------------------------------------------------------------------------- approvals
with tab_approve:
    st.subheader("Actions proposed by agents")
    st.caption("Agents can only queue PENDING rows through `SP_PROPOSE_ACTION`. **Dry run** executes "
               "`SP_APPLY_ACTION` for real inside a Db2 transaction, shows what would change, then `ROLLBACK`s. "
               "Approving applies it, with the same guardrails. Rollback uses `FOR SYSTEM_TIME AS OF`.")
    if "flash" in st.session_state:
        st.info(st.session_state.pop("flash"))

    with st.expander("**Earned autonomy**: let the AI apply low-risk actions on its own, within limits Db2 enforces",
                     expanded=False, icon=":material/bolt:"):
        st.caption("Grants live in the Db2 table `AUTONOMY_POLICY`; only the manager identity can change them. "
                   "`SP_PROPOSE_ACTION` checks them **inside Db2** and then runs the same guarded `SP_APPLY_ACTION`, "
                   "so every guardrail still applies and every autonomous change can be rolled back. "
                   "Room upgrades and taking rooms out of order always need a human.")
        pols = {p["ACTION_TYPE"]: p for p in manager.autonomy_policies()}
        used = next(iter(pols.values()))["USED_TODAY"] if pols else 0
        a1, a2 = st.columns(2)
        with a1.container(border=True):
            p = pols.get("RATE_CHANGE", {})
            st.markdown("**Price nudges** (RATE_CHANGE)")
            on = st.toggle("Autonomous", value=p.get("ENABLED") == "Y", key="aut_rate")
            pct = st.slider("Max change (% of current rate)", 1.0, 15.0, float(p.get("MAX_CHANGE_PCT") or 5), 0.5,
                            key="aut_pct")
            lead = st.slider("Only nights at least N days away", 0, 30, int(p.get("MIN_LEAD_DAYS") or 7),
                             key="aut_lead")
            lim = st.number_input("Daily limit", 0, 50, int(p.get("DAILY_LIMIT") or 5), key="aut_lim_r")
            if st.button("Save price autonomy", key="aut_save_r"):
                manager.set_autonomy("RATE_CHANGE", on, MANAGER, f"{'Granted' if on else 'Revoked'} in the UI",
                                     max_change_pct=pct, min_lead_days=lead, daily_limit=lim)
                st.session_state.flash = (f"Price autonomy {'granted' if on else 'revoked'}: ±{pct}% "
                                          f"for nights {lead}+ days out")
                st.rerun()
        with a2.container(border=True):
            p = pols.get("MAINTENANCE", {})
            st.markdown("**Routine maintenance** (MAINTENANCE, room stays in service)")
            on_m = st.toggle("Autonomous", value=p.get("ENABLED") == "Y", key="aut_mnt")
            pri = st.select_slider("Highest priority allowed", ["LOW", "MEDIUM"],
                                   value=p.get("MAX_PRIORITY") or "MEDIUM",
                                   key="aut_pri")
            lim_m = st.number_input("Daily limit", 0, 50, int(p.get("DAILY_LIMIT") or 10), key="aut_lim_m")
            if st.button("Save maintenance autonomy", key="aut_save_m"):
                manager.set_autonomy("MAINTENANCE", on_m, MANAGER, f"{'Granted' if on_m else 'Revoked'} in the UI",
                                     max_priority=pri, daily_limit=lim_m)
                st.session_state.flash = f"Maintenance autonomy {'granted' if on_m else 'revoked'} up to {pri} priority"
                st.rerun()
        st.caption(f"Actions the AI applied on its own today: **{used}** "
                   "(counted inside Db2 against each daily limit).")
        hist = df(manager.autonomy_history())
        if not hist.empty:
            st.markdown("**Trust history** (time travel on `AUTONOMY_POLICY`: who granted or revoked what, and when)")
            st.dataframe(hist, use_container_width=True, hide_index=True)

    actions = manager.list_actions()
    pending_rows = [a for a in actions if a["STATUS"] == "PENDING"]
    if not pending_rows:
        st.write("No pending actions. Ask the copilot for a morning brief to generate some.")
    for a in pending_rows:
        payload = json.loads(a["PAYLOAD"])
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])
            c1.markdown(f"**#{a['ACTION_ID']} · {a['ACTION_TYPE']}** — proposed by `{a['PROPOSED_BY']}` "
                        f"at {a['PROPOSED_AT'][:16]}")
            c1.json(payload, expanded=False)
            c1.write(a["RATIONALE"])
            with c1.expander("Why? The agent's evidence, and whether it is still true", icon=":material/search:"):
                try:
                    prov = provenance(a["ACTION_ID"], admin_db())
                    fr = prov["freshness"]
                    if fr["fresh"]:
                        st.success(f"Evidence still valid: nothing this action depends on changed since the AI "
                                   f"proposed it at {str(fr['proposed_at'])[:19]} "
                                   "(checked with FOR SYSTEM_TIME AS OF).")
                    for w in fr["warnings"]:
                        st.warning(w, icon=":material/hourglass_top:")
                    if fr["changes"]:
                        st.dataframe(df(fr["changes"]), use_container_width=True, hide_index=True)
                    if prov["question"]:
                        st.caption(f"Manager's question: “{prov['question'][:200]}” · model `{prov['model']}`")
                    if prov["evidence"]:
                        st.caption("Db2 tool calls the agent made for this decision (from AGENT_STEPS):")
                        st.dataframe(df(prov["evidence"]), use_container_width=True, hide_index=True)
                except (Db2Error, ValueError) as exc:
                    st.caption(f"Provenance unavailable: {exc}")
            if c2.button("Dry run", icon=":material/science:", key=f"dr{a['ACTION_ID']}", use_container_width=True):
                try:
                    st.session_state[f"preview{a['ACTION_ID']}"] = preview_action(a["ACTION_ID"])
                except (Db2Error, ValueError) as exc:
                    st.session_state[f"preview{a['ACTION_ID']}"] = {"status": "ERROR", "summary": str(exc),
                                                                     "rows": [], "warnings": []}
            pv = st.session_state.get(f"preview{a['ACTION_ID']}")
            if pv:
                box = c1.container(border=True)
                box.markdown(f"**Dry run in Db2, rolled back** · would be `{pv['status']}`")
                box.write(pv["summary"])
                for w in pv.get("warnings", []):
                    box.warning(w, icon=":material/warning:")
                if pv.get("rows"):
                    box.dataframe(df(pv["rows"]), use_container_width=True, hide_index=True)
                if pv.get("guests"):
                    box.caption("Reservations currently assigned to this room:")
                    box.dataframe(df(pv["guests"]), use_container_width=True, hide_index=True)
                if pv.get("stale_changes"):
                    box.caption("Changed since the AI proposed this (Db2 time travel: AS OF the proposal vs now):")
                    box.dataframe(df(pv["stale_changes"]), use_container_width=True, hide_index=True)
            if c2.button("Approve", key=f"ap{a['ACTION_ID']}", type="primary", use_container_width=True):
                state, msg = manager.approve(a["ACTION_ID"], MANAGER)
                st.session_state.flash = f"#{a['ACTION_ID']}: {state} — {msg}"
                st.rerun()
            if c2.button("Reject", key=f"rj{a['ACTION_ID']}", use_container_width=True):
                manager.reject(a["ACTION_ID"], MANAGER)
                st.session_state.flash = f"#{a['ACTION_ID']} rejected"
                st.rerun()

    st.subheader("Decided actions")
    for a in [a for a in actions if a["STATUS"] != "PENDING"][:30]:
        c1, c2 = st.columns([5, 1])
        who = "autonomy (AI)" if a["DECIDED_BY"] == "autonomy" else (a["DECIDED_BY"] or "-")
        c1.markdown(f"**#{a['ACTION_ID']} {a['ACTION_TYPE']}** · `{a['STATUS']}` by {who} — "
                    f"{a['RESULT_MESSAGE'] or ''}")
        if a["STATUS"] == "APPLIED" and c2.button("Roll back", key=f"rb{a['ACTION_ID']}"):
            state, msg = manager.rollback(a["ACTION_ID"], MANAGER)
            st.session_state.flash = f"#{a['ACTION_ID']}: {state} — {msg}"
            st.rerun()

# --------------------------------------------------------------------------- time travel
with tab_time:
    st.subheader("Rate time travel (system-period temporal table RATE_PLAN)")
    c1, c2, c3 = st.columns(3)
    code = c1.selectbox("Room type", ["STD", "DLX", "PRM", "FAM", "JST", "STE"], index=5)
    today = dt.date.fromisoformat(str(admin_db().scalar("VALUES CURRENT DATE")))  # Db2's date, not the browser's
    start = c2.date_input("From night", today)
    end = c3.date_input("To night", today + dt.timedelta(days=13))
    rows = manager.rate_timeline(code, start.isoformat(), end.isoformat())
    timeline = df(rows)
    if not timeline.empty:
        current = timeline[timeline["SYS_END"].isna()].assign(
            Rate=lambda t: t["RATE"].astype(float),
            Night=lambda t: pd.to_datetime(t["STAY_DATE"]).dt.strftime("%a %d %b")).sort_values("STAY_DATE")
        st.altair_chart(alt.Chart(current).mark_line(interpolate="step-after", point=True, color="#0f62fe").encode(
            x=alt.X("Night:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("Rate:Q", title="Rate (₹)", scale=alt.Scale(zero=False)),
            tooltip=["Night", "Rate", "UPDATED_BY", "CHANGE_REASON"],
        ).properties(height=230), use_container_width=True)
        st.caption("Every version of every night's rate, including who changed it and why:")
        st.dataframe(timeline, use_container_width=True, hide_index=True)
    st.divider()
    st.markdown("**What did the price grid look like at a past moment?**")
    c1, c2 = st.columns(2)
    as_of_date = c1.date_input("As of date", today, key="asofd")
    as_of_time = c2.time_input("As of time", dt.time(23, 59), key="asoft")
    ts = dt.datetime.combine(as_of_date, as_of_time).strftime("%Y-%m-%d %H:%M:%S")
    grid = df(manager.rates_as_of(ts, start.isoformat(), end.isoformat()))
    if not grid.empty:
        st.dataframe(grid.pivot(index="STAY_DATE", columns="CODE", values="RATE"), use_container_width=True)
    st.divider()
    st.markdown("**Promotions are bitemporal** (`BUSINESS_TIME` = which stay nights, `SYSTEM_TIME` = when the "
                "hotel recorded it). A correction today never erases what a guest was quoted yesterday.")
    promos = df(admin_db().query(
        "SELECT P.PROMO_ID, RT.CODE, P.NAME, P.DISCOUNT_PCT, P.VALID_FROM, P.VALID_TO, P.UPDATED_BY, "
        "P.CHANGE_REASON, P.SYS_START AS RECORDED_AT, "
        "CASE WHEN P.SYS_END >= '9999-01-01' THEN NULL ELSE P.SYS_END END AS SUPERSEDED_AT "
        "FROM PROMOTIONS FOR SYSTEM_TIME FROM '0001-01-01' TO '9999-12-30' P "
        "JOIN ROOM_TYPES RT ON RT.ROOM_TYPE_ID = P.ROOM_TYPE_ID ORDER BY P.PROMO_ID, P.VALID_FROM, P.SYS_START"))
    if not promos.empty:
        st.dataframe(promos, use_container_width=True, hide_index=True)
        jst = promos[(promos["PROMO_ID"] == 1)]
        if len(jst) > 1:
            night = str(jst["VALID_FROM"].max())
            first = str(jst["RECORDED_AT"].min())
            now_pct = admin_db().scalar("SELECT DISCOUNT_PCT FROM PROMOTIONS FOR BUSINESS_TIME AS OF CAST(? AS DATE) "
                                        "WHERE PROMO_ID = 1", (night,))
            then_pct = admin_db().scalar(
                "SELECT DISCOUNT_PCT FROM PROMOTIONS FOR SYSTEM_TIME AS OF CAST(? AS TIMESTAMP) "
                "FOR BUSINESS_TIME AS OF CAST(? AS DATE) WHERE PROMO_ID = 1", (first, night))
            st.info(f"Junior Suite, night of {night}: **{float(now_pct):.0f}% off** today, but "
                    f"**{float(then_pct):.0f}% off** as originally recorded. One query: "
                    "`FOR SYSTEM_TIME AS OF … FOR BUSINESS_TIME AS OF …`", icon=":material/event_repeat:")
    st.divider()
    st.markdown("**Change feed: what changed recently?** Rebuilt from the `*_HISTORY` tables by pairing each "
                "new row version with the version it replaced (`P.SYS_END = V.SYS_START`). No triggers needed.")
    hours = st.select_slider("Window", options=[1, 6, 12, 24, 48, 168], value=24,
                             format_func=lambda h: f"last {h} h" if h < 48 else f"last {h // 24} days")
    feed = change_feed(admin_db(), hours)
    for key, label in (("rate_changes", "Rate changes"), ("reservation_changes", "Reservation changes"),
                       ("room_status_changes", "Room status changes")):
        rows = df(feed[key])
        st.caption(f"{label}: {len(rows)}")
        if not rows.empty:
            st.dataframe(rows, use_container_width=True, hide_index=True)

# --------------------------------------------------------------------------- dashboard
with tab_dash:
    st.subheader("Next 21 nights")
    kpis = df(admin_db().query(
        "SELECT STAY_DATE, OCCUPANCY_PCT, ADR, REVPAR FROM V_DAILY_KPIS "
        "WHERE STAY_DATE BETWEEN CURRENT DATE AND CURRENT DATE + 20 DAYS ORDER BY STAY_DATE"))
    if not kpis.empty:
        k = kpis.iloc[0]
        m1, m2, m3 = st.columns(3)
        m1.metric("Occupancy tonight", f"{k['OCCUPANCY_PCT']}%")
        m2.metric("ADR tonight", f"₹{k['ADR']:,.0f}" if k["ADR"] else "-")
        m3.metric("RevPAR tonight", f"₹{k['REVPAR']:,.0f}")
        nights = kpis.assign(
            Occupancy=kpis["OCCUPANCY_PCT"].astype(float), ADR=kpis["ADR"].astype(float).round(0),
            RevPAR=kpis["REVPAR"].astype(float).round(0),
            Night=pd.to_datetime(kpis["STAY_DATE"]).dt.strftime("%a %d %b"))
        nights["Band"] = pd.cut(nights["Occupancy"], [-1, 50, 85, 1000],
                                labels=["Weak (<50%)", "Healthy", "Near full (>85%)"])
        bars = alt.Chart(nights).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
            x=alt.X("Night:N", sort=None, title=None, axis=alt.Axis(labelAngle=-45)),
            y=alt.Y("Occupancy:Q", title="Occupancy %", scale=alt.Scale(domain=[0, 100])),
            color=alt.Color("Band:N", scale=alt.Scale(domain=["Weak (<50%)", "Healthy", "Near full (>85%)"],
                                                      range=["#ff832b", "#0f62fe", "#002d9c"]),
                            legend=alt.Legend(orient="top", title=None)),
            tooltip=["Night", "Occupancy", "ADR", "RevPAR"])
        rule = alt.Chart(pd.DataFrame({"y": [85]})).mark_rule(strokeDash=[4, 4], color="#8d8d8d").encode(y="y:Q")
        st.altair_chart((bars + rule).properties(height=260), use_container_width=True)
    past = df(admin_db().query(
        "SELECT STAY_DATE, OCCUPANCY_PCT, REVPAR FROM MQT_DAILY_KPIS "
        "WHERE STAY_DATE BETWEEN CURRENT DATE - 30 DAYS AND CURRENT DATE - 1 DAY ORDER BY STAY_DATE"))
    if not past.empty:
        st.markdown("**Last 30 nights** · read from the materialized query table `MQT_DAILY_KPIS` "
                    "(precomputed by Db2, `REFRESH DEFERRED`)")
        hist = past.assign(Night=pd.to_datetime(past["STAY_DATE"]), Occupancy=past["OCCUPANCY_PCT"].astype(float),
                           RevPAR=past["REVPAR"].astype(float).round(0))
        st.altair_chart(alt.Chart(hist).mark_area(line={"color": "#0f62fe"}, color="#d0e2ff").encode(
            x=alt.X("Night:T", title=None, axis=alt.Axis(format="%d %b")),
            y=alt.Y("Occupancy:Q", title="Occupancy %", scale=alt.Scale(domain=[0, 100])),
            tooltip=[alt.Tooltip("Night:T", format="%a %d %b"), "Occupancy", "RevPAR"],
        ).properties(height=170), use_container_width=True)
    by_type = df(admin_db().query(
        "SELECT STAY_DATE, ROOM_TYPE_CODE, DECIMAL(100.0 * ROOMS_SOLD / NULLIF(ROOMS_IN_SERVICE,0), 5, 1) AS OCC "
        "FROM V_ROOM_TYPE_DAY WHERE STAY_DATE BETWEEN CURRENT DATE AND CURRENT DATE + 20 DAYS"))
    if not by_type.empty:
        st.markdown("**Occupancy by room type** · cells at 100% or more are sold out or oversold")
        cells = by_type.assign(Occ=by_type["OCC"].astype(float),
                               Date=pd.to_datetime(by_type["STAY_DATE"]))
        cells["Night"] = cells["Date"].dt.strftime("%d %b")
        night_order = cells.sort_values("Date")["Night"].unique().tolist()
        base = alt.Chart(cells).encode(
            x=alt.X("Night:N", sort=night_order, title=None, axis=alt.Axis(labelAngle=-45)),
            y=alt.Y("ROOM_TYPE_CODE:N", title=None, sort=["STD", "DLX", "PRM", "FAM", "JST", "STE"]))
        heat = base.mark_rect(cornerRadius=2).encode(
            color=alt.Color("Occ:Q", scale=alt.Scale(scheme="blues", domain=[0, 100]), legend=None),
            stroke=alt.condition("datum.Occ >= 100", alt.value("#da1e28"), alt.value(None)),
            strokeWidth=alt.condition("datum.Occ >= 100", alt.value(2), alt.value(0)),
            tooltip=[alt.Tooltip("ROOM_TYPE_CODE:N", title="Room type"), "Night", alt.Tooltip("Occ:Q", title="Occ %")])
        text = base.mark_text(fontSize=10).encode(
            text=alt.Text("Occ:Q", format=".0f"),
            color=alt.condition("datum.Occ > 60", alt.value("white"), alt.value("#161616")))
        st.altair_chart((heat + text).properties(height=230), use_container_width=True)
    st.subheader("Complaint radar (last 30 days)")
    st.caption("One Db2 query classifies every complaint sentence into themes by vector similarity "
               "(`VALUES` anchor vectors × `REVIEW_CHUNKS`, `VECTOR_DISTANCE`, `ROW_NUMBER() OVER`) and "
               "aggregates them by theme, floor and room with `GROUP BY GROUPING SETS`.")
    radar = radar_cached(30)
    if radar["themes"]:
        cells = pd.DataFrame([{"Theme": t["THEME"], "Floor": f"Floor {f['FLOOR_NO']}", "Reviews": f["REVIEWS"]}
                              for t in radar["themes"] for f in t["FLOORS"]])
        order = [t["THEME"] for t in radar["themes"]]
        base = alt.Chart(cells).encode(
            x=alt.X("Floor:N", title=None, axis=alt.Axis(labelAngle=0, orient="top")),
            y=alt.Y("Theme:N", sort=order, title=None, axis=alt.Axis(labelLimit=260, labelFontSize=12)))
        heat = base.mark_rect(cornerRadius=3).encode(
            color=alt.Color("Reviews:Q", scale=alt.Scale(scheme="oranges"), legend=None),
            tooltip=["Theme", "Floor", "Reviews"])
        top = int(cells["Reviews"].max())
        labels = base.mark_text(fontWeight="bold").encode(
            text="Reviews:Q",
            color=alt.condition(f"datum.Reviews > {top * 0.55}", alt.value("white"), alt.value("#161616")))
        st.altair_chart((heat + labels).properties(height=34 * len(order) + 30), use_container_width=True)
        st.dataframe(df([{"Theme": t["THEME"], "Reviews": t["REVIEWS"], "Avg rating": t["AVG_RATING"],
                          "Pattern": t["PATTERN"].capitalize(),
                          "What it means": t["HINT"]} for t in radar["themes"]]),
                     use_container_width=True, hide_index=True)
        if radar["no_complaints_about"]:
            st.caption("No complaints about: " + ", ".join(radar["no_complaints_about"]))
    st.subheader("Guest rating trend (weekly)")
    trend = df(admin_db().query(
        "SELECT WEEK, DECIMAL(AVG(RATING * 1.0), 3, 2) AS AVG_RATING, COUNT(*) AS REVIEWS FROM ("
        "  SELECT CREATED_AT - (DAYOFWEEK(CREATED_AT) - 1) DAYS AS WEEK, RATING FROM GUEST_REVIEWS "
        "  WHERE CREATED_AT >= CURRENT DATE - 120 DAYS) W GROUP BY WEEK ORDER BY WEEK"))
    if not trend.empty:
        weekly = trend.assign(Rating=trend["AVG_RATING"].astype(float), Week=pd.to_datetime(trend["WEEK"]))
        st.altair_chart(alt.Chart(weekly).mark_line(point=True, color="#0f62fe").encode(
            x=alt.X("Week:T", title=None, axis=alt.Axis(format="%d %b")),
            y=alt.Y("Rating:Q", title="Avg rating (1–5)", scale=alt.Scale(domain=[1, 5])),
            tooltip=[alt.Tooltip("Week:T", format="%d %b %Y"), "Rating", "REVIEWS"],
        ).properties(height=200), use_container_width=True)

# --------------------------------------------------------------------------- red team
with tab_red:
    st.subheader("Red-team scoreboard: what if the agent is fooled?")
    st.caption("Each attack is what a prompt-injected or malicious agent would try. Most bypass the app on purpose "
               "and use the agent's own Db2 credentials, so the defence has to come from Db2 itself. No LLM is used, "
               "and every attack runs in a transaction that is rolled back.")
    run_clicked = st.button("Run all attacks against the live Db2", icon=":material/play_arrow:", type="primary")
    siren, feed_box = st.empty(), st.empty()
    if run_clicked:
        st.session_state.red_feed = []

        def render_feed(done: bool = False, blocked: int = 0, total: int = 0) -> None:
            if done:
                ok = blocked == total
                siren.markdown(
                    f'<div class="siren {"done" if ok else ""}">{"DEFENDED" if ok else "BREACH"} · '
                    f'{blocked}/{total} attacks blocked · every attack rolled back</div>', unsafe_allow_html=True)
            else:
                siren.markdown(f'<div class="siren">UNDER ATTACK · attack #{len(st.session_state.red_feed)} '
                               'hitting the live Db2 with the agent\'s own credentials</div>',
                               unsafe_allow_html=True)
            feed_box.markdown('<div class="feed">' + "".join(reversed(st.session_state.red_feed)) + "</div>",
                              unsafe_allow_html=True)

        def on_attack(a) -> None:
            verdict = (f'<span class="ok">BLOCKED</span> <span class="by">by {html.escape(a.layer)}</span>'
                       if a.blocked else '<span class="no">NOT BLOCKED</span>')
            st.session_state.red_feed.append(
                f'<div class="row"><span class="atk">ATTACK #{a.id}</span>'
                f'<span class="what">{html.escape(a.attack)}</span>{verdict}</div>')
            render_feed()
            time.sleep(0.3)  # pace the feed so each attack is visible on screen

        st.session_state.redteam = run_redteam(progress=on_attack)
        r = st.session_state.redteam
        st.session_state.red_done = (r["blocked"], r["total"])
        render_feed(done=True, blocked=r["blocked"], total=r["total"])
    elif st.session_state.get("red_feed"):
        b, t = st.session_state.red_done
        siren.markdown(f'<div class="siren {"done" if b == t else ""}">{"DEFENDED" if b == t else "BREACH"} · '
                       f'{b}/{t} attacks blocked · every attack rolled back</div>', unsafe_allow_html=True)
        feed_box.markdown('<div class="feed">' + "".join(reversed(st.session_state.red_feed)) + "</div>",
                          unsafe_allow_html=True)
    res = st.session_state.get("redteam")
    if res is None and REDTEAM_FILE.exists():
        res = json.loads(REDTEAM_FILE.read_text(encoding="utf-8"))
        st.caption(f"Showing the saved run from {res['run_at']}. Press the button to run it live.")
    if res:
        m1, m2, m3 = st.columns(3)
        m1.metric("Attacks blocked", f"{res['blocked']}/{res['total']}")
        m2.metric("Defence layers involved", len(res["by_layer"]))
        m3.metric("Stopped by Db2 itself", sum(v for k, v in res["by_layer"].items() if k.startswith("Db2")))
        layers = pd.DataFrame([{"Layer": k, "Attacks stopped": v} for k, v in res["by_layer"].items()])
        st.altair_chart(alt.Chart(layers).mark_bar(cornerRadiusEnd=3).encode(
            x=alt.X("Attacks stopped:Q", title=None, axis=alt.Axis(tickMinStep=1)),
            y=alt.Y("Layer:N", sort="-x", title=None, axis=alt.Axis(labelLimit=320, labelFontSize=12)),
            color=alt.value("#0f62fe"), tooltip=["Layer", "Attacks stopped"]).properties(height=34 * len(layers) + 20),
            use_container_width=True)
        st.dataframe(df([{"#": a["id"], "Result": "Blocked" if a["blocked"] else "NOT BLOCKED",
                          "Attack": a["attack"], "Category": a["category"], "Stopped by": a["layer"],
                          "Evidence": a["evidence"]} for a in res["attacks"]]),
                     use_container_width=True, hide_index=True)

# --------------------------------------------------------------------------- audit
with tab_audit:
    st.subheader("Every agent run and tool call is persisted in Db2")
    chain = verify_audit_chain(admin_db())
    if chain["INTACT"]:
        st.success(f"Audit trail intact: {chain['STEPS']} steps, SHA-256 hash chain verified inside Db2 "
                   "(any edit or deletion of a past step would break it).", icon=":material/verified_user:")
    else:
        st.error(f"Audit trail TAMPERED: the hash chain breaks at step {chain['FIRST_BROKEN_STEP']} "
                 f"({chain['BROKEN']} step(s) affected).")
    t1, t2 = st.columns([3, 1])
    t1.caption("What if an insider with DBA rights quietly edits what an agent did? The button edits one past "
               "step's recorded output inside a Db2 transaction, re-verifies the chain, then rolls the edit back.")
    if t2.button("Simulate tampering", icon=":material/gpp_bad:", use_container_width=True) and chain["STEPS"]:
        st.session_state.tamper = simulate_tampering()
    tamper = st.session_state.get("tamper")
    if tamper:
        stp, bad = tamper["step"], tamper["tampered"]
        with st.container(border=True):
            st.markdown(f"**Edited step {stp['STEP_ID']}**: `{stp['AGENT']}` → **{stp['TOOL_NAME']}** "
                        f"(run `{str(stp['RUN_ID'])[:8]}`), output replaced with *\"quietly edited after the fact\"*")
            if not bad["INTACT"]:
                st.error(f"Db2 caught it: the hash chain breaks at step **{bad['FIRST_BROKEN_STEP']}**, exactly "
                         f"the edited step ({bad['BROKEN']} of {bad['STEPS']} steps fail verification). Hiding the "
                         "edit would mean re-hashing that step and every step after it, because each hash covers "
                         "the one before.", icon=":material/gpp_bad:")
            else:
                st.warning("The edit was not detected.", icon=":material/warning:")
            if tamper["restored"]["INTACT"]:
                st.success("Edit rolled back. The chain verifies again, and nothing was changed.",
                           icon=":material/undo:")
    anchor = check_anchor(admin_db())
    a1, a2 = st.columns([3, 1])
    if anchor["ok"] is None:
        a1.caption("External anchor: none written yet (one is written after every agent run).")
    else:
        a1.caption(f"**External anchor** (outside Db2): step {anchor['anchor']['step_id']} · "
                   f"`{anchor['anchor']['row_hash'][:16]}…` · {anchor['anchor']['anchored_at']} · "
                   + ("matches Db2" if anchor["ok"] else "**DOES NOT MATCH Db2**")
                   + ". But what if the insider also re-hashes every later step?")
    if a2.button("Simulate a rebuilt ledger", icon=":material/history_edu:", use_container_width=True) \
            and chain["STEPS"]:
        st.session_state.rebuild = simulate_rebuilt_ledger()
    rb = st.session_state.get("rebuild")
    if rb:
        with st.container(border=True):
            st.markdown(f"**Insider edit of step {rb['step_id']}, then {rb['rehashed']} later hashes recomputed** "
                        "inside a Db2 transaction.")
            if rb["chain_after_rebuild"]["INTACT"]:
                st.warning("The in-database hash chain now verifies as intact: a careful insider can rebuild it.",
                           icon=":material/warning:")
            if rb["anchor_after_rebuild"]["ok"] is False:
                st.error("Caught anyway: the chain head no longer matches the anchor copied outside Db2 "
                         "after the last run.", icon=":material/gpp_bad:")
            if rb["anchor_after_rollback"]["ok"]:
                st.success("Rolled back. Db2 matches the external anchor again.", icon=":material/undo:")
    runs = df(admin_db().query(
        "SELECT RUN_ID, STARTED_AT, ROUTE, STATUS, MODEL, SUBSTR(USER_QUESTION, 1, 120) AS QUESTION, LLM_CALLS, "
        "(SELECT COUNT(*) FROM AGENT_STEPS S WHERE S.RUN_ID = R.RUN_ID) AS TOOL_CALLS, "
        "TIMESTAMPDIFF(2, CHAR(FINISHED_AT - STARTED_AT)) AS SECONDS "
        "FROM AGENT_RUNS R ORDER BY STARTED_AT DESC FETCH FIRST 50 ROWS ONLY"))
    if runs.empty:
        st.write("No runs yet.")
    else:
        st.dataframe(runs, use_container_width=True, hide_index=True)
        run_id = st.selectbox("Inspect run", runs["RUN_ID"].tolist(),
                              format_func=lambda r: f"{r[:8]} — {runs.set_index('RUN_ID').loc[r, 'QUESTION']}")
        steps = df(admin_db().query(
            "SELECT STEP_ID, CREATED_AT, AGENT, TOOL_NAME, OK, LATENCY_MS, SUBSTR(TOOL_INPUT, 1, 1500) AS INPUT, "
            "SUBSTR(TOOL_OUTPUT, 1, 600) AS OUTPUT FROM AGENT_STEPS WHERE RUN_ID = ? ORDER BY STEP_ID", (run_id,)))
        st.dataframe(steps, use_container_width=True, hide_index=True)
        answer = admin_db().scalar("SELECT FINAL_ANSWER FROM AGENT_RUNS WHERE RUN_ID = ?", (run_id,))
        if st.button("Replay this run (no LLM calls)", icon=":material/replay:",
                     help="Re-plays the recorded trace from AGENT_STEPS"):
            replay = st.status(f"Replaying recorded run {run_id[:8]} from Db2…", expanded=True)
            for s in steps.to_dict("records"):
                time.sleep(min(0.8, max(0.15, (s["LATENCY_MS"] or 0) / 1000)))
                mark = ":green[:material/check_circle:]" if s["OK"] else ":orange[:material/warning:]"
                replay.write(f"{mark} `{s['AGENT']}` → **{s['TOOL_NAME']}** "
                             f"({s['LATENCY_MS']} ms) {str(s['INPUT'])[:220]}")
            replay.update(label=f"Replay of recorded run {run_id[:8]} · {len(steps)} tool calls · no LLM used",
                          state="complete")
        if answer:
            with st.expander("Final answer", expanded=True):
                st.markdown(answer)

# --------------------------------------------------------------------------- proofs
with tab_proof:
    st.subheader("Proofs: every claim, checked live against Db2")
    st.caption(f"The same {len(CHECKS)} checks as `python src/verify.py`. No LLM is used, and anything a check "
               "writes runs in a transaction that is rolled back, so the database is left exactly as it was.")
    go = st.button(f"Run all {len(CHECKS)} checks against the live Db2", icon=":material/play_arrow:",
                   type="primary")
    banner, box = st.empty(), st.empty()

    def proof_row(i, area, name, ok, detail, secs) -> str:
        pill = '<span class="pill ok">PASS</span>' if ok else '<span class="pill bad">FAIL</span>'
        return (f'<div class="proof"><span class="n">{i}</span>{pill}<div><span class="name">{html.escape(name)}'
                f'</span><span class="area">{html.escape(area)} · {secs:.1f}s</span>'
                f'<div class="d">{html.escape(str(detail))}</div></div></div>')

    if go:
        rows, passed, t0 = [], 0, time.time()
        for row in run_checks(own_admin=True):
            rows.append(proof_row(*row))
            passed += row[3]
            banner.markdown(f'<div class="siren done" style="animation:none;background:#0f62fe">CHECKING · '
                            f'{len(rows)} of {len(CHECKS)}</div>', unsafe_allow_html=True)
            box.markdown("".join(rows), unsafe_allow_html=True)
        st.session_state.proofs = (rows, passed, time.time() - t0)
    if st.session_state.get("proofs"):
        rows, passed, secs = st.session_state.proofs
        ok = passed == len(CHECKS)
        banner.markdown(f'<div class="siren {"done" if ok else ""}" style="animation:none">'
                        f'{passed}/{len(CHECKS)} CHECKS PASSED · {secs:.0f}s · nothing changed in the database</div>',
                        unsafe_allow_html=True)
        box.markdown("".join(rows), unsafe_allow_html=True)
