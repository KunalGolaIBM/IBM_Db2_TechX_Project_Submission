"""Small presentation helpers: DataFrames built only from fields Db2 actually returned."""

from __future__ import annotations

import pandas as pd

from ..models import LockAnalysis, Note, Severity, Snapshot

SEVERITY_ICON = {Severity.INFO: "🔵", Severity.WARNING: "🟠", Severity.CRITICAL: "🔴"}

PROVENANCE_LABEL = {
    "db2_lockwait": "Reported by Db2",
    "lock_table_match": "Inferred (single granted holder of same lock)",
    "ambiguous": "Ambiguous (several holders)",
    "holder_gone": "Holder no longer exists",
    "unknown": "Unknown",
}


def severity_text(sev: Severity | str) -> str:
    s = Severity.parse(sev)
    return f"{SEVERITY_ICON[s]} {s.name}"


def _drop_empty(df: pd.DataFrame) -> pd.DataFrame:
    """Hide columns where Db2 returned nothing, rather than showing columns of blanks."""
    keep = [c for c in df.columns if df[c].notna().any() and (df[c].astype(str) != "").any()]
    return df[keep]


def waits_dataframe(analysis: LockAnalysis, snapshot: Snapshot) -> pd.DataFrame:
    rows = []
    for e in analysis.edges:
        w = snapshot.sessions.get(e.waiter) if e.waiter is not None else None
        h = snapshot.sessions.get(e.holder) if e.holder is not None else None
        rows.append({
            "Waiting app": e.waiter,
            "Waiting application": w.application_name if w else None,
            "Waiting user": w.system_auth_id if w else None,
            "Blocked by": e.holder if e.holder is not None else (
                ", ".join(map(str, e.holder_candidates)) or None),
            "Blocker application": h.application_name if h else None,
            "Blocker user": h.system_auth_id if h else None,
            "Blocker state": h.workload_state if h else None,
            "How known": PROVENANCE_LABEL.get(e.provenance, e.provenance),
            "Locked object": e.resource_label,
            "Mode requested": e.lock_mode_requested,
            "Mode held": e.lock_mode_held,
            "Waited (s)": e.wait_seconds,
            "Wait started": e.wait_start_time,
            "On wait cycle": "yes" if e.on_cycle else None,
        })
    return _drop_empty(pd.DataFrame(rows))


def locks_dataframe(snapshot: Snapshot) -> pd.DataFrame:
    rows = []
    for lk in snapshot.locks:
        s = snapshot.sessions.get(lk.application_handle) if lk.application_handle is not None else None
        res = snapshot.resources.get(lk.lock_name_hex or "")
        rows.append({
            "App handle": lk.application_handle,
            "Application": s.application_name if s else None,
            "User": s.system_auth_id if s else None,
            "Object type": lk.lock_object_type,
            "Locked object": res.label if res else None,
            "Mode": lk.lock_mode,
            "Status": {"G": "G (granted)", "W": "W (waiting)", "C": "C (converting)"}.get(
                lk.lock_status or "", lk.lock_status),
            "Count": lk.lock_count,
            "Lock name": lk.lock_name_hex,
        })
    return _drop_empty(pd.DataFrame(rows))


def render_notes(st, notes: list[Note]) -> None:
    for n in notes:
        {"error": st.error, "warning": st.warning}.get(n.level, st.info)(n.message)
