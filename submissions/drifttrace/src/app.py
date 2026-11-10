"""DriftTrace Streamlit UI. Run from the official repo root:
    streamlit run submissions/drifttrace/src/app.py
"""
from __future__ import annotations

import csv
import hashlib
import html
import re
import io
import json
import sys
import uuid
from datetime import datetime, time, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import streamlit as st

from config import get_settings
from db import Db2Error, connect, server_identity
from intake import EXAMPLES, PROVIDER, extract, manual_extraction, validate
from models import INSUFFICIENT_DATA, OUTSIDE_SCOPE, REVIEW_SCOPE, SUPPORTED_FUNCTION, NoticeExtraction, Scope
from trace import (FACTS_SQL, MAX_BOUND_MM, MAX_NOTICE_CHARS, MAX_RATIONALE_CHARS, SHIPMENTS_SQL, InputError,
                   StalePreviewError, db2_crosscheck, fetch_instruments, fmt_ts, list_cases, load_case, run_trace, save_case,
                   DISPOSITIONS, MAX_NOTE_CHARS, MAX_REVIEWER_CHARS, OPEN_CLASSES, record_review, review_status)

st.set_page_config(page_title="DriftTrace", page_icon="📏", layout="wide")
st.markdown(
    """<style>
    .dt-badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.8rem;font-weight:600}
    .dt-review{background:#fef3c7;color:#92400e;border:1px solid #f59e0b}
    .dt-outside{background:#f1f5f9;color:#334155;border:1px solid #94a3b8}
    .dt-missing{background:#fee2e2;color:#991b1b;border:1px solid #f87171}
    .dt-path{font-family:ui-monospace,monospace;font-size:0.9rem}
    </style>""",
    unsafe_allow_html=True,
)

BADGE = {REVIEW_SCOPE: ("dt-review", "NEEDS REVIEW"), OUTSIDE_SCOPE: ("dt-outside", "OUTSIDE THIS CASE"),
         INSUFFICIENT_DATA: ("dt-missing", "INSUFFICIENT DATA")}
ss = st.session_state
settings = get_settings()


def md(value) -> str:
    """Escape untrusted text (Db2 rows, user input, model output) before markdown rendering."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|<>~$])", r"\\\1", "" if value is None else str(value))


def h(value) -> str:
    """Escape untrusted text placed inside unsafe_allow_html markup."""
    return html.escape("" if value is None else str(value), quote=True)


def badge(cls: str) -> str:
    c, label = BADGE[cls]
    return f'<span class="dt-badge {c}">{label}</span>'


def invalidate(*_):
    for k in ("extraction", "validation", "scope", "intake_mode", "model_used"):
        ss.pop(k, None)


# ---------------- sidebar: real status ----------------
with st.sidebar:
    st.subheader("System status")
    try:
        ident = server_identity()
        st.success(f"Db2 connected: {ident['SERVER']} · {ident['DBMS_NAME']} {ident['DBMS_VER']}\n\nschema {ident['SCHEMA_NAME']} · app user {ident['DB_USER'].strip()} (least privilege) · verified by live query")
        db_ok = True
    except Db2Error as exc:
        st.error(f"Db2 not reachable: {exc}")
        db_ok = False
    if ss.get("model_verified"):
        st.success(f"AI model verified this session: {ss['model_verified']}")
    elif settings.google_api_key:
        st.info(f"AI key configured for {settings.ai_model}; not yet verified (runs on Extract).")
    else:
        st.warning("No AI key configured. Manual entry only.")
    st.caption("All operational data is synthetic. DriftTrace builds a review worklist; it does not decide defects, safety or release.")

st.title("DriftTrace")
st.markdown("**Trace a failed calibration to the work that needs review.**")
if not db_ok:
    st.stop()

with connect() as conn:
    instruments = {r["ID"]: r for r in fetch_instruments(conn)}
known_ids = sorted(instruments)

case_param = st.query_params.get("case")
tab_notice, tab_trace, tab_case = st.tabs(["1 · Notice", "2 · Trace", "3 · Saved case"])

# ================= 1. Notice =================
with tab_notice:
    left, right = st.columns([1, 1])
    with left:
        example = st.selectbox("Example notice", list(EXAMPLES), key="example", on_change=lambda: (ss.update(notice=EXAMPLES[ss.example]), invalidate()))
        if "notice" not in ss:
            ss.notice = EXAMPLES[example]
        st.text_area("Pasted calibration notice (untrusted text)", key="notice", height=170, on_change=invalidate, max_chars=MAX_NOTICE_CHARS)
        b1, b2 = st.columns(2)
        if b1.button("Extract with AI", type="primary", disabled=not settings.google_api_key):
            with st.spinner(f"Calling {settings.ai_model} via LangChain…"):
                try:
                    ex = extract(ss.notice, known_ids, settings.ai_model, settings.google_api_key)
                    ss.extraction, ss.intake_mode, ss.model_used = ex.model_dump(), "ai", settings.ai_model
                    ss.model_verified = settings.ai_model
                    ss.extracted_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                    ss.pop("scope", None)
                    ok = True
                except Exception as exc:  # keep text; offer manual entry; never fake success
                    ok = False
                    msg = str(exc).replace(settings.google_api_key, "***") if settings.google_api_key else str(exc)
                    st.error(f"AI extraction failed ({type(exc).__name__}: {msg[:160]}). Your text is kept. Use manual entry.")
            if ok:
                st.rerun()  # refresh sidebar so it reports the verified model
        if b2.button("Manual entry (no AI)"):
            ss.extraction, ss.intake_mode, ss.model_used = manual_extraction().model_dump(), "manual", None
            ss.pop("scope", None)

    with right:
        if "extraction" in ss:
            ex = NoticeExtraction.model_validate(ss.extraction)
            val = validate(ex, ss.notice, known_ids)
            ss.validation = val
            if ss.intake_mode == "ai":
                st.markdown(f"**Live AI extraction** · {md(ss.model_used)} · {md(ss.extracted_at)}")
            else:
                st.markdown("**Manual entry** — no AI result; all fields are entered by the manager.")
            rows = []
            for name in ("report_reference", "instrument_id", "function_code", "detected_at", "observed_error_magnitude_mm", "observed_direction"):
                quotes = [q for q in val.quotes if q.field == name]
                rows.append({
                    "Field": name,
                    "Extracted": "missing" if getattr(ex, name) in (None, "unknown") else str(getattr(ex, name)),
                    "Source quote": quotes[0].quote if quotes else "—",
                    "Quote check": ("verbatim in notice" if quotes[0].exact else "NOT FOUND in notice") if quotes else "no quote",
                })
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            if ex.scope_limitations:
                st.markdown("**Scope limitations stated:** " + "; ".join(ex.scope_limitations))
            for m in val.blocking:
                st.error("Blocks tracing until confirmed: " + m)
            for m in val.review:
                st.warning("Requires review: " + m)

    if "extraction" in ss:
        val = ss.validation
        st.divider()
        st.subheader("Confirm investigation scope")
        c1, c2, c3 = st.columns([1, 1, 1.3])
        with c1:
            default_idx = known_ids.index(val.resolved_instrument) if val.resolved_instrument in known_ids else None
            inst = st.selectbox("Instrument (exact Db2 ID)", known_ids, index=default_idx, placeholder="Select — not resolved from notice")
            st.selectbox("Measurement function", [SUPPORTED_FUNCTION], help="Only external_diameter in mm is supported.")
        with c2:
            rec = instruments.get(inst) if inst else None
            if rec:
                st.markdown("**Db2 verification record** (retrieved, not generated)")
                st.markdown(f"`DT_INSTRUMENTS` · **{md(rec['ID'])}** — {md(rec['NAME'])}  \n"
                            f"Last acceptable verification: **{fmt_ts(rec['LAST_VERIFIED_AT'])}**  \n"
                            f"Reference: **{md(rec['VERIFICATION_REF'] or 'missing')}**")
            start_default = rec["LAST_VERIFIED_AT"] if rec and rec["LAST_VERIFIED_AT"] else None
            end_default = val.detected_at
        with c3:
            sd = st.date_input("Review start (UTC)", value=start_default.date() if start_default else None, key=f"sd_{inst}")
            stt = st.time_input("Start time (UTC)", value=start_default.time() if start_default else time(0, 0), key=f"st_{inst}")
            ed = st.date_input("Review end / detection (UTC)", value=end_default.date() if end_default else None, key="ed")
            ett = st.time_input("End time (UTC)", value=end_default.time() if end_default else time(23, 59), key="et")
        default_rat = (
            f"From last documented acceptable verification {rec['VERIFICATION_REF']} ({fmt_ts(start_default)}) through detection "
            f"of the failed check ({fmt_ts(end_default)}). Drift onset is not established, so the window is not shortened."
            if rec and start_default and end_default else ""
        )
        rationale = st.text_area("Window rationale (required)", value=default_rat, key=f"rat_{inst}_{bool(end_default)}", max_chars=MAX_RATIONALE_CHARS)
        ack_block = True
        if val.blocking or val.review or ss.intake_mode == "manual":
            ack_block = st.checkbox("I reviewed the flagged items above and confirm the instrument, window and scope myself "
                                    "(DriftTrace does not apply stated limitations automatically).")
        if st.button("Confirm scope", type="primary"):
            if not (inst and sd and ed and rationale.strip() and ack_block):
                st.error("Instrument, start, end, rationale and acknowledgement of flagged items are required.")
            else:
                start, end = datetime.combine(sd, stt), datetime.combine(ed, ett)
                if end < start:
                    st.error("Review end must be on or after review start.")
                else:
                    ss.scope = Scope(inst, SUPPORTED_FUNCTION, start, end)
                    ss.rationale = rationale.strip()
                    st.success("Scope confirmed. Open step 2 · Trace.")
        if "scope" in ss:
            s = ss.scope
            st.info(f"Confirmed: {s.instrument_id} · {s.function_code} · {fmt_ts(s.review_start)} → {fmt_ts(s.review_end)} (inclusive)")

# ================= 2. Trace =================
with tab_trace:
    if "scope" not in ss:
        st.info("Confirm the investigation scope in step 1 first.")
    else:
        s: Scope = ss.scope
        bc1, bc2 = st.columns([1, 2])
        with bc1:
            use_bound = st.checkbox("Apply an illustrative error bound", value=False)
            bound_val = st.number_input("Hypothetical symmetric bound ± (mm)", min_value=0.0, max_value=float(MAX_BOUND_MM), value=0.040, step=0.005, format="%.3f", disabled=not use_bound)
        with bc2:
            st.markdown("**Illustrative sensitivity analysis; historical error not established.**")
            st.caption("The 0.04 mm as-found observation does not establish the historical error. The bound only ranks which "
                       "recorded ACCEPTED decisions could cross a limit under that assumption. It never removes records from review.")
        try:
            bound = Decimal(f"{bound_val:.3f}") if use_bound else None
        except InvalidOperation:
            bound = None
        with connect() as conn:
            findings, totals, fp = run_trace(conn, s, bound)
            cc = db2_crosscheck(conn, totals)

        draft_key = hashlib.sha256(json.dumps([ss.notice, ss.get("extraction"), s.instrument_id, str(s.review_start), str(s.review_end),
                                               ss.get("rationale"), str(bound)], default=str).encode()).hexdigest()
        tokens = ss.setdefault("draft_tokens", {})
        sub_id = tokens.setdefault(draft_key, str(uuid.uuid4()))

        m = st.columns(6)
        m[0].metric("Lots needing review", len(totals.review_lots))
        m[1].metric("Linked shipments", len(totals.review_shipments))
        m[2].metric("Shipped units in review", totals.review_shipped_units)
        m[3].metric("Unshipped units in review", totals.review_unshipped_units)
        m[4].metric("Insufficient-data lots", len(totals.insufficient_lots))
        m[5].metric("Insufficient-data shipped units", totals.insufficient_shipped_units)
        if cc["matches"]:
            st.success(f"Db2 cross-check: view DT_LOT_EXPOSURE_V independently aggregates {cc['lots']} lots, {cc['shipments']} shipments, "
                       f"{cc['shipped']} shipped / {cc['unshipped']} unshipped units, matching the lineage totals.")
        else:
            st.error(f"Db2 cross-check MISMATCH: {cc}. Saving is blocked.")
        with st.expander("Db2 queries behind this trace (parameterized, read-only)"):
            st.code(FACTS_SQL.strip(), language="sql")
            st.code(SHIPMENTS_SQL.strip(), language="sql")
            st.code("SELECT COUNT(*), SUM(SHIPPED_QUANTITY), ... FROM DT_LOT_EXPOSURE_V WHERE LOT_ID IN (?, ?, ?)", language="sql")
            st.caption(f"Bound parameters: instrument_id={s.instrument_id!r}, function_code={s.function_code!r}. "
                       "The AI model never writes SQL. Saved cases, findings and audit events are append-only (Db2 triggers).")
        st.caption("Counts cover recorded Db2 data only. Units are review candidates, not confirmed defective units; "
                   "one inspection record per lot does not establish measurement of every unit.")

        def path(fd):
            ships = ", ".join(f"{x.shipment_id} ({x.shipped_quantity} → {x.customer_name})" for x in fd.shipments) or "no shipment"
            return f"{fd.fact.instrument_id} → {fd.fact.inspection_id} → {fd.fact.lot_id} → {ships}"

        def table(cls):
            rows = []
            for fd in findings:
                if fd.classification != cls:
                    continue
                f = fd.fact
                rows.append({
                    "Lineage": path(fd),
                    "Measured (UTC)": fmt_ts(f.measured_at),
                    "Value mm": str(f.recorded_value) if f.recorded_value is not None else "missing",
                    "Limits mm": f"{f.lower_limit}–{f.upper_limit}",
                    "Original": f.original_decision,
                    **({"Under ± bound": (fd.hypothetical or "").replace("_", " ").lower() or "—",
                        "Interval": f"{fd.hypothetical_interval[0]}–{fd.hypothetical_interval[1]}" if fd.hypothetical_interval else "—"}
                       if cls == REVIEW_SCOPE else {}),
                    "Reason": fd.reason,
                })
            return pd.DataFrame(rows)

        st.markdown(f"#### {badge(REVIEW_SCOPE)} Instrument → Inspection → Lot → Shipment", unsafe_allow_html=True)
        st.dataframe(table(REVIEW_SCOPE), hide_index=True, width="stretch")
        st.markdown(f"#### {badge(INSUFFICIENT_DATA)} Potentially relevant, missing evidence", unsafe_allow_html=True)
        st.dataframe(table(INSUFFICIENT_DATA), hide_index=True, width="stretch")
        with st.expander("Comparison: records outside this case (not a safety verdict)", expanded=True):
            st.dataframe(table(OUTSIDE_SCOPE), hide_index=True, width="stretch")

        st.markdown("#### Record detail")
        pick = st.selectbox("Inspect record", [fd.fact.inspection_id for fd in findings])
        fd = next(x for x in findings if x.fact.inspection_id == pick)
        st.markdown(f"{badge(fd.classification)} &nbsp; <span class='dt-path'>{h(path(fd))}</span>", unsafe_allow_html=True)
        st.markdown(f"**Reason:** {md(fd.reason)}")
        st.json({"inspection": {k: str(v) if v is not None else None for k, v in fd.fact.__dict__.items()},
                 "shipments": [x.__dict__ | {"shipped_at": str(x.shipped_at)} for x in fd.shipments],
                 "hypothetical": fd.hypothetical}, expanded=False)

        st.divider()
        st.subheader("Save investigation case")
        confirm = st.checkbox("I confirm the scope" + (" and accept the illustrative bound" if bound is not None else "") +
                              ". This case is a review worklist, not a defect, safety or release determination.")
        st.caption(f"Draft token {sub_id[:8]}… · data fingerprint {fp[:12]} · editing scope or bound creates a new draft")
        if st.button("Save case to Db2", type="primary", disabled=not confirm):
            draft = {
                "client_submission_id": sub_id, "notice_text": ss.notice,
                "extraction": {"original": ss.extraction, "validation_blocking": ss.validation.blocking,
                               "validation_review": ss.validation.review},
                "intake_mode": ss.intake_mode, "provider": PROVIDER if ss.intake_mode == "ai" else None,
                "model": ss.get("model_used"), "scope": s, "rationale": ss.rationale, "bound": bound,
                "bound_accepted": bound is not None and confirm, "preview_fingerprint": fp,
            }
            try:
                case_id, created = save_case(draft)
                st.query_params["case"] = case_id
                st.success(("Saved new case " if created else "Already saved — returning existing case ") + case_id +
                           ". Open step 3 · Saved case.")
                case_param = case_id
            except (StalePreviewError, InputError) as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"Save failed and was rolled back: {type(exc).__name__}: {str(exc)[:200]}")


# ================= 3. Saved case =================
def sanitize(v):
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


with tab_case:
    with connect() as conn:
        cases = list_cases(conn, limit=500)
    if not cases:
        st.info("No saved cases yet.")
    else:
        ids = [c["ID"] for c in cases]
        is_test = {c["ID"]: c["CLIENT_SUBMISSION_ID"].startswith("test-") for c in cases}
        first_real = next((i for i in ids if not is_test[i]), ids[0])
        idx = ids.index(case_param) if case_param in ids else ids.index(first_real)
        chosen = st.selectbox("Saved cases (newest first)", ids, index=idx,
                              format_func=lambda i: next(f"{c['CREATED_AT']} UTC · {c['INSTRUMENT_ID']} · {i[:8]}"
                                                         + (" · automated test record" if is_test[i] else "") for c in cases if c["ID"] == i))
        with connect() as conn:
            case = load_case(conn, chosen)
        sc = case["SCOPE"]
        st.markdown(f"**Case {case['ID']}** · created {case['CREATED_AT']} UTC · stored snapshot (not recomputed)")
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**Scope**  \n{md(sc['instrument_id'])} · {md(sc['function_code'])} · {md(sc['unit'])}  \n{md(sc['review_start'])} → {md(sc['review_end'])}")
        c2.markdown(f"**Intake**  \n{md(sc['intake_mode'])} · {md(sc.get('model') or 'no model')}  \nBound: {sc['assumption_bound_mm'] or 'none'} mm (illustrative)")
        t = sc["totals"]
        c3.markdown(f"**Totals at save**  \n{len(t['review_lots'])} lots · {len(t['review_shipments'])} shipments · {t['review_shipped_units']} shipped / "
                    f"{t['review_unshipped_units']} unshipped units  \nInsufficient: {md(', '.join(t['insufficient_lots']) or 'none')} ({t['insufficient_shipped_units']} shipped units)")
        st.markdown(f"**Rationale:** {md(sc['window_rationale'])}")
        frows = [{"Inspection": f["INSPECTION_ID"], "Classification": f["CLASSIFICATION"], "Reason": f["REASON"],
                  "Recorded mm": f["SNAPSHOT"]["inspection"]["recorded_value"],
                  "Shipments": ", ".join(f"{x['shipment_id']}:{x['shipped_quantity']}" for x in f["SNAPSHOT"]["linked_shipments"]),
                  "Hypothetical": f["SNAPSHOT"]["hypothetical_result"] or "—"} for f in case["FINDINGS"]]
        st.dataframe(pd.DataFrame(frows), hide_index=True, width="stretch")

        # ---- review dispositions (append-only; latest event per finding is its status) ----
        rs = review_status(case)
        done = len(rs["open_ids"]) - len(rs["remaining"])
        st.markdown(f"#### Review progress: {done} of {len(rs['open_ids'])} open findings dispositioned")
        st.progress(done / len(rs["open_ids"]) if rs["open_ids"] else 1.0)
        if rs["open_ids"]:
            st.dataframe(pd.DataFrame([{
                "Inspection": i,
                "Status": DISPOSITIONS[rs["latest"][i]["DISPOSITION"]] if i in rs["latest"] else "Open — awaiting review",
                "Re-measured mm": str(rs["latest"][i]["REMEASURED_VALUE"]) if i in rs["latest"] and rs["latest"][i]["REMEASURED_VALUE"] is not None else "—",
                "By / note": f"{rs['latest'][i]['REVIEWER']}: {rs['latest'][i]['NOTE']}" if i in rs["latest"] else "—",
            } for i in rs["open_ids"]]), hide_index=True, width="stretch")
            with st.form(f"review_{chosen}", clear_on_submit=True):
                st.markdown("**Record a review outcome** (appends history; earlier entries are never edited)")
                r1, r2, r3 = st.columns([1, 1.6, 1])
                insp = r1.selectbox("Finding", rs["open_ids"])
                disp = r2.selectbox("Disposition", list(DISPOSITIONS), format_func=lambda k: DISPOSITIONS[k])
                val = r3.text_input("Re-measured value (mm)", help="Required only for re-measured dispositions.")
                note = st.text_input("Note (required)", max_chars=MAX_NOTE_CHARS)
                reviewer = st.text_input("Reviewer name (not authenticated)", max_chars=MAX_REVIEWER_CHARS)
                if st.form_submit_button("Append review event"):
                    try:
                        v = Decimal(val.strip()) if val.strip() else None
                        record_review(chosen, insp, disp, note, reviewer, v)
                        st.success(f"Recorded {insp}: {DISPOSITIONS[disp]}")
                        st.rerun()
                    except InvalidOperation:
                        st.error("Re-measured value must be a number in mm.")
                    except InputError as exc:
                        st.error(str(exc))
        st.caption("Dispositions record the manager's documented follow-up. DriftTrace does not decide product safety or release.")

        st.markdown("**Audit trail**")
        st.dataframe(pd.DataFrame([{"Event": a["EVENT_TYPE"], "At (UTC)": str(a["CREATED_AT"]), "Details": json.dumps(a["DETAILS"])} for a in case["AUDIT"]]),
                     hide_index=True, width="stretch")
        with st.expander("Original notice and stored AI extraction"):
            st.code(case["NOTICE_TEXT"], language=None)
            st.json(case["EXTRACTED"], expanded=False)
        export = {k: v for k, v in case.items() if k not in ("SCOPE_JSON", "EXTRACTED_JSON")}
        d1, d2 = st.columns(2)
        d1.download_button("Export JSON", json.dumps(export, default=str, indent=2), file_name=f"drifttrace-{chosen[:8]}.json", mime="application/json")
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(list(frows[0].keys()) if frows else [])
        for r in frows:
            w.writerow([sanitize(v) for v in r.values()])
        d2.download_button("Export findings CSV", buf.getvalue(), file_name=f"drifttrace-{chosen[:8]}.csv", mime="text/csv")
