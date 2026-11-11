"""Streamlit dashboard: Overview, Live Lock Monitor, Relationships, Diagnostics, Incidents, Settings."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from ..config import Settings, load_env_file
from ..errors import ConfigError, Db2Error
from ..logging_setup import configure_logging
from ..models import Severity
from ..services.graph_layout import build_graph
from ..services.runtime import CycleResult, LockLensRuntime
from . import components as ui
from .graph_view import build_figure

PAGES = ["Overview", "Live Lock Monitor", "Blocking Relationships", "Diagnostics",
         "Incident History", "Settings"]
_SUBMISSION_DIR = Path(__file__).resolve().parents[3]

CONNECTION_HELP = {
    "invalid_credentials": "Check DB2_USER and DB2_PASSWORD in your .env file.",
    "database_not_found": "Check DB2_DATABASE. In Docker, wait until the container log shows "
                          "'Setup has completed'.",
    "unreachable": "Check DB2_HOST/DB2_PORT and that the Db2 container is running "
                   "(docker ps).",
    "timeout": "The server did not answer in time. Check the host, port and any firewall.",
    "driver_missing": "Install dependencies: pip install -r requirements.txt",
}


@st.cache_resource(show_spinner=False)
def _get_runtime(fingerprint: str, _settings: Settings) -> LockLensRuntime:
    """One runtime (one Db2 connection) shared across reruns. ``fingerprint`` has no secrets."""
    return LockLensRuntime(_settings)


def _load_settings() -> Settings | None:
    load_env_file(_SUBMISSION_DIR / ".env")
    load_env_file(".env")
    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        st.error("LockLens is not configured yet.")
        for p in exc.problems:
            st.markdown(f"- {p}")
        st.code("cp .env.example .env     # then edit DB2_PASSWORD and friends\n"
                "streamlit run src/app.py", language="bash")
        return None
    configure_logging(settings.log_level, [settings.db_password])
    return settings


def _connection_banner(result: CycleResult) -> None:
    if result.error:
        st.error(f"Cannot read from Db2: {result.error}")
        hint = CONNECTION_HELP.get(result.connection_kind)
        if hint:
            st.info(hint)


def _body(rt: LockLensRuntime, page: str, force: bool) -> None:
    s = rt.settings
    result = rt.refresh(min_age=0 if force else max(1.0, s.poll_seconds / 2))
    if result.error or result.snapshot is None or result.diagnosis is None:
        st.subheader(page)
        _connection_banner(result)
        if page == "Settings":
            _settings_page(rt)
        return
    snap, diag = result.snapshot, result.diagnosis
    st.caption(f"Live snapshot taken {snap.captured_at} UTC · pipeline: {diag.pipeline}")
    ui.render_notes(st, snap.notes + result.notes)
    {
        "Overview": lambda: _overview(rt, result),
        "Live Lock Monitor": lambda: _live(result),
        "Blocking Relationships": lambda: _relationships(result, s),
        "Diagnostics": lambda: _diagnostics(rt, result),
        "Incident History": lambda: _incidents(rt),
        "Settings": lambda: _settings_page(rt),
    }[page]()


# ---- pages ------------------------------------------------------------------------------
def _overview(rt: LockLensRuntime, result: CycleResult) -> None:
    snap, diag = result.snapshot, result.diagnosis
    a = diag.analysis
    st.subheader("Overview")
    st.markdown("**Current snapshot** (what Db2 reports right now)")
    c = st.columns(5)
    c[0].metric("Connection", "Connected")
    c[1].metric("Locks observed", a.total_locks if snap.locks_available else "n/a")
    c[2].metric("Waiting applications", len(a.waiters) if snap.waits_available else "n/a")
    c[3].metric("Blocking applications", len(a.blockers) if snap.waits_available else "n/a")
    longest = a.max_wait_seconds
    c[4].metric("Longest wait", f"{longest}s" if longest is not None else "n/a")
    attention = [f for f in diag.findings if f.severity >= Severity.WARNING]
    st.metric("Findings needing attention (current snapshot)", len(attention))

    st.markdown("**History** (incidents stored in Db2, not part of the snapshot)")
    open_count = rt.count_open_incidents()
    h = st.columns(2)
    h[0].metric("Open incidents", open_count if open_count is not None else "not initialised")
    if result.recorded:
        r = result.recorded
        h[1].metric("This refresh", f"+{r.created} new / {r.updated} updated / {r.resolved} resolved")
    st.markdown("**Summary**")
    st.write(diag.narrative)
    st.caption(f"Source: {diag.narrative_source}")


def _live(result: CycleResult) -> None:
    snap, diag = result.snapshot, result.diagnosis
    st.subheader("Live Lock Monitor")
    st.markdown("**Lock waits** (MON_GET_APPL_LOCKWAIT)")
    df = ui.waits_dataframe(diag.analysis, snap)
    if df.empty:
        st.success("No application is currently waiting for a lock.") if snap.waits_available \
            else st.warning("Lock-wait information is unavailable (see the notes above).")
    else:
        st.markdown(df.to_html(index=False, escape=True), unsafe_allow_html=True)
    st.markdown("**All locks** (MON_GET_LOCKS)")
    if not snap.locks_available:
        st.warning("Lock list is unavailable (see the notes above).")
        return
    locks = ui.locks_dataframe(snap)
    if locks.empty:
        st.info("MON_GET_LOCKS returned no locks.")
        return
    options = ["All"] + sorted({str(x) for x in locks.get("Status", pd.Series(dtype=str)).dropna()})
    chosen = st.selectbox("Filter by lock status", options)
    if chosen != "All":
        locks = locks[locks["Status"] == chosen]
    st.markdown(locks.to_html(index=False, escape=True), unsafe_allow_html=True)
    st.caption(f"{len(locks)} row(s) shown. Columns Db2 did not return are hidden.")


def _relationships(result: CycleResult, s: Settings) -> None:
    snap, diag = result.snapshot, result.diagnosis
    st.subheader("Blocking Relationships")
    model = build_graph(diag.analysis, snap, s.wait_warn_seconds)
    if not model.nodes:
        st.info("No blocking relationships in this snapshot.")
        return
    st.plotly_chart(build_figure(model), use_container_width=True)
    st.caption("Arrows read holder → locked resource → waiting application. Grey 'Holder unknown' "
               "nodes mean Db2 did not identify the holder; no relationship is guessed. "
               "Orange = wait beyond the warning threshold, red = part of a wait cycle.")
    a = diag.analysis
    if a.root_blockers:
        st.markdown("**Root blockers** (not themselves waiting): "
                    + ", ".join(f"`{h}`" for h in sorted(a.root_blockers)))
    for cyc in a.cycles:
        st.warning("Circular wait observed: " + " → ".join(map(str, cyc)) + f" → {cyc[0]}. "
                   "This is a snapshot observation, not a confirmed deadlock.")


def _diagnostics(rt: LockLensRuntime, result: CycleResult) -> None:
    diag = result.diagnosis
    st.subheader("Diagnostics")
    st.caption("Findings come from deterministic rules over Db2 monitoring data. The optional "
               "local-model summary below is clearly labelled and never replaces them.")
    for f in diag.findings:
        with st.expander(f"{ui.severity_text(f.severity)} · {f.title}",
                         expanded=f.severity >= Severity.WARNING):
            st.markdown(f"**Detected condition:** `{f.finding_type}`")
            st.markdown(f"**Explanation:** {f.explanation}")
            if f.affected_applications:
                st.markdown("**Affected applications:** " + ", ".join(map(str, f.affected_applications)))
            if f.evidence:
                st.markdown("**Evidence**")
                for e in f.evidence:
                    st.markdown(f"- {e}")
            if f.recommendations:
                st.markdown("**Recommended next steps** (advisory only; LockLens changes nothing)")
                for r in f.recommendations:
                    st.markdown(f"- {r}")
    st.divider()
    st.markdown("**Optional: plain-English summary from a local model (Ollama)**")
    if not rt.settings.llm_enabled:
        st.caption("Disabled. Set LOCKLENS_LLM_ENABLED=true and run an Ollama model to use it. "
                   "The rest of LockLens does not need it.")
        return
    if st.button("Generate summary with local model"):
        with st.spinner("Asking the local model…"):
            llm_result = rt.refresh(use_llm=True, record=False)
        if llm_result.diagnosis:
            st.session_state["llm_summary"] = (llm_result.diagnosis.narrative,
                                               llm_result.diagnosis.narrative_source)
    if "llm_summary" in st.session_state:
        text, source = st.session_state["llm_summary"]
        st.write(text)
        st.caption(f"Source: {source}")


def _incidents(rt: LockLensRuntime) -> None:
    st.subheader("Incident History")
    st.caption("Stored in Db2 (table LOCK_INCIDENTS). A refresh never duplicates an open incident.")
    if not rt.schema_ready():
        st.warning("The incident tables do not exist yet. Open Settings → Initialise incident tables.")
        return
    c = st.columns(4)
    severity = c[0].selectbox("Severity", ["Any", "CRITICAL", "WARNING", "INFO"])
    category = c[1].selectbox("Category", ["Any", "lock_contention", "possible_deadlock"])
    status = c[2].selectbox("Status", ["Any", "OPEN", "RESOLVED"])
    use_date = c[3].checkbox("Filter by date")
    since = None
    if use_date:
        since = st.date_input("Detected on or after", value=date.today()).isoformat()
    try:
        rows = rt.list_incidents(severity=None if severity == "Any" else severity,
                                 category=None if category == "Any" else category,
                                 status=None if status == "Any" else status, since=since)
    except (Db2Error, ValueError) as exc:
        st.error(f"Could not read incidents: {exc}")
        return
    if not rows:
        st.info("No incidents match these filters.")
        return
    df = pd.DataFrame(rows)
    show = ["INCIDENT_ID", "STATUS", "SEVERITY", "FINDING_TYPE", "TITLE", "DETECTED_AT",
            "LAST_SEEN_AT", "OBSERVATIONS", "BLOCKER_HANDLE", "WAITER_HANDLES", "MAX_WAIT_SECONDS"]
    st.markdown(df[[c for c in show if c in df.columns]].to_html(index=False, escape=True), unsafe_allow_html=True)
    chosen = st.selectbox("Inspect incident", [r["INCIDENT_ID"] for r in rows])
    row = next(r for r in rows if r["INCIDENT_ID"] == chosen)
    st.markdown(f"**{row['TITLE']}**")
    st.markdown(f"**Explanation:** {row.get('EXPLANATION') or 'n/a'}")
    st.markdown("**Recommended action:**\n\n" + (row.get("RECOMMENDATION") or "n/a"))
    try:
        for e in json.loads(row.get("EVIDENCE") or "[]"):
            st.markdown(f"- {e}")
    except (TypeError, ValueError):
        pass
    if row.get("RESOLVED_AT"):
        st.caption(f"Resolved {row['RESOLVED_AT']}: {row.get('RESOLUTION_NOTE') or ''}")


def _settings_page(rt: LockLensRuntime) -> None:
    s = rt.settings
    st.subheader("Settings")
    st.markdown("**Database connection** (read from environment / `.env`; secrets are never shown)")
    settings_df = pd.DataFrame([{"Setting": k, "Value": str(v)} for k, v in s.redacted().items()
                                if k.startswith("db_") or k == "schema"])
    st.markdown(settings_df.to_html(index=False, escape=True), unsafe_allow_html=True)
    st.caption("To change the connection or password, edit `.env` and restart the app.")
    c = st.columns(2)
    if c[0].button("Test connection"):
        status = rt.test_connection()
        (st.success if status.ok else st.error)(status.message + (f" Server: {status.server}" if status.server else ""))
        if not status.ok and CONNECTION_HELP.get(status.kind):
            st.info(CONNECTION_HELP[status.kind])
    if c[1].button("Initialise incident tables"):
        try:
            st.code("\n".join(rt.init_schema()))
            st.success("Incident tables are ready.")
        except Db2Error as exc:
            st.error(f"Initialisation failed: {exc}")
            st.caption("The user needs CREATETAB and IMPLICIT_SCHEMA (or DBADM). Alternatively run "
                       "scripts/init_db.sql as an administrator.")

    st.markdown("**Polling and thresholds** (apply until the app restarts)")
    with st.form("runtime_settings"):
        poll = st.number_input("Poll interval (seconds)", 2, 300, s.poll_seconds)
        warn = st.number_input("Wait warning threshold (seconds)", 1, 86400, s.wait_warn_seconds)
        crit = st.number_input("Wait critical threshold (seconds)", 2, 86400, s.wait_critical_seconds)
        rec = st.checkbox("Record incidents in Db2 automatically", value=s.auto_record)
        minimum = st.selectbox("Minimum severity to record", ["INFO", "WARNING", "CRITICAL"],
                               index=int(s.record_min_severity) - 1)
        if st.form_submit_button("Apply"):
            try:
                rt.settings = s.with_runtime_overrides(
                    poll_seconds=int(poll), wait_warn_seconds=int(warn), wait_critical_seconds=int(crit),
                    auto_record=rec, record_min_severity=Severity.parse(minimum))
                st.success("Applied.")
            except ConfigError as exc:
                st.error("; ".join(exc.problems))

    st.markdown("**Optional local model (Ollama)**")
    st.write(f"Enabled: `{s.llm_enabled}` · URL: `{s.ollama_url}` · model: `{s.ollama_model}`")
    st.caption("Set via LOCKLENS_LLM_* in `.env`. LockLens works fully without it.")
    with st.expander("Required Db2 privileges"):
        st.markdown(
            "- `EXECUTE` on `MON_GET_LOCKS`, `MON_GET_APPL_LOCKWAIT`, `MON_GET_CONNECTION` and "
            "`MON_FORMAT_LOCK_NAME`, or an authority such as DBADM / SQLADM / DATAACCESS / SYSMON.\n"
            "- To store incidents: `CREATETAB` and `IMPLICIT_SCHEMA` (or run `scripts/init_db.sql` "
            "as an administrator), then `INSERT/UPDATE/SELECT` on `LOCKLENS.LOCK_INCIDENTS`.\n"
            "- Missing privileges are reported on the dashboard; nothing is fabricated.")


# ---- entry ------------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="Db2 LockLens", page_icon="🔎", layout="wide")
    st.title("Db2 LockLens")
    st.caption("Explainable lock and blocking investigator for IBM Db2 · advisory only: "
               "LockLens never terminates sessions or changes the database.")
    settings = _load_settings()
    if settings is None:
        return
    rt = _get_runtime(settings.fingerprint(), settings)

    with st.sidebar:
        page = st.radio("Section", PAGES, label_visibility="collapsed")
        auto = st.toggle("Auto-refresh", value=rt.settings.auto_refresh,
                         help="Re-reads Db2 every poll interval using the same connection.")
        st.caption(f"Poll interval: {rt.settings.poll_seconds}s (change in Settings)")
        force = st.button("Refresh now")
        st.caption(f"Target: {settings.fingerprint()}")

    if auto and hasattr(st, "fragment"):
        @st.fragment(run_every=rt.settings.poll_seconds)
        def live_view() -> None:
            _body(rt, page, False)

        live_view()
    else:
        if auto:
            st.sidebar.warning("Auto-refresh needs Streamlit 1.37+; use Refresh now.")
        _body(rt, page, force)
