"""The one retrieval call shared by both front ends (Streamlit app.py and the FastAPI api.py).

``do_run`` opens a Db2 connection AS THE GIVEN USER, so row and column access control (RCAC) decides what comes
back, runs NEEDLE.TRIAGE_MODE (keyword + vector + fusion in one statement) and the temporal exposure join, and
returns plain data: no live handles, never the password.
"""
from __future__ import annotations

import time

from needle import sbom
from needle.retriever import MODES, Db2Unavailable, TriageRun, run_triage

ERROR_MARKERS = ("SQL30081N", "SQL1336N", "SQL1013N", "SQL30082N", "SQL1224N", "SQL0204N", "SQL0551N",
                 "SQL0440N", "SQL0727N", "SQL0901N")


def _short_error(e: Exception) -> str:
    s = str(e)
    for marker in ERROR_MARKERS:
        if marker in s:
            i = s.index(marker)
            return s[i:i + 220]
    return s[:220]


def do_run(user: str, query: str, k: int, depth: int | None = None, password: str | None = None) -> dict:
    """Retrieval + exposure for one user. Returns a plain dict (no live handles, no password).

    ``password`` given: connect with exactly these credentials (login form). None: demo switcher (.env lookup).
    ``depth`` None (default): the RCAC router chooses the search depth for this session user.
    """
    import ibm_db

    out: dict = {"user": user, "query": query, "k": k, "depth": depth, "ts": time.strftime("%H:%M:%S")}
    try:
        conn = sbom.connect_as(user, timeout_s=10, password=password)
    except ValueError as e:
        out["fatal"] = ("login", str(e))
        return out
    except Exception as e:
        kind = "login" if ("SQL30082N" in str(e) or "no password" in str(e)) else "db"
        out["fatal"] = (kind, f"{'Sign-in failed' if kind == 'login' else 'Db2 unavailable'} for {user}: "
                              f"{_short_error(e)}")
        return out
    try:
        try:
            run = run_triage(conn, query, authid=user, k=k, depth=depth)
        except Db2Unavailable as e:
            out["fatal"] = ("db", str(e))
            return out
        except Exception as e:
            if "11434" in str(e) or "requests" in type(e).__module__:
                kind = "ollama"
            elif "SQL30081N" in str(e) or "SQL1224N" in str(e):
                kind = "db"
            else:
                kind = "sql"
            out["fatal"] = (kind, _short_error(e))
            return out
        out["run"] = run
        ids = sorted({c["ADV_ID"] for m in MODES for c in run.ranked(m)})
        t0 = time.perf_counter()
        try:
            out["exposure"] = sbom.fetch_exposure(conn, ids)
        except Exception as e:
            out["exposure"], out["exposure_error"] = [], _short_error(e)
        run.timings_ms["exposure_sql"] = round((time.perf_counter() - t0) * 1000, 1)
        try:
            r = ibm_db.fetch_tuple(ibm_db.exec_immediate(conn, "SELECT COUNT(*) FROM NEEDLE.ADV_DOC"))
            out["visible_docs"] = int(r[0])
        except Exception:
            out["visible_docs"] = None
        out["exposure_ids"] = ids
    finally:
        ibm_db.close(conn)
    return out


def title_of(doc: dict, n: int) -> str:
    """SUMMARY, or the first non-empty line of DETAILS (PYSEC records often have no summary)."""
    s = (doc.get("SUMMARY") or "").strip()
    if not s:
        s = next((l.strip(" #*") for l in (doc.get("DETAILS") or "").splitlines() if l.strip()), "")
    return s[:n]


ROUTER_HOW = {"approx-index": "approx via vector index", "deep-exact": "exact scan"}


def depth_line(run: TriageRun) -> str:
    """One line on how the RCAC router chose the search depth for this session user."""
    c = run.depth_choice or {}
    how = ROUTER_HOW.get(c.get("reason"), c.get("reason") or "fixed")
    vis, tot = c.get("visible_rows"), c.get("total_rows")
    seen = f" ({vis:,} of {tot:,} advisories visible)" if vis is not None and tot else ""
    retry = (f"; Db2 answered at depth {c['depth']} after a retry"
             if c.get("chosen_depth") and c.get("depth") != c.get("chosen_depth") else "")
    return f"Search depth {run.depth} chosen for your visibility{seen}: {how}{retry}"


def osv_link(adv_id: str) -> str:
    return f"https://osv.dev/vulnerability/{adv_id}"
