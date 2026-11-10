"""NEEDLE Streamlit UI (owner: app agent).

Run from the needle/ folder:
    .venv\\Scripts\\streamlit run src/needle/app.py

Every Db2 statement runs on a connection opened with the SELECTED user's credentials (needle/.env
<AUTHID>_PASSWORD), so RCAC decides what this page can show. Results are tied to the user who ran them:
switching the user hides them until the next run.
"""
from __future__ import annotations

import sys
from pathlib import Path

# `streamlit run src/needle/app.py` puts src/needle on sys.path, where needle/tokenize.py would shadow the
# stdlib tokenize module. Remove that entry and import the package from src/ instead.
_HERE = Path(__file__).resolve().parent
sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != _HERE]
SRC = _HERE.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import html  # noqa: E402
import os  # noqa: E402

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from needle import sbom  # noqa: E402
from needle.retriever import MODES, TriageRun  # noqa: E402
from needle.service import _short_error, depth_line, do_run, osv_link, title_of  # noqa: E402,F401

ROOT = SRC.parent
load_dotenv(ROOT / ".env")

# Default: the visitor signs in with their own Db2 user ID + password and RCAC binds to that identity.
# NEEDLE_DEMO_SWITCHER=1 (recorded demo only) shows a one-click switch between two demo identities whose
# passwords the server reads from needle/.env. That switch is NOT authentication; the page says so.
DEMO_USERS = ["NDL_SENIOR", "NDL_JUNIOR", "NDL_P10"]
DEMO_LABELS = {"NDL_P10": "NDL_P10 - Analyst with 10% visibility (sweep identity)"}


def demo_switcher_enabled() -> bool:
    return os.environ.get("NEEDLE_DEMO_SWITCHER") == "1"

SAMPLE = ("heads up from #platform-sec: someone says the yaml loader we use in a few python services can run "
          "arbitrary code when it parses an untrusted config file. no CVE number in the thread. are we exposed?")

# Carbon (Gray 10 / White) tokens: Plex Sans 14/20 body, 12/16 labels, 0 radius except pill tags, 8px grid.
CSS = """
<style>
:root { --ink:#161616; --ink-2:#525252; --ink-3:#6f6f6f; --line:#e0e0e0; --layer:#f4f4f4; --blue:#0f62fe;
        --red:#da1e28; --yellow:#f1c21b; }
code, pre, .mono { font-family: 'IBM Plex Mono', ui-monospace, Consolas, monospace !important; }
header[data-testid="stHeader"] { background: transparent; height: 0; }
.block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1480px; }
.ndl-eyebrow { font-size: 12px; line-height: 16px; letter-spacing: .32px; color: var(--ink-3); margin: 0 0 4px 0; }
.ndl-title { font-size: 28px; line-height: 36px; font-weight: 400; color: var(--ink); margin: 0; }
.ndl-sub { color: var(--ink-2); font-size: 14px; line-height: 20px; margin: 4px 0 16px 0; max-width: 900px; }
.ndl-brand { font-size: 16px; font-weight: 600; letter-spacing: .5px; margin: 0; }
.ndl-brand-sub { font-size: 12px; line-height: 16px; color: var(--ink-2); margin: 2px 0 16px 0; }
.ndl-section { font-size: 14px; line-height: 20px; font-weight: 600; color: var(--ink);
  border-bottom: 1px solid var(--line); padding-bottom: 8px; margin: 32px 0 12px 0; }
.ndl-section span { font-weight: 400; color: var(--ink-3); }
.ndl-chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 16px 0; }
.ndl-chip { font-size: 12px; line-height: 16px; background: #e0e0e0; color: var(--ink); padding: 4px 10px;
  border-radius: 24px; white-space: nowrap; font-variant-numeric: tabular-nums; }
.ndl-chip b { font-weight: 600; }
.ndl-chip.blue { background: #d0e2ff; color: #0043ce; }
.ndl-chip.red { background: #ffd7d9; color: #a2191f; }
.ndl-chip.amber { background: #fcf4d6; color: #8e6a00; white-space: normal; display: inline-block; max-width: 100%;
  border-radius: 8px; }
.ndl-verdict { border-left: 3px solid var(--ink-3); background: var(--layer); padding: 12px 16px; margin: 0 0 8px 0;
  font-size: 14px; line-height: 20px; }
.ndl-verdict b { font-weight: 600; }
.ndl-verdict.red { border-left-color: var(--red); background: #fff1f1; }
.ndl-verdict .meta { color: var(--ink-2); font-size: 12px; line-height: 16px; margin-top: 4px; }
.ndl-col-head { font-size: 14px; font-weight: 600; padding: 8px 12px; border-top: 3px solid var(--line);
  background: var(--layer); margin-bottom: 4px; }
.ndl-col-head span { display: block; font-size: 12px; font-weight: 400; color: var(--ink-2); }
.ndl-col-head.active { border-top-color: var(--blue); }
.ndl-note { font-size: 12px; line-height: 16px; color: var(--ink-2); margin: 4px 0 8px 0; }
.ndl-kpi { border-left: 3px solid var(--line); padding: 4px 12px; margin-bottom: 12px; }
.ndl-kpi .v { font-size: 28px; line-height: 36px; font-weight: 400; font-variant-numeric: tabular-nums; }
.ndl-kpi .l { font-size: 12px; line-height: 16px; color: var(--ink-2); }
.ndl-kpi.red { border-left-color: var(--red); } .ndl-kpi.amber { border-left-color: var(--yellow); }
.ndl-kpi.gray { border-left-color: #a8a8a8; }
</style>
"""


# ------------------------------------------------------------------------------------------------
# Data access: needle.service.do_run (shared with the FastAPI front end) opens and closes its own
# connection as the selected user.
# ------------------------------------------------------------------------------------------------

# ------------------------------------------------------------------------------------------------
# Rendering helpers
# ------------------------------------------------------------------------------------------------

def chips(items: list[tuple[str, str, str]]) -> None:
    body = "".join(f'<span class="ndl-chip {cls}">{html.escape(label)} <b>{html.escape(str(val))}</b></span>'
                   for label, val, cls in items)
    st.markdown(f'<div class="ndl-chips">{body}</div>', unsafe_allow_html=True)


def section(title: str, sub: str = "") -> None:
    extra = f' <span>&nbsp;·&nbsp; {html.escape(sub)}</span>' if sub else ""
    st.markdown(f'<div class="ndl-section">{html.escape(title)}{extra}</div>', unsafe_allow_html=True)


def kpi(col, value, label: str, cls: str = "") -> None:
    v = f"{value:,}" if isinstance(value, int) else str(value)
    col.markdown(f'<div class="ndl-kpi {cls}"><div class="v">{html.escape(v)}</div>'
                 f'<div class="l">{html.escape(label)}</div></div>', unsafe_allow_html=True)


def exposure_frame(res: dict, mode_ids: list[str]) -> pd.DataFrame:
    rows = [r for r in res.get("exposure", []) if r["ADV_ID"] in set(mode_ids)]
    return pd.DataFrame(rows, columns=list(sbom.EXPOSURE_COLUMNS))


def verdict(df: pd.DataFrame, n_adv: int, mode: str) -> None:
    """One-line answer, derived only from the SQL exposure rows."""
    aff = df[df.STATUS == "AFFECTED"]
    nc = df[df.STATUS == "NOT_CONFIRMED"].SERVICE.nunique()
    prev = df[df.STATUS == "PREVIOUSLY_AFFECTED"].SERVICE.nunique()
    uc = df[df.STATUS == "UNKNOWN_COVERAGE"].SERVICE.nunique()
    if len(aff):
        g = aff.groupby(["SERVICE", "PACKAGE", "VERSION_NOW"], as_index=False).agg(
            since=("EXPOSED_SINCE", "min"), days=("DAYS_EXPOSED", "max"), advs=("ADV_ID", "nunique"))
        parts = [f"<b>{html.escape(r.SERVICE)}</b> ({html.escape(r.PACKAGE)} {html.escape(str(r.VERSION_NOW))}, "
                 f"since {r.since}, {int(r.days):,} days, {r.advs} advisories)" for r in g.itertuples()]
        head = f"<b>{aff.SERVICE.nunique()} service{'s' if aff.SERVICE.nunique() != 1 else ''} affected now:</b> "
        cls = "red"
    else:
        parts, head, cls = [], "<b>No exact package + version match</b> for the ranked advisories. ", ""
    meta = (f"{nc} service{'s' if nc != 1 else ''} NOT_CONFIRMED (never 'safe') &nbsp;·&nbsp; {uc} UNKNOWN_COVERAGE "
            f"(ranges only, not checked) &nbsp;·&nbsp; {prev} previously "
            f"affected &nbsp;·&nbsp; top {n_adv} {mode} advisories &nbsp;·&nbsp; synthetic fleet")
    st.markdown(f'<div class="ndl-verdict {cls}">{head}{"; ".join(parts)}<div class="meta">{meta}</div></div>',
                unsafe_allow_html=True)


def rank_table(run: TriageRun, mode: str) -> pd.DataFrame:
    """Each leg shows its own order plus where the same advisory lands in the other leg."""
    rows = []
    for i, c in enumerate(run.ranked(mode), 1):
        d = run.docs.get(c["ADV_ID"], {})
        row = {"#": i, "Advisory": osv_link(c["ADV_ID"]), "Package": (d.get("PACKAGES_LIST") or [""])[0]}
        if mode == "keyword":
            row["Vec rank"] = c.get("VEC_RANK")
        elif mode == "vector":
            row["Cos dist"] = None if c.get("VEC_DIST") is None else float(c["VEC_DIST"])
            row["KW rank"] = c.get("KW_RANK")
        else:
            row["KW rank"] = c.get("KW_RANK")
            row["Vec rank"] = c.get("VEC_RANK")
        rows.append(row)
    df = pd.DataFrame(rows)
    for col in ("KW rank", "Vec rank"):
        if col in df:  # text, so a missing leg shows blank (Streamlit renders a null int as "None")
            df[col] = df[col].map(lambda v: "" if v is None or pd.isna(v) else str(int(v)))
    return df.set_index("#") if len(df) else df


def tint_fleet_rows(df: pd.DataFrame, fleet_pkgs: set[str]):
    """Carbon blue-10 rows: the advisory lists a package that the (synthetic) fleet deploys."""
    return df.style.format(na_rep="", precision=3).apply(
        lambda r: ["background-color: #edf5ff" if r["Package"] in fleet_pkgs else "" for _ in r], axis=1)


def detail_table(run: TriageRun, mode: str) -> pd.DataFrame:
    rows = []
    for i, c in enumerate(run.ranked(mode), 1):
        d = run.docs.get(c["ADV_ID"], {})
        rows.append({"#": i, "Advisory": osv_link(c["ADV_ID"]), "Summary": title_of(d, 160),
                     "Packages": ", ".join(d.get("PACKAGES_LIST", [])[:4]),
                     "Aliases": ", ".join(d.get("ALIASES", [])[:3]),
                     "Keyword rank": c.get("KW_RANK"), "Vector rank": c.get("VEC_RANK"),
                     "RRF": float(c["RRF"]) if c.get("RRF") is not None else None,
                     "Published": str(d.get("PUBLISHED") or "")[:10]})
    return pd.DataFrame(rows)


LINK = st.column_config.LinkColumn("Advisory", display_text=r"https://osv\.dev/vulnerability/(.*)", width="medium")


def render_exposure(res: dict, mode_ids: list[str]) -> None:
    section("Affected services", "SBOM_COMPONENT FOR BUSINESS_TIME AS OF CURRENT DATE + deploy history")
    chips([("Fleet", "SYNTHETIC: fictional services, real PyPI versions", "amber"),
           ("AFFECTED", "exact package + version in NEEDLE.ADV_AFFECTED", "blue")])
    if res.get("exposure_error"):
        if "SQL0551N" in res["exposure_error"]:  # e.g. the sweep identities: no SELECT on ADV_AFFECTED / SBOM
            st.info(f"Exposure not granted to this identity ({res['user']}): it may rank advisories but has no "
                    "SELECT on the affected-version or SBOM tables. The ranking above still comes from Db2 under RCAC.")
        else:
            st.warning(f"Exposure query failed: {res['exposure_error']}")
        return
    df = exposure_frame(res, mode_ids)
    aff = df[df.STATUS == "AFFECTED"]
    nc = df[df.STATUS == "NOT_CONFIRMED"]
    prev = df[df.STATUS == "PREVIOUSLY_AFFECTED"]
    uc = df[df.STATUS == "UNKNOWN_COVERAGE"]
    c1, c2, c3, c4, c5 = st.columns(5)
    kpi(c1, aff.SERVICE.nunique(), "services affected now", "red")
    kpi(c2, int(aff.DAYS_EXPOSED.max()) if len(aff) else "-", "longest exposure (days)", "red")
    kpi(c3, nc.SERVICE.nunique(), "not confirmed", "amber")
    kpi(c4, uc.SERVICE.nunique(), "unknown coverage", "amber")
    kpi(c5, prev.SERVICE.nunique(), "previously affected", "gray")

    def view(d: pd.DataFrame, cols: list[str]) -> None:
        d = d.copy()
        d["Advisory"] = d.ADV_ID.map(osv_link)
        d["Fleet"] = d.SYNTHETIC.map(lambda x: "synthetic" if x == 1 else "real")
        st.dataframe(d[cols], hide_index=True, width="stretch",
                     column_config={"Advisory": LINK, "SERVICE": "Service", "OWNER_TEAM": "Team",
                                    "PACKAGE": "Package", "VERSION_NOW": "Version now",
                                    "EXPOSED_SINCE": st.column_config.DateColumn("Exposed since"),
                                    "EXPOSED_UNTIL": st.column_config.DateColumn("Fixed on"),
                                    "DAYS_EXPOSED": st.column_config.NumberColumn("Days exposed", format="localized"),
                                    "VERSIONS": "Listed versions in window", "STATUS": "Status"})

    t1, t2, t4, t3 = st.tabs([f"AFFECTED ({len(aff)})", f"NOT_CONFIRMED ({len(nc)})",
                              f"UNKNOWN_COVERAGE ({len(uc)})", f"PREVIOUSLY_AFFECTED ({len(prev)})"])
    with t4:
        st.markdown('<div class="ndl-note">The advisory names a package that the service deploys, but OSV gives '
                    'only version ranges for it (no enumerated versions in NEEDLE.ADV_AFFECTED): '
                    f'{html.escape(sbom.STATUS_HELP["UNKNOWN_COVERAGE"])}.</div>', unsafe_allow_html=True)
        if len(uc):
            view(uc, ["SERVICE", "OWNER_TEAM", "PACKAGE", "VERSION_NOW", "Advisory", "Fleet"])
    with t1:
        if len(aff):
            view(aff.sort_values("DAYS_EXPOSED", ascending=False),
                 ["SERVICE", "OWNER_TEAM", "PACKAGE", "VERSION_NOW", "Advisory", "EXPOSED_SINCE", "DAYS_EXPOSED",
                  "VERSIONS", "Fleet"])
        else:
            st.markdown('<div class="ndl-note">No exact package+version match for the ranked advisories. '
                        'That is not a clean bill of health: see NOT_CONFIRMED.</div>', unsafe_allow_html=True)
    with t2:
        st.markdown('<div class="ndl-note">The service deploys the package, but the deployed version is not '
                    'listed by the advisory. The advisory may use ranges, or the data may be incomplete. '
                    'NOT_CONFIRMED is never "safe".</div>', unsafe_allow_html=True)
        if len(nc):
            view(nc, ["SERVICE", "OWNER_TEAM", "PACKAGE", "VERSION_NOW", "Advisory", "Fleet"])
    with t3:
        if len(prev):
            view(prev.sort_values("EXPOSED_SINCE"),
                 ["SERVICE", "OWNER_TEAM", "PACKAGE", "Advisory", "EXPOSED_SINCE", "EXPOSED_UNTIL", "DAYS_EXPOSED",
                  "VERSIONS", "Fleet"])


def render_memo(res: dict, run: TriageRun, mode: str) -> None:
    section("Triage memo", "local qwen3:14b via LangChain; every sentence checked against the SQL results")
    memo_key = (res["user"], res["ts"], mode)
    go = st.button("Generate memo (Ollama, local)", key="memo_btn")
    if go:
        from needle.llm_summary import MAX_ADVISORIES, generate_memo

        advs = [{"adv_id": c["ADV_ID"], "summary": run.docs[c["ADV_ID"]].get("SUMMARY"),
                 "details": run.docs[c["ADV_ID"]].get("DETAILS"),
                 "packages": run.docs[c["ADV_ID"]].get("PACKAGES_LIST", []),
                 "aliases": run.docs[c["ADV_ID"]].get("ALIASES", [])} for c in run.ranked(mode)][:MAX_ADVISORIES]
        ids = {a["adv_id"] for a in advs}
        rows = [r for r in res.get("exposure", []) if r["ADV_ID"] in ids]
        with st.spinner("qwen3:14b is writing the memo locally..."):
            try:
                st.session_state["memo"] = (memo_key, generate_memo(advs, rows), None)
            except Exception as e:
                st.session_state["memo"] = (memo_key, None, _short_error(e))
    memo = st.session_state.get("memo")
    if not memo or memo[0] != memo_key:
        st.markdown('<div class="ndl-note">The memo is optional. The ranking and exposure tables above come from '
                    'SQL only.</div>', unsafe_allow_html=True)
        return
    _, result, err = memo
    if err:
        st.error(f"Local LLM unavailable: {err}")
        return
    v = result.verified
    chips([("Model", result.model, ""), ("Time", f"{result.elapsed_s:.1f} s", ""),
           ("Kept sentences", v.kept, "blue"), ("Removed by verifier", v.removed_count,
                                                "red" if v.removed_count else "")])
    with st.container(border=True):
        st.markdown(v.text or "_The verifier removed every sentence._")
    with st.expander(f"Removed claims ({v.removed_count})", expanded=bool(v.removed_count)):
        if not v.removed:
            st.markdown('<div class="ndl-note">Nothing removed.</div>', unsafe_allow_html=True)
        for r in v.removed:
            st.markdown(f"- ~~{html.escape(r.text)}~~  \n  <span class='ndl-note'>{html.escape('; '.join(r.reasons))}"
                        f"</span>", unsafe_allow_html=True)
    with st.expander("Raw model output (unverified)"):
        st.code(result.raw or "", language="markdown")


# ------------------------------------------------------------------------------------------------
# Page
# ------------------------------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="NEEDLE · vulnerability triage", layout="wide", initial_sidebar_state="expanded")
    st.markdown(CSS, unsafe_allow_html=True)

    with st.sidebar:
        st.markdown('<div class="ndl-brand">NEEDLE</div><div class="ndl-brand-sub">Permission-aware hybrid retrieval '
                    'inside IBM Db2 12.1</div>', unsafe_allow_html=True)
        query = st.text_area("Advisory or chat message", value=SAMPLE, height=190)
        demo = demo_switcher_enabled()
        if demo:
            user = st.selectbox("Demo identity switcher (not authentication)", DEMO_USERS, index=0,
                                format_func=lambda u: DEMO_LABELS.get(u, u))
            password = None  # the server reads the demo identity's password from needle/.env
            st.markdown('<span class="ndl-chip amber"><b>Demo identity switcher - not authentication</b></span>',
                        unsafe_allow_html=True)
        else:
            user = st.text_input("Db2 user ID", value="", placeholder="e.g. NDL_JUNIOR").strip().upper()
            password = st.text_input("Db2 password", value="", type="password")
            st.markdown('<div class="ndl-note">Your own Db2 credentials. RCAC binds to this identity. The password '
                        'is sent only to Db2 and is kept only in this browser session.</div>', unsafe_allow_html=True)
        mode = st.radio("Ranking for exposure + memo", MODES, index=2, horizontal=True)
        with st.expander("Retrieval settings"):
            k = st.slider("Top k", 5, 20, 10)
            st.markdown('<div class="ndl-note">The search depth is chosen per user by the RCAC router.</div>',
                        unsafe_allow_html=True)
        run_clicked = st.button("Run triage", type="primary", width="stretch")
        st.markdown('<div class="ndl-note">Each run connects as this Db2 user. Changing the user hides the previous '
                    'results.</div>', unsafe_allow_html=True)

    st.markdown('<div class="ndl-eyebrow">NEEDLE &nbsp;/&nbsp; Vulnerability triage</div>'
                '<div class="ndl-title">Which services does this advisory hit?</div>'
                '<div class="ndl-sub">BM25 keyword rank and DiskANN vector rank, fused by reciprocal rank fusion in one '
                'Db2 statement under row and column access control, then joined to a temporal SBOM history.</div>',
                unsafe_allow_html=True)

    if run_clicked:
        if not query.strip():
            st.warning("Paste an advisory or a chat message first.")
        elif not demo and (not user or not password):
            st.warning("Enter your Db2 user ID and password first.")
        else:
            with st.spinner(f"Running NEEDLE.TRIAGE as {user}..."):
                st.session_state["res"] = do_run(user, query.strip(), int(k), None, password=password)
            st.session_state.pop("memo", None)

    res = st.session_state.get("res")
    if not res:
        st.info("Paste a vague advisory or a chat message, sign in with a Db2 user and press **Run triage**.")
        return
    if res["user"] != user:
        st.info(f"The results on file were produced as {res['user']}. They are hidden for "
                f"{user or 'another user'}. Press **Run triage** to run as this user.")
        return
    if res.get("fatal"):
        kind, msg = res["fatal"]
        title = {"db": "Db2 unavailable", "sql": "Db2 query failed", "login": "Sign-in failed",
                 "ollama": "Embedding service unavailable (Ollama)"}.get(kind, "Error")
        st.error(f"**{title}**  \n{msg}")
        st.markdown('<div class="ndl-note">Nothing is shown from cache. Check the port forward to the Codespace '
                    '(localhost:50000) or Ollama (localhost:11434) and run again.</div>', unsafe_allow_html=True)
        return

    run: TriageRun = res["run"]
    t = run.timings_ms
    vis = res.get("visible_docs")
    chips([("User", res["user"], "blue"), ("Readable advisories", f"{vis:,}" if vis is not None else "?", ""),
           ("Path", run.path, ""), ("Embed", f"{t.get('embed', 0):,.0f} ms", ""),
           ("Triage SQL", f"{t.get('triage_sql', 0):,.0f} ms", ""),
           ("Exposure SQL", f"{t.get('exposure_sql', 0):,.0f} ms", ""), ("Run at", res["ts"], "")])

    mode_ids = [c["ADV_ID"] for c in run.ranked(mode)]
    if not res.get("exposure_error"):
        verdict(exposure_frame(res, mode_ids), len(mode_ids), mode)

    section("Ranked advisories", "one candidate set from NEEDLE.TRIAGE, three orderings; the blue column feeds "
                                 "exposure and the memo")
    fleet_pkgs = {r["PACKAGE"] for r in res.get("exposure", [])}
    cols = st.columns(3, gap="small")
    sub = {"keyword": "BM25 in plain SQL over NEEDLE.POSTING", "vector": "DiskANN index, FETCH APPROX",
           "hybrid": "reciprocal rank fusion inside Db2"}
    for col, m in zip(cols, MODES):
        with col:
            st.markdown(f'<div class="ndl-col-head {"active" if m == mode else ""}">{m.capitalize()}'
                        f'<span>{sub[m]}</span></div>', unsafe_allow_html=True)
            df = rank_table(run, m)
            if df.empty:
                st.markdown('<div class="ndl-note">No candidates in this leg.</div>', unsafe_allow_html=True)
                continue
            st.dataframe(tint_fleet_rows(df, fleet_pkgs), hide_index=False, width="stretch",
                         column_config={"_index": st.column_config.NumberColumn("#", width=32),
                                        "Advisory": st.column_config.LinkColumn(
                                            "Advisory", display_text=r"https://osv\.dev/vulnerability/(.*)",
                                            width=150),
                                        "Package": st.column_config.TextColumn("Package", width=110),
                                        "Cos dist": st.column_config.NumberColumn("Cos dist", format="%.3f",
                                                                                  width=64),
                                        "KW rank": st.column_config.TextColumn("KW", width=44),
                                        "Vec rank": st.column_config.TextColumn("Vec", width=44)})
    st.markdown('<div class="ndl-note">Blue rows: the advisory lists a package that the synthetic fleet deploys. '
                'KW / Vec = the same advisory\'s rank in the other leg (blank = outside that leg\'s candidates).'
                '</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="ndl-note">{html.escape(depth_line(run))}</div>', unsafe_allow_html=True)

    with st.expander(f"Summaries of the {mode} top {len(mode_ids)}", expanded=False):
        st.dataframe(detail_table(run, mode), hide_index=True, width="stretch",
                     column_config={"Advisory": LINK, "RRF": st.column_config.NumberColumn("RRF", format="%.5f")})

    with st.expander("SQL: the one retrieval statement and the exposure join, with bound parameters"):
        st.markdown(f"**Retrieval** ({run.path})")
        st.code(run.call_text, language="sql")
        st.json(run.params_display, expanded=False)
        st.code(run.sql_text, language="sql")
        st.markdown("**Exposure** (parameter values = the advisory ids ranked above, as visible to this user)")
        ids = res.get("exposure_ids") or []
        st.code(sbom.exposure_sql(max(1, len(ids))), language="sql")
        st.json({"params": ids}, expanded=False)

    render_exposure(res, mode_ids)
    render_memo(res, run, mode)


if __name__ == "__main__":  # streamlit runs the script as __main__; tests import main() instead
    main()
