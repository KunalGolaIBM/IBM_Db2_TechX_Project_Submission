"""Python wrapper for NEEDLE.TRIAGE / NEEDLE.TRIAGE_MODE (sql/03_triage_proc.sql).

The query is embedded with Ollama nomic-embed-text (``search_query: `` prefix, via needle.embed.embed_query)
and analyzed with the BM25 analyzer (needle.bm25.query_terms = shared tokenizer + stop words). Both go to Db2
as parameters; retrieval, BM25 scoring and reciprocal rank fusion all run inside Db2.

    from needle.triage import triage
    res = triage("yaml load lets an attacker run code", k=10)   # HYBRID; depth chosen per user (RCAC router)
    res.depth, res.depth_choice                                    # e.g. 50 'approx-index' / 128 'deep-exact'
    res = triage(text, mode="KW")   # keyword only        res = triage(text, mode="VEC", depth=50)  # explicit depth

CLI:  python -m needle.triage "query text" [--k 10] [--depth N] [--mode HYBRID|KW|VEC]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from needle.bm25 import query_terms

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
MODES = ("HYBRID", "KW", "VEC")

# Depth (P_DEPTH, used by both legs) per caller visibility, chosen with the RCAC router (needle.rcac.choose_strategy).
# Under RCAC every plan carries the row permission with filter factor 0.495, and Db2 sizes the vector IXSCAN at
# depth / 0.495: depth 50 (~101 candidates) keeps IXSCAN on ADV_DOC_VIX; from depth 100 Db2 switches to an exact
# table scan (docs/evidence/rcac_real.md, docs/evidence/triage_router_explain.md).
TRIAGE_APPROX_DEPTH = 50   # router says APPROX with depth <= 50 (high visibility): ANN through the vector index
TRIAGE_DEEP_DEPTH = 128    # router says EXACT or a deeper APPROX (low visibility): exact scan (the optimizer's
                           # choice at 26,210 rows), full recall in our runs
SQL0901N_DEPTHS = (99, 100)  # FETCH APPROX FIRST 99/100 raised SQL0901N on 12.1.5.0 (eval_sql0901n_fetch_approx.md)


@dataclass(frozen=True)
class TriageHit:
    adv_id: str
    rrf: float
    kw_rank: int | None
    vec_rank: int | None
    vec_dist: float | None


@dataclass(frozen=True)
class DepthChoice:
    """Search depth for one caller. ``reason``: 'approx-index' | 'deep-exact' (router) or 'explicit' (caller)."""
    depth: int
    reason: str
    session_user: str | None = None
    visible_rows: int | None = None
    total_rows: int | None = None
    router_mode: str | None = None
    router_depth: int | None = None

    @property
    def visible_fraction(self) -> float | None:
        if self.visible_rows is None or not self.total_rows or self.total_rows <= 0:
            return None
        return self.visible_rows / max(self.total_rows, self.visible_rows)


@dataclass
class TriageResult:
    hits: list[TriageHit]
    terms: list[str]
    mode: str
    k: int
    depth: int                      # the P_DEPTH that answered (UI: "search depth chosen for your visibility")
    timings_ms: dict[str, float] = field(default_factory=dict)
    depth_choice: DepthChoice | None = None


def depth_for_visibility(visible_rows: int, total_rows: int, k: int) -> DepthChoice:
    """Pure rule (no DB): RCAC router strategy -> TRIAGE depth.

    Router APPROX with depth <= 50 (and k < 50) -> 50, which keeps the vector index under the RCAC filter factor;
    anything else (router EXACT, or APPROX deeper than 50) -> max(128, 2k), a depth at which Db2 runs the exact table
    scan, so a low-visibility user gets full recall instead of an under-filled ANN result. Never 99/100 (SQL0901N)."""
    from needle.rcac import choose_strategy

    k = int(k)
    s = choose_strategy(visible_rows, total_rows, k)
    if s.mode == "APPROX" and s.depth <= TRIAGE_APPROX_DEPTH and k < TRIAGE_APPROX_DEPTH:
        depth, reason = TRIAGE_APPROX_DEPTH, "approx-index"
    else:
        depth, reason = min(1000, max(TRIAGE_DEEP_DEPTH, 2 * k)), "deep-exact"
    if depth in SQL0901N_DEPTHS:
        depth = TRIAGE_DEEP_DEPTH
    return DepthChoice(depth, reason, None, s.visible_rows, s.total_rows, s.mode, s.depth)


_VISIBILITY_ATTR = "_needle_visibility"


def choose_depth(conn, k: int) -> DepthChoice:
    """Depth for the session user of ``conn`` (ibm_db_dbi). Visibility (COUNT(*) on NEEDLE.ADV_DOC as that user, under
    RCAC, and SYSCAT cardinality) is read once and cached on the connection object."""
    from needle.rcac import visible_and_total

    cached = getattr(conn, _VISIBILITY_ATTR, None)
    if cached is None:
        handle = getattr(conn, "conn_handler", conn)  # raw ibm_db handle behind ibm_db_dbi
        cur = conn.cursor()
        try:
            cur.execute("SELECT SESSION_USER FROM SYSIBM.SYSDUMMY1")
            user = str(cur.fetchone()[0]).strip()
        finally:
            cur.close()
        visible, total = visible_and_total(handle, "NEEDLE.ADV_DOC")
        cached = (user, visible, total)
        try:
            setattr(conn, _VISIBILITY_ATTR, cached)
        except AttributeError:
            pass  # not cacheable on this object: recomputed next call
    user, visible, total = cached
    c = depth_for_visibility(visible, total, k)
    return DepthChoice(c.depth, c.reason, user, c.visible_rows, c.total_rows, c.router_mode, c.router_depth)


def connect(user: str | None = None, password: str | None = None):
    """ibm_db_dbi connection from needle/.env (DB2_HOST/PORT/DATABASE/USER/PASSWORD). Caller closes it.

    ``user``/``password`` override DB2_USER/DB2_PASSWORD (e.g. an RCAC test user such as NDL_JUNIOR)."""
    import ibm_db_dbi

    try:
        from dotenv import dotenv_values
        file_env = dotenv_values(ROOT / ".env")
    except ImportError:  # e.g. inside the codespace, where only environment variables are used
        file_env = {}
    env = {**file_env, **{k: v for k, v in os.environ.items() if k.startswith("DB2_")}}
    dsn = (f"DATABASE={env['DB2_DATABASE']};HOSTNAME={env['DB2_HOST']};PORT={env['DB2_PORT']};PROTOCOL=TCPIP;"
           f"UID={user or env['DB2_USER']};PWD={password or env['DB2_PASSWORD']};CONNECTTIMEOUT=30;")
    return ibm_db_dbi.connect(dsn, "", "")


def vector_literal(vec: Sequence[float]) -> str:
    """Serialize a query embedding for VECTOR(CAST(? AS CLOB(100K)), 768, FLOAT32)."""
    if len(vec) != 768:
        raise ValueError(f"expected a 768-dim vector, got {len(vec)}")
    return json.dumps([float(x) for x in vec], separators=(",", ":"))


def call_triage(conn, qvec: Sequence[float] | None, terms: Sequence[str], k: int = 10, depth: int | None = None,
                mode: str = "HYBRID") -> list[TriageHit]:
    """CALL NEEDLE.TRIAGE_MODE on an open ibm_db_dbi connection; all values are bound parameters.

    ``depth=None`` (default): chosen per session user by ``choose_depth`` (RCAC router); an int overrides it."""
    return call_triage_ex(conn, qvec, terms, k=k, depth=depth, mode=mode)[0]


def call_triage_ex(conn, qvec: Sequence[float] | None, terms: Sequence[str], k: int = 10, depth: int | None = None,
                   mode: str = "HYBRID") -> tuple[list[TriageHit], int, DepthChoice]:
    """As ``call_triage``; also returns the depth that answered and how the depth was chosen."""
    mode = mode.upper()
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    k = int(k)
    choice = choose_depth(conn, k) if depth is None else DepthChoice(int(depth), "explicit")
    depth = choice.depth
    qv = vector_literal(qvec) if qvec is not None else None
    qt = json.dumps(list(terms), ensure_ascii=False)
    # Db2 12.1.5.0 CE raised SQL0901N "Fetched nodes unexpectedly unsorted" for FETCH APPROX FIRST 100 (and 99)
    # on one query vector (docs/evidence/eval_sql0901n_fetch_approx.md). Retry only on that error, at other
    # depths, and record which depth answered so the fallback is visible, never silent.
    rows: list = []
    last_err: Exception | None = None
    answered = depth
    for attempt_depth in dict.fromkeys((depth, 64, 128)):
        cur = conn.cursor()
        try:
            cur.callproc("NEEDLE.TRIAGE_MODE", (qv, qt, k, attempt_depth, mode))
            rows = cur.fetchall() or []
            if attempt_depth != depth:
                log.warning("TRIAGE depth %d hit SQL0901N; answered with depth %d", depth, attempt_depth)
            answered = attempt_depth
            last_err = None
            break
        except Exception as e:  # ibm_db_dbi raises its own exception classes
            if "SQL0901N" not in str(e):
                raise
            last_err = e
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            cur.close()
    if last_err is not None:
        raise last_err
    hits = [TriageHit(str(r[0]).strip(), float(r[1]),
                      None if r[2] is None else int(r[2]),
                      None if r[3] is None else int(r[3]),
                      None if r[4] is None else float(r[4])) for r in rows]
    return hits, answered, choice


def triage(text: str, k: int = 10, depth: int | None = None, mode: str = "HYBRID", conn=None) -> TriageResult:
    """Embed + tokenize ``text`` and run NEEDLE.TRIAGE_MODE. Opens (and closes) a connection if none is given."""
    from needle.embed import embed_query

    timings: dict[str, float] = {}
    t = time.perf_counter()
    terms = query_terms(text)
    timings["tokenize"] = (time.perf_counter() - t) * 1000
    qvec = None
    if mode.upper() in ("HYBRID", "VEC"):
        t = time.perf_counter()
        qvec = embed_query(text)
        timings["embed"] = (time.perf_counter() - t) * 1000
    own = conn is None
    if own:
        conn = connect()
    try:
        t = time.perf_counter()
        hits, answered, choice = call_triage_ex(conn, qvec, terms, k=k, depth=depth, mode=mode)
        timings["db_call"] = (time.perf_counter() - t) * 1000  # includes the one-time visibility lookup
    finally:
        if own:
            conn.close()
    return TriageResult(hits, terms, mode.upper(), int(k), int(answered), timings, choice)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("text")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--depth", type=int, default=None, help="default: chosen per user by the RCAC router")
    ap.add_argument("--mode", default="HYBRID", choices=MODES)
    a = ap.parse_args()
    res = triage(a.text, a.k, a.depth, a.mode)
    c = res.depth_choice
    print(f"depth={res.depth} ({c.reason if c else '?'}; user={c.session_user if c else None}, "
          f"visible={c.visible_rows if c else None}/{c.total_rows if c else None})")
    print(f"terms={res.terms[:20]}{'...' if len(res.terms) > 20 else ''}")
    print(f"timings_ms={ {k: round(v, 1) for k, v in res.timings_ms.items()} }")
    for i, h in enumerate(res.hits, 1):
        vd = "" if h.vec_dist is None else f"{h.vec_dist:.4f}"
        print(f"{i:>3} {h.adv_id:<24} rrf={h.rrf:.6f} kw={h.kw_rank} vec={h.vec_rank} dist={vd}")


if __name__ == "__main__":
    main()
