"""LangChain retriever over NEEDLE.TRIAGE (owner: app agent).

``Db2HybridRetriever`` runs on the CALLER'S OWN ibm_db connection, so Db2 row and column access control
(RCAC) decides what the retriever can return: the user's auth id is the session user of every statement.

Path, in order:
1. needle.triage.call_triage (bm25 agent) -> CALL NEEDLE.TRIAGE_MODE(..., 'HYBRID'), on an ibm_db_dbi wrapper of the same handle.
2. ``CALL NEEDLE.TRIAGE(P_QVEC, P_QTERMS, P_K, P_DEPTH)`` (fusion inside Db2; signature in sql/03_triage_proc.sql).
3. NEEDLE.TRIAGE is a required object (installed by setup). If it is missing (SQL0440N/SQL0204N) the run stops
   with Db2Unavailable and a clear message; there is no direct-SQL fallback (analysts have EXECUTE on the
   procedures but no SELECT on NEEDLE.TERM_DF / NEEDLE.CORPUS_STATS since the C1 fix).
Depth: None (default) = chosen per session user by the RCAC router in needle.triage.choose_depth.

Defence in depth for RCAC: an id from step 1-3 is shown only if the same connection can also read its
NEEDLE.ADV_DOC row. An advisory the user cannot read never reaches the UI, the SQL panel or the LLM.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict, Field, PrivateAttr

ROOT = Path(__file__).resolve().parents[2]
TRIAGE_SQL_FILE = ROOT / "sql" / "03_triage_proc.sql"
MODES = ("keyword", "vector", "hybrid")

class Db2Unavailable(RuntimeError):
    """Db2 cannot be reached or a required object is missing; the UI shows this state."""


@dataclass
class TriageRun:
    query: str
    authid: str
    path: str = ""
    candidates: list[dict] = field(default_factory=list)  # ADV_ID, RRF, KW_RANK, VEC_RANK, VEC_DIST
    docs: dict[str, dict] = field(default_factory=dict)  # visible ADV_DOC rows by id
    dropped_invisible: int = 0
    sql_text: str = ""
    call_text: str = ""
    params_display: dict = field(default_factory=dict)
    timings_ms: dict = field(default_factory=dict)
    k: int = 10
    depth: int = 0                      # the P_DEPTH that answered (set by run_triage)
    depth_choice: dict = field(default_factory=dict)  # router: depth, reason, visible_rows, total_rows

    def ranked(self, mode: str, k: int | None = None) -> list[dict]:
        """Top-k VISIBLE candidates for one leg (see ``top_candidates``)."""
        return top_candidates([c for c in self.candidates if c["ADV_ID"] in self.docs], mode, int(k or self.k))


def top_candidates(rows: list[dict], mode: str, k: int) -> list[dict]:
    """keyword/vector: by that leg's rank (rows without a rank in that leg are skipped); hybrid: by RRF."""
    if mode == "keyword":
        rows = sorted((c for c in rows if c.get("KW_RANK")), key=lambda c: (int(c["KW_RANK"]), c["ADV_ID"]))
    elif mode == "vector":
        rows = sorted((c for c in rows if c.get("VEC_RANK")), key=lambda c: (int(c["VEC_RANK"]), c["ADV_ID"]))
    elif mode == "hybrid":
        rows = sorted(rows, key=lambda c: (-float(c.get("RRF") or 0), c["ADV_ID"]))
    else:
        raise ValueError(f"mode must be one of {MODES}")
    return rows[:k]


def _fetch_all(stmt) -> list[dict]:
    import ibm_db

    out = []
    r = ibm_db.fetch_assoc(stmt)
    while r:
        out.append({k.upper(): (v.strip() if isinstance(v, str) else v) for k, v in r.items()})
        r = ibm_db.fetch_assoc(stmt)
    return out


def _sqlcode(e: Exception) -> str:
    m = re.search(r"SQL\d{4,5}[NWC]", str(e))
    return m.group(0) if m else ""


def query_inputs(query: str) -> tuple[list[float], list[str]]:
    """(query vector, query terms): nomic-embed-text ('search_query: ') and the shared BM25 analyzer."""
    from needle.bm25 import query_terms
    from needle.embed import embed_query

    return [float(x) for x in embed_query(query)], list(query_terms(query))


def triage_sql_text() -> str:
    """The SQL shown in the UI: BM25_SEARCH + TRIAGE_MODE from the bm25 agent's sql/03_triage_proc.sql."""
    if not TRIAGE_SQL_FILE.exists():
        return ""
    blocks = re.split(r"(?m)^@\s*$", TRIAGE_SQL_FILE.read_text(encoding="utf-8"))
    keep = []
    for b in blocks:
        code = "\n".join(l for l in b.strip().splitlines() if not l.lstrip().startswith("--"))
        if ("FUNCTION NEEDLE.BM25_SEARCH" in code) or ("PROCEDURE NEEDLE.TRIAGE_MODE" in code):
            keep.append(code.strip())
    return "\n\n".join(keep) if keep else TRIAGE_SQL_FILE.read_text(encoding="utf-8")


MISSING_TRIAGE = ("NEEDLE.TRIAGE / NEEDLE.TRIAGE_MODE is not installed (or not executable for this user). "
                  "It is a required object: run sql/03_triage_proc.sql and sql/04_rcac.sql (setup).")


def _call_triage(conn: Any, qvec: list[float], terms: list[str], k: int,
                 depth: int | None) -> tuple[list[dict], str, dict]:
    """Return (rows, path, depth_choice). Runs on ``conn``, the caller's own connection.

    ``depth=None``: the RCAC router (needle.triage.choose_depth) picks the depth for the SESSION USER of ``conn``
    from the user's own k, exactly as ``call_triage(depth=None)`` would. P_K is then widened to 2 * depth so all
    fused candidates come back and the UI can show the keyword / vector / hybrid top-k side by side (the router
    rule depends on k, so the wide P_K must not be passed to the router).
    """
    import ibm_db_dbi

    from needle import triage as tri  # bm25 agent's wrapper (NEEDLE.TRIAGE_MODE, all values bound)

    dbi = ibm_db_dbi.Connection(conn)  # wraps the user's handle; never closed here (caller owns it)
    try:
        choice = tri.choose_depth(dbi, int(k)) if depth is None else tri.DepthChoice(int(depth), "explicit")
        hits, answered, _ = tri.call_triage_ex(dbi, qvec, terms, k=min(1000, 2 * choice.depth),
                                               depth=choice.depth, mode="HYBRID")
    except Exception as e:
        if _sqlcode(e) in ("SQL0440N", "SQL0204N"):
            raise Db2Unavailable(MISSING_TRIAGE) from e
        raise
    rows = [{"ADV_ID": h.adv_id, "RRF": h.rrf, "KW_RANK": h.kw_rank, "VEC_RANK": h.vec_rank,
             "VEC_DIST": h.vec_dist} for h in hits]
    info = {"depth": int(answered), "chosen_depth": choice.depth, "reason": choice.reason,
            "visible_rows": choice.visible_rows, "total_rows": choice.total_rows,
            "session_user": choice.session_user}
    return rows, "CALL NEEDLE.TRIAGE_MODE(..., 'HYBRID')", info


def fetch_docs(conn: Any, ids: Sequence[str]) -> dict[str, dict]:
    """ADV_DOC rows the CALLER can read (RCAC), plus aliases. Invisible ids are simply absent."""
    import ibm_db

    ids = list(dict.fromkeys(ids))
    if not ids:
        return {}
    marks = ", ".join("?" * len(ids))
    stmt = ibm_db.prepare(conn, f"SELECT ADV_ID, KIND, SUMMARY, DETAILS, PACKAGES, PUBLISHED, CVSS, EMBARGO_UNTIL "
                                f"FROM NEEDLE.ADV_DOC WHERE ADV_ID IN ({marks})")
    ibm_db.execute(stmt, tuple(ids))
    docs = {r["ADV_ID"]: r for r in _fetch_all(stmt)}
    ibm_db.free_stmt(stmt)
    for d in docs.values():
        d["PACKAGES_LIST"] = [p for p in re.split(r"[\s,;]+", d.get("PACKAGES") or "") if p]
        d["ALIASES"] = []
    if docs:
        try:
            vis = list(docs)
            stmt = ibm_db.prepare(conn, f"SELECT ADV_ID, ALIAS FROM NEEDLE.ADV_ALIAS WHERE ADV_ID IN "
                                        f"({', '.join('?' * len(vis))}) ORDER BY ADV_ID, ALIAS")
            ibm_db.execute(stmt, tuple(vis))
            for r in _fetch_all(stmt):
                docs[r["ADV_ID"]]["ALIASES"].append(r["ALIAS"])
            ibm_db.free_stmt(stmt)
        except Exception:
            pass  # aliases are optional (privilege or table missing)
    return docs


def run_triage(conn: Any, query: str, authid: str = "", k: int = 10, depth: int | None = None) -> TriageRun:
    """Embed + one Db2 statement + visible-docs fetch, all on the caller's connection.

    ``depth=None`` (default): the RCAC router chooses the depth for the session user; an int overrides it."""
    k = int(k)
    if not 1 <= k <= 50 or (depth is not None and not 1 <= int(depth) <= 500):
        raise ValueError("k must be 1..50 and depth 1..500")
    run = TriageRun(query=query, authid=authid, k=k)
    t0 = time.perf_counter()
    qvec, terms = query_inputs(query)
    run.timings_ms["embed"] = round((time.perf_counter() - t0) * 1000, 1)
    t1 = time.perf_counter()
    rows, path, info = _call_triage(conn, qvec, terms, k, depth)
    run.timings_ms["triage_sql"] = round((time.perf_counter() - t1) * 1000, 1)
    run.path = path
    run.depth_choice = info
    depth = run.depth = int(info["depth"])
    run.candidates = rows
    ids = {c["ADV_ID"] for mode in MODES for c in top_candidates(rows, mode, k)}
    t2 = time.perf_counter()
    run.docs = fetch_docs(conn, sorted(ids))
    run.timings_ms["docs_sql"] = round((time.perf_counter() - t2) * 1000, 1)
    run.dropped_invisible = len(ids - set(run.docs))
    run.sql_text = triage_sql_text() or "-- procedure source not found in sql/03_triage_proc.sql"
    run.call_text = "CALL NEEDLE.TRIAGE_MODE(?, ?, ?, ?, 'HYBRID')  -- = NEEDLE.TRIAGE(?, ?, ?, ?)"
    run.params_display = {"P_QVEC": "[768 x FLOAT32] nomic-embed-text('search_query: ' + text)",
                          "P_QTERMS": terms[:64], "P_K": min(1000, 2 * depth), "P_DEPTH": depth,
                          "depth_reason": run.depth_choice.get("reason")}
    return run


def to_document(cand: dict, doc: dict) -> Document:
    text = (doc.get("SUMMARY") or "") + "\n\n" + (doc.get("DETAILS") or "")
    return Document(
        page_content=text.strip(),
        metadata={
            "adv_id": cand["ADV_ID"], "rrf": float(cand["RRF"]) if cand.get("RRF") is not None else None,
            "kw_rank": cand.get("KW_RANK"), "vec_rank": cand.get("VEC_RANK"),
            "vec_dist": float(cand["VEC_DIST"]) if cand.get("VEC_DIST") is not None else None,
            "summary": doc.get("SUMMARY"), "packages": doc.get("PACKAGES_LIST", []),
            "aliases": doc.get("ALIASES", []), "kind": doc.get("KIND"),
            "published": str(doc.get("PUBLISHED") or ""), "cvss": doc.get("CVSS"),
        },
    )


class Db2HybridRetriever(BaseRetriever):
    """Permission-aware hybrid retriever: NEEDLE.TRIAGE on the caller's own Db2 connection.

    ``conn`` must be opened with the end user's credentials (for example NDL_JUNIOR); the retriever never
    opens a connection of its own, so it cannot see more than the user.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    conn: Any = Field(exclude=True)
    authid: str = ""
    k: int = 10
    depth: int | None = None  # None = RCAC router chooses per session user
    mode: str = "hybrid"
    _last_run: TriageRun | None = PrivateAttr(default=None)

    @property
    def last_run(self) -> TriageRun | None:
        return self._last_run

    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun) -> list[Document]:
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        run = run_triage(self.conn, query, authid=self.authid, k=self.k, depth=self.depth)
        self._last_run = run
        return [to_document(c, run.docs[c["ADV_ID"]]) for c in run.ranked(self.mode, self.k)]
