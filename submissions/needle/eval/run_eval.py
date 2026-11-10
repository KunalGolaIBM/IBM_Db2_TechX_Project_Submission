"""NEEDLE retrieval evaluation on the frozen query slices (eval/queries/*.jsonl).

Run from the needle/ folder (Db2 reachable at DB2_HOST:DB2_PORT, Ollama running):
    .venv\\Scripts\\python eval\\run_eval.py                          # all slices, all retrievers
    .venv\\Scripts\\python eval\\run_eval.py --retrievers exact,approx --limit 10   # smoke run
    .venv\\Scripts\\python eval\\run_eval.py --mock                   # pipeline check, no DB

Two metric families, reported separately and never mixed:
  RELEVANCE     against canon_id ground truth (gt = all non-withdrawn adv_ids sharing the query's
                canon_id). recall@k = share of queries with at least one gt adv_id in the top k
                (k = 1, 3, 10); mrr@10 = mean of 1/rank of the first gt hit (0 if none in the top 10);
                set_recall@10 = mean share of the gt set found in the top 10 (secondary).
  ANN FIDELITY  APPROX top-10 vs EXACT top-10 for the same query vector and the same filter:
                overlap@10 = |approx ∩ exact| / |exact|. Says nothing about relevance.

Retrievers (each returns at most 10 adv_ids):
  bm25        keyword-only BM25 in plain SQL: NEEDLE.TRIAGE_MODE(..., 'KW') = NEEDLE.BM25_SEARCH
              (the bm25 agent's single BM25 implementation; query terms from needle.bm25.query_terms).
  exact       VECTOR_DISTANCE(... COSINE) ORDER BY ... FETCH EXACT FIRST 10 ROWS ONLY
  approx      same with FETCH APPROX FIRST 10 ROWS ONLY (literal 10: a parameter marker never
              uses the vector index)
  rrf_client  reciprocal rank fusion IN PYTHON of the KW leg and an APPROX leg (depth 100, k_rrf 60):
              a parity check for the in-Db2 fusion, not a product feature.
  triage      NEEDLE.TRIAGE_MODE(..., 'HYBRID') = NEEDLE.TRIAGE (fusion inside Db2), through
              needle.triage.call_triage with k=10, depth=100.
  db2vs       OPT-IN. langchain-db2 1.0.0 DB2VS.similarity_search on its own table layout
              (NDL_DEV_EVAL.DB2VS_ADV: id, text, BSON metadata, nullable VECTOR, no index). The eval never
              fills that table (owned by the connector-findings agent); it runs only when the table holds
              as many rows as NEEDLE.ADV_DOC.
  exact_b50 / approx_b50   filter test: the same vector legs with WHERE ROW_BUCKET < 50.
              Relevance is computed only for queries whose gt is visible (row_bucket < 50);
              every returned row is checked against the filter.
Query vectors: Ollama nomic-embed-text with the "search_query: " prefix (needle.embed).
Latency: client-observed wall time of one retrieval call (execute + fetch) through the
gh port-forward tunnel, excluding query embedding (reported separately). Warm-up calls excluded.

Gate (exit code 1): recall@10 of GATE_RETRIEVER on the named slice < GATE_MIN (0.80).
Rationale, fixed before the first real run: named queries are verbatim advisory summaries that
contain the package name and the source advisory is in the corpus, so a working hybrid
retriever must find a correct advisory in its top 10 for at least 80% of them.
Exit codes: 0 pass, 1 gate failed or a setup error raised as SystemExit (sha256 mismatch, saved vectors
that do not match the queries), 2 DB unreachable, 3 gate retriever not evaluated (use --no-gate for partial
runs; the JSON still records it).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import platform
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # needle/
sys.path.insert(0, str(ROOT / "src"))

QDIR = ROOT / "eval" / "queries"
RDIR = ROOT / "eval" / "results"
DOCS = ROOT / "data" / "docs.jsonl"
EVIDENCE = ROOT / "docs" / "evidence"

K = 10
SLICES = ("named", "masked", "paraphrase")
ALL_RETRIEVERS = ("bm25", "exact", "approx", "rrf_client", "triage", "db2vs", "exact_b50", "approx_b50")
CHART_RETRIEVERS = ("triage", "bm25", "exact", "approx", "rrf_client", "db2vs")  # fixed color slots
GATE_RETRIEVER, GATE_SLICE, GATE_METRIC, GATE_MIN = "triage", "named", "recall@10", 0.80
RRF_K, RRF_DEPTH, TRIAGE_DEPTH = 60, 100, 100  # depth = needle.triage default
FILTER_BUCKET_LT = 50
DB2VS_TABLE = "NDL_DEV_EVAL.DB2VS_ADV"
WARMUP = 3
EXPLAIN_TAG = "NDLEVAL"


# ================================================================================================
# Metrics (pure functions; tests/test_eval_metrics.py)
# ================================================================================================
def first_hit_rank(ranked: list[str], gt) -> int | None:
    g = set(gt)
    for i, a in enumerate(ranked, 1):
        if a in g:
            return i
    return None


def recall_at(ranked: list[str], gt, k: int) -> float:
    """1.0 if any gt id is in the top k (hit@k), else 0.0."""
    r = first_hit_rank(ranked[:k], gt)
    return 1.0 if r is not None else 0.0


def reciprocal_rank(ranked: list[str], gt, k: int = K) -> float:
    r = first_hit_rank(ranked[:k], gt)
    return 1.0 / r if r else 0.0


def set_recall_at(ranked: list[str], gt, k: int) -> float:
    g = set(gt)
    return len(g & set(ranked[:k])) / len(g) if g else 0.0


def overlap_at(approx: list[str], exact: list[str], k: int = K) -> float | None:
    """ANN fidelity: share of the exact top-k that the approximate top-k also returned."""
    e = exact[:k]
    if not e:
        return None
    return len(set(approx[:k]) & set(e)) / len(e)


def percentile(values: list[float], p: float) -> float | None:
    """Linear-interpolation percentile (numpy 'linear'); p in [0, 100]."""
    v = sorted(x for x in values if x is not None)
    if not v:
        return None
    if len(v) == 1:
        return v[0]
    pos = (len(v) - 1) * p / 100.0
    lo, hi = math.floor(pos), math.ceil(pos)
    return v[lo] + (v[hi] - v[lo]) * (pos - lo)


def rrf_fuse(rank_lists: list[list[str]], k_rrf: int = RRF_K, top: int = K) -> list[str]:
    """Reciprocal rank fusion: score(d) = sum 1/(k_rrf + rank). Ties broken by adv_id."""
    score: dict[str, float] = {}
    for lst in rank_lists:
        for r, a in enumerate(lst, 1):
            score[a] = score.get(a, 0.0) + 1.0 / (k_rrf + r)
    return [a for a, _ in sorted(score.items(), key=lambda x: (-x[1], x[0]))][:top]


def summarize_relevance(rows: list[dict]) -> dict:
    """rows: dicts with 'ranked', 'gt', 'latency_ms', 'error'. Only rows with gt are scored."""
    scored = [r for r in rows if r.get("gt")]
    n = len(scored)
    lat = [r["latency_ms"] for r in rows if r.get("latency_ms") is not None and not r.get("error")]
    out = {"n": n, "errors": sum(1 for r in rows if r.get("error"))}
    for k in (1, 3, 10):
        out[f"recall@{k}"] = round(sum(recall_at(r["ranked"], r["gt"], k) for r in scored) / n, 4) if n else None
    out["mrr@10"] = round(sum(reciprocal_rank(r["ranked"], r["gt"]) for r in scored) / n, 4) if n else None
    out["set_recall@10"] = round(sum(set_recall_at(r["ranked"], r["gt"], 10) for r in scored) / n, 4) if n else None
    out["latency_p50_ms"] = _r1(percentile(lat, 50))
    out["latency_p95_ms"] = _r1(percentile(lat, 95))
    out["returned_lt_k"] = sum(1 for r in rows if not r.get("error") and len(r["ranked"]) < K)
    return out


def _r1(x):
    return None if x is None else round(x, 1)


# ================================================================================================
# Query sets
# ================================================================================================
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_slice(name: str) -> tuple[list[dict], str, dict]:
    p, s = QDIR / f"{name}.jsonl", QDIR / f"{name}.sha256"
    want = s.read_text(encoding="utf-8").split()[0]
    got = sha256_file(p)
    if want != got:
        raise SystemExit(f"SETUP ERROR: {p.name} sha256 {got} != frozen {want}. Refusing to run.")
    man_p = QDIR / f"{name}.manifest.json"
    manifest = json.loads(man_p.read_text(encoding="utf-8")) if man_p.exists() else {}
    with open(p, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()], got, manifest


# ================================================================================================
# Embedding
# ================================================================================================
def ollama_model_info(url: str, model: str) -> dict:
    import requests

    r = requests.get(f"{url}/api/tags", timeout=30)
    r.raise_for_status()
    for m in r.json().get("models", []):
        if m.get("name") in (model, f"{model}:latest") or m.get("model") in (model, f"{model}:latest"):
            return {"name": m.get("name"), "digest": m.get("digest"),
                    "quantization": (m.get("details") or {}).get("quantization_level")}
    return {"name": model, "digest": None}


def embed_queries(queries: list[dict], url: str, model: str) -> tuple[dict[str, list[float]], list[float]]:
    """One Ollama call per query (latency measured per query). Returns ({qid: vec}, latencies ms)."""
    import requests

    from needle.embed import QUERY_PREFIX, embed_batch

    vecs, lat = {}, []
    with requests.Session() as s:
        embed_batch(s, url, model, [QUERY_PREFIX + "warm up"])
        for q in queries:
            t0 = time.perf_counter()
            vecs[q["qid"]] = embed_batch(s, url, model, [QUERY_PREFIX + q["query"]])[0]
            lat.append((time.perf_counter() - t0) * 1000)
    return vecs, lat


def vec_text(v: list[float]) -> str:
    return json.dumps(v, separators=(",", ":"))


# ================================================================================================
# SQL legs
# ================================================================================================
def _int(x, lo=1, hi=1000) -> int:
    v = int(x)
    if not lo <= v <= hi:
        raise ValueError(f"integer {v} out of range [{lo},{hi}]")
    return v


def vector_sql(mode: str, k: int, bucket_lt: int | None = None) -> str:
    if mode not in ("EXACT", "APPROX"):
        raise ValueError(mode)
    where = "" if bucket_lt is None else f" WHERE ROW_BUCKET < {_int(bucket_lt, 0, 100)}"
    return ("SELECT ADV_ID, VECTOR_DISTANCE(EMB, VECTOR(CAST(? AS CLOB(100K)), 768, FLOAT32), COSINE) AS DIST "
            f"FROM NEEDLE.ADV_DOC{where} ORDER BY DIST FETCH {mode} FIRST {_int(k)} ROWS ONLY")


def query_terms(text: str) -> list[str]:
    """The ONE BM25 query analyzer (needle.bm25: shared tokenizer + stop words, distinct terms)."""
    from needle.bm25 import query_terms as qt

    return qt(text)


# ================================================================================================
# Db2 access
# ================================================================================================
def connect(user: str | None = None, password: str | None = None):
    import ibm_db_dbi

    e = os.environ
    cs = (f"DATABASE={e['DB2_DATABASE']};HOSTNAME={e['DB2_HOST']};PORT={e['DB2_PORT']};PROTOCOL=TCPIP;"
          f"UID={user or e['DB2_USER']};PWD={password or e['DB2_PASSWORD']};CONNECTTIMEOUT=20;")
    conn = ibm_db_dbi.connect(cs, "", "")
    # The eval only reads (plus EXPLAIN rows). Autocommit ends every statement's unit of work, so the
    # connection never sits idle inside a transaction while Python/Ollama work runs.
    conn.set_autocommit(True)
    return conn


def q_all(conn, sql: str, params: tuple | list = ()) -> list[tuple]:
    cur = conn.cursor()
    try:
        cur.execute(sql, tuple(params))
        return cur.fetchall()
    finally:
        cur.close()


def db_facts(conn) -> dict:
    f: dict = {}

    def one(key, sql):
        try:
            rows = q_all(conn, sql)
            f[key] = [list(r) for r in rows] if len(rows) != 1 or len(rows[0]) != 1 else rows[0][0]
        except Exception as ex:  # noqa: BLE001
            f[key] = f"ERROR {str(ex)[:200]}"

    one("db2_level", "SELECT SERVICE_LEVEL, BLD_LEVEL FROM SYSIBMADM.ENV_INST_INFO")
    one("session_user", "VALUES SESSION_USER")
    one("adv_doc_visible_rows", "SELECT COUNT(*) FROM NEEDLE.ADV_DOC")
    one("adv_doc_rows_by_kind", "SELECT KIND, COUNT(*) FROM NEEDLE.ADV_DOC GROUP BY KIND ORDER BY KIND")
    one("adv_doc_indexes", "SELECT INDNAME, INDEXTYPE FROM SYSCAT.INDEXES WHERE TABSCHEMA='NEEDLE' AND TABNAME='ADV_DOC' ORDER BY INDNAME")
    one("adv_doc_card_stats", "SELECT CARD, STATS_TIME FROM SYSCAT.TABLES WHERE TABSCHEMA='NEEDLE' AND TABNAME='ADV_DOC'")
    one("rcac_control", "SELECT TABNAME, CONTROL FROM SYSCAT.TABLES WHERE TABSCHEMA='NEEDLE' AND TABNAME IN "
                        "('ADV_DOC','POSTING','ADV_ALIAS','ADV_AFFECTED','TERM_DF','CORPUS_STATS') ORDER BY TABNAME")
    one("embargoed_visible_adv_ids", "SELECT ADV_ID FROM NEEDLE.ADV_DOC WHERE EMBARGO_UNTIL > CURRENT TIMESTAMP "
                                     "ORDER BY ADV_ID")
    try:
        info = conn.server_info()
        f["server_info"] = [str(x) for x in info]
    except Exception as ex:  # noqa: BLE001
        f["server_info"] = f"ERROR {str(ex)[:200]}"
    one("bm25_tables", "SELECT TABNAME, CARD FROM SYSCAT.TABLES WHERE TABSCHEMA='NEEDLE' AND TABNAME IN ('POSTING','TERM_DF','CORPUS_STATS') ORDER BY TABNAME")
    one("triage_proc", "SELECT PROCNAME FROM SYSCAT.PROCEDURES WHERE PROCSCHEMA='NEEDLE' AND PROCNAME='TRIAGE'")
    if isinstance(f.get("rcac_control"), list):
        f["rcac_active"] = {str(t).strip(): ("R" in str(c) or "B" in str(c)) for t, c in f["rcac_control"]}
    e = f.get("embargoed_visible_adv_ids")
    if isinstance(e, list):
        f["embargoed_visible_adv_ids"] = [str(r[0]).strip() for r in e]
    elif isinstance(e, str) and not e.startswith("ERROR"):
        f["embargoed_visible_adv_ids"] = [e.strip()]
    for k in ("adv_doc_card_stats",):
        if isinstance(f.get(k), list):
            f[k] = [[str(x) for x in r] for r in f[k]]
    return f


def explain(conn, sql: str, tag: str) -> dict:
    """EXPLAIN one statement (parameter markers kept, as executed) and summarise the plan."""
    import ibm_db

    out: dict = {"statement": sql, "querytag": tag}
    try:
        cur = conn.cursor()
        try:
            cur.execute(f"EXPLAIN PLAN SET QUERYTAG = '{tag}' FOR {sql}")
        finally:
            cur.close()
        rows = q_all(conn, "SELECT EXPLAIN_TIME, SOURCE_NAME FROM EXPLAIN_STATEMENT WHERE QUERYTAG = ? "
                           "AND EXPLAIN_LEVEL = 'P' ORDER BY EXPLAIN_TIME DESC FETCH FIRST 1 ROW ONLY", (tag,))
        if not rows:
            out["error"] = "no EXPLAIN_STATEMENT row"
            return out
        et, src = rows[0]
        ops = q_all(conn, "SELECT OPERATOR_ID, OPERATOR_TYPE, TOTAL_COST FROM EXPLAIN_OPERATOR "
                          "WHERE EXPLAIN_TIME = ? AND SOURCE_NAME = ? ORDER BY OPERATOR_ID", (et, src))
        objs = q_all(conn, "SELECT DISTINCT OBJECT_SCHEMA, OBJECT_NAME, OBJECT_TYPE FROM EXPLAIN_OBJECT "
                           "WHERE EXPLAIN_TIME = ? AND SOURCE_NAME = ? ORDER BY 1, 2", (et, src))
        out["explain_time"] = str(et)
        out["operators"] = [[int(a), str(b).strip(), float(c)] for a, b, c in ops]
        out["objects"] = [[str(a).strip(), str(b).strip(), str(c).strip()] for a, b, c in objs]
        out["vector_index_in_plan"] = any(o[1] == "ADV_DOC_VIX" for o in out["objects"])
    except Exception as ex:  # noqa: BLE001
        out["error"] = str(ex)[:400]
    _ = ibm_db  # imported to fail loudly if the driver is missing
    return out


# ================================================================================================
# Retrievers: search(q, vec) -> list[adv_id]
# ================================================================================================
class Retriever:
    name = "?"
    needs_vec = True
    last_meta = None  # optional per-query info (e.g. the TRIAGE depth that answered)

    def search(self, q: dict, vec: list[float]) -> list[str]:  # pragma: no cover - interface
        raise NotImplementedError


class VectorLeg(Retriever):
    def __init__(self, conn, name, mode, k=K, bucket_lt=None):
        self.conn, self.name, self.sql = conn, name, vector_sql(mode, k, bucket_lt)

    def search(self, q, vec):
        return [str(r[0]) for r in q_all(self.conn, self.sql, (vec_text(vec),))]


class Bm25Leg(Retriever):
    """Keyword-only BM25 in SQL: NEEDLE.TRIAGE_MODE(mode 'KW') = NEEDLE.BM25_SEARCH, via needle.triage.
    depth=None: the depth the RCAC router picks for the session user (shipped configuration)."""

    needs_vec = False

    def __init__(self, conn, k=K, depth=None):
        from needle.triage import call_triage_ex

        self.conn, self.name, self.k = conn, "bm25", k
        self.depth = None if depth is None else max(k, int(depth))
        self.call = call_triage_ex

    def search(self, q, vec):
        terms = query_terms(q["query"])
        if not terms:
            self.last_meta = {"depth": None, "terms": 0}
            return []
        hits, answered, _ = self.call(self.conn, None, terms, k=self.k, depth=self.depth, mode="KW")
        self.last_meta = {"depth": answered}
        return [h.adv_id for h in hits]


class RrfClient(Retriever):
    """Python-side RRF of the KW leg and an APPROX leg at the same depth: parity check for TRIAGE."""

    name = "rrf_client"

    def __init__(self, conn):
        self.kw = Bm25Leg(conn, RRF_DEPTH, RRF_DEPTH)  # explicit depth: parity check, not the router
        self.vec = VectorLeg(conn, "approx_depth", "APPROX", RRF_DEPTH)

    def search(self, q, vec):
        return rrf_fuse([self.kw.search(q, vec), self.vec.search(q, vec)], RRF_K, K)


class TriageProc(Retriever):
    """Hybrid: NEEDLE.TRIAGE_MODE(mode 'HYBRID') = NEEDLE.TRIAGE, via needle.triage.call_triage_ex.
    depth=None: chosen per session user by the RCAC router (needle.triage.choose_depth)."""

    name = "triage"

    def __init__(self, conn, depth=None):
        from needle.triage import call_triage_ex

        self.conn, self.call, self.depth = conn, call_triage_ex, depth
        self.choice = None
        self.via = (f"needle.triage.call_triage_ex(mode='HYBRID', k={K}, "
                    f"depth={'None -> RCAC router' if depth is None else depth})")

    def search(self, q, vec):
        terms = query_terms(q["query"])
        hits, answered, choice = self.call(self.conn, vec, terms, k=K, depth=self.depth, mode="HYBRID")
        if self.choice is None:
            from dataclasses import asdict

            self.choice = asdict(choice)
        self.last_meta = {"depth": answered}
        return [h.adv_id for h in hits][:K]


class Db2vsBaseline(Retriever):
    name = "db2vs"

    def __init__(self, conn, url, model, qvecs: dict[str, list[float]], queries: list[dict]):
        from langchain_community.vectorstores.utils import DistanceStrategy
        from langchain_core.embeddings import Embeddings
        from langchain_db2.db2vs import DB2VS

        from needle.embed import DOC_PREFIX, QUERY_PREFIX, embed_batch

        by_text = {q["query"]: qvecs[q["qid"]] for q in queries}

        class PrefixedOllama(Embeddings):
            """Query vectors identical to the other legs (precomputed); docs go to Ollama."""

            def embed_documents(self, texts):
                import requests

                with requests.Session() as s:
                    return embed_batch(s, url, model, [DOC_PREFIX + t for t in texts])

            def embed_query(self, text):
                return by_text[text] if text in by_text else self.embed_documents([text])[0]

        # The eval never copies the corpus (one 26k-row INSERT ... SELECT filled the transaction log on
        # 2026-11-10). The table is owned and filled by the connector-findings agent; use it only when full.
        n_vs = q_all(conn, f"SELECT COUNT(*) FROM {DB2VS_TABLE}")[0][0]
        n_doc = q_all(conn, "SELECT COUNT(*) FROM NEEDLE.ADV_DOC")[0][0]
        if int(n_vs) != int(n_doc):
            raise RuntimeError(f"{DB2VS_TABLE} has {n_vs} rows, NEEDLE.ADV_DOC has {n_doc}: baseline table not "
                               "filled (owned by the connector-findings agent; the eval does not copy data)")
        self.setup = {"table": DB2VS_TABLE, "rows": int(n_vs), "adv_doc_rows": int(n_doc)}
        self.conn = conn
        self.vs = DB2VS(embedding_function=PrefixedOllama(), table_name=DB2VS_TABLE, client=conn,
                        distance_strategy=DistanceStrategy.COSINE)

    def search(self, q, vec):
        docs = self.vs.similarity_search(q["query"], k=K)
        return [d.metadata.get("adv_id") for d in docs]


class MockRetriever(Retriever):
    """--mock: deterministic fake results (pipeline test only; numbers are meaningless)."""

    def __init__(self, name, all_ids):
        self.name, self.ids = name, all_ids

    def search(self, q, vec):
        h = int(hashlib.sha256((self.name + q["qid"]).encode()).hexdigest(), 16)
        out = [self.ids[(h >> (8 * i)) % len(self.ids)] for i in range(K)]
        if h % 3 == 0:
            out[h % K] = q["gt"][0]
        return out


# ================================================================================================
# Charts (dataviz skill: reference palette, validated light + dark; identity also on the axis)
# ================================================================================================
THEMES = {
    "light": {"surface": "#fcfcfb", "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781",
              "grid": "#e1e0d9", "axis": "#c3c2b7",
              "series": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]},
    "dark": {"surface": "#1a1a19", "ink": "#f0efec", "ink2": "#c3c2b7", "muted": "#898781",
             "grid": "#2c2c2a", "axis": "#383835",
             "series": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300"]},
}
LABELS = {"triage": "Hybrid TRIAGE (in Db2)", "bm25": "BM25 keyword (SQL)", "exact": "Vector EXACT",
          "approx": "Vector APPROX", "rrf_client": "RRF in Python (check)", "db2vs": "langchain-db2 DB2VS"}


def _style_axis(ax, th):
    ax.set_facecolor(th["surface"])
    ax.xaxis.grid(True, color=th["grid"], linewidth=0.8)
    ax.set_axisbelow(True)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color(th["axis"])
    ax.tick_params(colors=th["ink2"], labelsize=9, length=0)


def plot_recall(summary: dict, caption: str, out: Path, theme: str, stamp: str = "", metric: str = "recall@10") -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    th = THEMES[theme]
    rets = [r for r in CHART_RETRIEVERS if r in summary]
    slices = [s for s in SLICES if any(s in summary[r] for r in rets)]
    fig, axes = plt.subplots(1, len(slices), figsize=(4.4 * len(slices), 0.55 * len(rets) + 2.4),
                             sharey=True, facecolor=th["surface"])
    axes = [axes] if len(slices) == 1 else list(axes)
    for ax, s in zip(axes, slices):
        _style_axis(ax, th)
        for i, r in enumerate(rets):
            v = (summary[r].get(s) or {}).get(metric)
            y = len(rets) - 1 - i
            if v is None:
                ax.text(0.01, y, "not run", va="center", ha="left", color=th["muted"], fontsize=9)
                continue
            ax.barh(y, v, height=0.62, color=th["series"][CHART_RETRIEVERS.index(r)],
                    edgecolor=th["surface"], linewidth=2)
            ax.text(v + 0.015, y, f"{v:.2f}", va="center", ha="left", color=th["ink"], fontsize=9)
        n = next((summary[r][s]["n"] for r in rets if s in summary[r]), 0)
        ax.set_title(f"{s} (n={n})", color=th["ink"], fontsize=11, loc="left")
        ax.set_xlim(0, 1.13)
        ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
        ax.set_xlabel(f"{metric.capitalize()} (share of queries)", color=th["ink2"], fontsize=9)
    axes[0].set_yticks(range(len(rets)))
    axes[0].set_yticklabels([LABELS.get(r, r) for r in reversed(rets)], color=th["ink"], fontsize=9)
    fig.suptitle(f"Relevance: {metric} per retriever on each frozen query slice" + stamp,
                 color=th["ink"], fontsize=12, x=0.01, ha="left")
    fig.text(0.01, 0.01, caption, color=th["muted"], fontsize=7, ha="left", va="bottom", linespacing=1.4)
    fig.tight_layout(rect=(0, 0.09, 1, 0.95))
    fig.savefig(out, dpi=150, facecolor=th["surface"])
    plt.close(fig)


def plot_latency(summary_all: dict, caption: str, out: Path, theme: str, stamp: str = "", where: str = "") -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    th = THEMES[theme]
    rets = [r for r in CHART_RETRIEVERS if r in summary_all and summary_all[r].get("latency_p50_ms") is not None]
    if not rets:
        return
    xmax = max(summary_all[r]["latency_p95_ms"] for r in rets)
    fig, ax = plt.subplots(figsize=(11.0, 0.5 * len(rets) + 2.0), facecolor=th["surface"])
    _style_axis(ax, th)
    for i, r in enumerate(rets):
        y = len(rets) - 1 - i
        p50, p95 = summary_all[r]["latency_p50_ms"], summary_all[r]["latency_p95_ms"]
        c = th["series"][CHART_RETRIEVERS.index(r)]
        ax.plot([p50, p95], [y, y], color=c, linewidth=2, solid_capstyle="round")
        ax.plot([p50], [y], "o", color=c, markersize=8, markeredgecolor=th["surface"], markeredgewidth=2)
        ax.plot([p95], [y], "o", color=th["surface"], markersize=8, markeredgecolor=c, markeredgewidth=2)
        ax.text(p95 + xmax * 0.02, y, f"p50 {p50:.1f} / p95 {p95:.1f} ms", color=th["ink2"], fontsize=8,
                ha="left", va="center")
    ax.set_yticks(range(len(rets)))
    ax.set_yticklabels([LABELS.get(r, r) for r in reversed(rets)], color=th["ink"], fontsize=9)
    ax.set_xlim(0, xmax * 1.35)
    ax.set_ylim(-0.6, len(rets) - 0.4)
    ax.set_xlabel("Retrieval latency per query (ms); filled dot = p50, ring = p95", color=th["ink2"], fontsize=9)
    fig.suptitle(f"Latency: one retrieval call, client {where or '?'}, query embedding excluded" + stamp,
                 color=th["ink"], fontsize=11, x=0.01, ha="left")
    fig.text(0.01, 0.01, caption, color=th["muted"], fontsize=7, ha="left", va="bottom", linespacing=1.4)
    fig.tight_layout(rect=(0, 0.11, 1, 0.94))
    fig.savefig(out, dpi=150, facecolor=th["surface"])
    plt.close(fig)


# ================================================================================================
# Saved query vectors (embed on the PC, run SQL legs elsewhere) and chart re-rendering
# ================================================================================================
def _qhash(q: dict) -> str:
    return hashlib.sha256(q["query"].encode("utf-8")).hexdigest()


def save_qvecs(path: Path, queries, qvecs, lat, info: dict, qsets: dict) -> None:
    import gzip

    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"embedding": info, "query_sets": {s: v["sha256"] for s, v in qsets.items()},
            "latency_ms": dict(zip([q["qid"] for q in queries], [round(x, 2) for x in lat])),
            "query_sha256": {q["qid"]: _qhash(q) for q in queries},
            "vectors": {q["qid"]: qvecs[q["qid"]] for q in queries}}
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(body, f, separators=(",", ":"))


def load_qvecs(path: Path, queries) -> tuple[dict, list[float], dict]:
    import gzip

    with gzip.open(path, "rt", encoding="utf-8") as f:
        body = json.load(f)
    missing = [q["qid"] for q in queries if q["qid"] not in body["vectors"]]
    changed = [q["qid"] for q in queries if body["query_sha256"].get(q["qid"]) != _qhash(q)]
    if missing or changed:
        raise SystemExit(f"SETUP ERROR: saved vectors do not match the queries (missing={len(missing)}, "
                         f"changed={len(changed)})")
    info = dict(body["embedding"], vectors_file=path.name, vectors_file_sha256=sha256_file(path),
                note="query vectors embedded on the PC (Ollama) and loaded from file")
    return ({q["qid"]: body["vectors"][q["qid"]] for q in queries},
            [body["latency_ms"][q["qid"]] for q in queries], info)


WHERE_TEXT = {"codespace-localhost": "inside the codespace over localhost:50000",
              "pc-tunnel": "on the PC through a tunnel to the codespace (network round trip included)"}


def render_charts(res: dict) -> list[Path]:
    rel = {r: v for r, v in res["relevance"].items() if r in CHART_RETRIEVERS}
    if not rel:
        return []
    qs, run_id = res["query_sets"], res["run_id"]
    where = (res.get("client") or {}).get("where", "?")
    nps = ", ".join(f"{s}={v['n_used']}" for s, v in qs.items())
    digest = str(res["embedding"].get("digest") or "")[:12]
    db = res.get("db") or {}
    rcac = db.get("rcac_active") or {}
    who = f"user {str(db.get('session_user') or '?').strip()}" + (" | RCAC active" if rcac.get("ADV_DOC") else "")
    line1 = (f"run {run_id}{' (canonical)' if res.get('canonical') else ''} | {who} | k={res['k']} | n/slice {nps} | "
             f"embed {res['embedding'].get('model')} {digest} | client {where}")
    line2 = ("queries sha256 " + " ".join(f"{s}:{v['sha256'][:12]}" for s, v in qs.items())
             + f" | docs sha256 {res['dataset']['sha256'][:12]}")
    partial = bool(res.get("mock") or res.get("smoke_limit"))
    stamp = "  [MOCK DATA, NOT A MEASUREMENT]" if res.get("mock") else ("  [SMOKE RUN, PARTIAL]" if partial else "")
    pre = f"{run_id}_" if partial else ""
    out = []
    for metric, stem in (("recall@10", "recall_by_slice"), ("recall@1", "recall_at1_by_slice")):
        for theme, suf in (("light", ""), ("dark", "_dark")):
            p = RDIR / f"{pre}{stem}{suf}.png"
            plot_recall(rel, f"{line1} | relevance vs canon_id ground truth" + chr(10) + line2, p, theme, stamp, metric)
            out.append(p)
    lat = {r: v["all"] for r, v in rel.items()}
    for theme, suf in (("light", ""), ("dark", "_dark")):
        p = RDIR / f"{pre}latency_by_retriever{suf}.png"
        plot_latency(lat, f"{line1} | latency, warm-up excluded" + chr(10) + line2, p, theme, stamp,
                     WHERE_TEXT.get(where, where))
        out.append(p)
    return out


def charts_from(path: Path) -> int:
    for p in render_charts(json.loads(path.read_text(encoding="utf-8"))):
        print(f"wrote {p}")
    return 0


# ================================================================================================
# Main
# ================================================================================================
def load_bucket_map() -> dict[str, int]:
    m = {}
    with open(DOCS, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            m[d["adv_id"]] = d["row_bucket"]
    return m


def run_retriever(ret: Retriever, queries: list[dict], qvecs: dict, bucket_lt: int | None) -> list[dict]:
    for q in queries[:WARMUP]:
        try:
            ret.search(q, qvecs.get(q["qid"]))
        except Exception:  # noqa: BLE001 - errors are recorded in the measured loop
            pass
    rows = []
    for q in queries:
        gt = q["gt"]
        if bucket_lt is not None and not (q.get("row_bucket") is not None and q["row_bucket"] < bucket_lt):
            gt = []  # ground truth not visible under the filter: excluded from relevance
        t0 = time.perf_counter()
        err = None
        try:
            ranked = ret.search(q, qvecs.get(q["qid"]))
        except Exception as ex:  # noqa: BLE001
            ranked, err = [], f"{type(ex).__name__}: {str(ex)[:300]}"
        ms = (time.perf_counter() - t0) * 1000
        row = {"qid": q["qid"], "slice": q["slice"], "ranked": ranked, "gt": gt,
               "first_hit_rank": first_hit_rank(ranked, gt) if gt else None,
               "latency_ms": round(ms, 2), "error": err}
        if getattr(ret, "last_meta", None) is not None:
            row["meta"] = ret.last_meta
            ret.last_meta = None
        rows.append(row)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="NEEDLE retrieval evaluation")
    ap.add_argument("--slices", default=",".join(SLICES))
    ap.add_argument("--retrievers", default="triage,bm25,exact,approx,rrf_client,exact_b50,approx_b50",
                    help="db2vs is opt-in: it needs the connector-findings agent's filled NDL_DEV_EVAL.DB2VS_ADV")
    ap.add_argument("--limit", type=int, default=0, help="first N queries per slice (smoke run; flagged)")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--gate-retriever", default=GATE_RETRIEVER)
    ap.add_argument("--gate-min", type=float, default=GATE_MIN)
    ap.add_argument("--no-gate", action="store_true")
    ap.add_argument("--mock", action="store_true", help="no DB, fake retrievers (pipeline test only)")
    ap.add_argument("--note", default="")
    ap.add_argument("--triage-depth", type=int, default=None,
                    help="TRIAGE/KW depth; default None = chosen per session user by the RCAC router")
    ap.add_argument("--canonical", action="store_true", help="mark this run as the canonical result")
    ap.add_argument("--supersedes", default="", help="comma-separated run ids this run supersedes")
    ap.add_argument("--embed-only", action="store_true", help="embed the queries, write --qvecs-out, exit")
    ap.add_argument("--qvecs-out", default=None, help="write query vectors (json.gz) for a later --qvecs-in run")
    ap.add_argument("--qvecs-in", default=None, help="use saved query vectors instead of calling Ollama")
    ap.add_argument("--where", default=None, help="label for where the client ran (default: hostname)")
    ap.add_argument("--no-charts", action="store_true")
    ap.add_argument("--charts-from", default=None, help="only re-render the charts from a saved results JSON")
    args = ap.parse_args()

    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except ImportError:  # inside the codespace: settings come from the environment
        pass
    if args.charts_from:
        return charts_from(Path(args.charts_from))
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    model = os.environ.get("EMBED_MODEL", "nomic-embed-text")
    slices = [s for s in args.slices.split(",") if s]
    wanted = [r for r in args.retrievers.split(",") if r]
    for r in wanted:
        if r not in ALL_RETRIEVERS:
            raise SystemExit(f"unknown retriever {r}; choose from {ALL_RETRIEVERS}")
    started = dt.datetime.now(dt.timezone.utc)
    run_id = args.run_id or (("mock-" if args.mock else "") + started.strftime("%Y%m%dT%H%M%SZ"))

    # ---- queries + provenance
    queries, qsets = [], {}
    for s in slices:
        recs, digest, man = load_slice(s)
        if args.limit:
            recs = recs[: args.limit]
        queries.extend(recs)
        qsets[s] = {"file": f"eval/queries/{s}.jsonl", "sha256": digest, "n_used": len(recs),
                    "n_frozen": man.get("count"), "synthetic": man.get("synthetic"),
                    "built_from_docs_sha256": man.get("docs_sha256")}
    docs_sha = sha256_file(DOCS)
    stale = sorted({v["built_from_docs_sha256"] for v in qsets.values()} - {docs_sha})
    if stale:
        print(f"WARNING: docs.jsonl sha256 {docs_sha} differs from the one the slices were built from {stale}")
    print(f"run {run_id}: {len(queries)} queries, slices={slices}, retrievers={wanted}", flush=True)

    result: dict = {
        "run_id": run_id, "started_utc": started.isoformat(timespec="seconds"), "mock": args.mock,
        "smoke_limit": args.limit or None, "note": args.note, "k": K,
        "code_sha256": {"eval/run_eval.py": sha256_file(Path(__file__).resolve())},
        "metric_families": {
            "relevance": "recall@k = share of queries with >=1 gt adv_id (same canon_id) in top k; "
                         "mrr@10; set_recall@10 = mean share of the gt set in top 10",
            "ann_fidelity": "overlap@10 = |APPROX top10 ∩ EXACT top10| / |EXACT top10|, same vector and filter",
        },
        "query_sets": qsets, "dataset": {"file": "data/docs.jsonl", "sha256": docs_sha,
                                         "slices_built_from_same_docs": not stale},
        "embedding": {"model": model, "prefix": "search_query: "},
        "client": {"python": platform.python_version(), "platform": platform.platform(),
                   "where": args.where or socket.gethostname(), "db2_host": os.environ.get("DB2_HOST"),
                   "db2_port": os.environ.get("DB2_PORT")},
        "config": {"rrf_k": RRF_K, "rrf_depth": RRF_DEPTH, "triage_depth": TRIAGE_DEPTH,
                   "bm25": "needle.bm25 analyzer + NEEDLE.BM25_SEARCH (k1=1.2, b=0.75, rank_bm25 idf, <=64 terms)",
                   "filter_bucket_lt": FILTER_BUCKET_LT,
                   "warmup_calls": WARMUP},
        "gate": {"retriever": args.gate_retriever, "slice": GATE_SLICE, "metric": GATE_METRIC,
                 "min": args.gate_min},
    }

    # ---- embeddings
    if args.mock:
        qvecs, elat = {q["qid"]: [0.0] * 768 for q in queries}, []
    elif args.qvecs_in:
        qvecs, elat, info = load_qvecs(Path(args.qvecs_in), queries)
        result["embedding"].update(info)
        print(f"loaded {len(qvecs)} query vectors from {args.qvecs_in}", flush=True)
    else:
        result["embedding"].update(ollama_model_info(url, model))
        t0 = time.time()
        qvecs, elat = embed_queries(queries, url, model)
        print(f"embedded {len(qvecs)} queries in {time.time()-t0:.1f}s", flush=True)
        if args.qvecs_out or args.embed_only:
            outp = Path(args.qvecs_out or (ROOT / "data" / "eval_qvecs.json.gz"))
            save_qvecs(outp, queries, qvecs, elat, result["embedding"], qsets)
            print(f"wrote {outp}", flush=True)
        if args.embed_only:
            return 0
    result["embedding"]["latency_p50_ms"] = _r1(percentile(elat, 50))
    result["embedding"]["latency_p95_ms"] = _r1(percentile(elat, 95))

    # ---- retrievers
    conn = None
    rows_by_ret: dict[str, list[dict]] = {}
    result["retrievers"] = {}
    try:
        if args.mock:
            ids = sorted({a for q in queries for a in q["gt"]})
            rets = {r: MockRetriever(r, ids) for r in wanted}
            result["db"] = {"mock": True}
        else:
            try:
                conn = connect()
            except Exception as ex:  # noqa: BLE001
                print(f"SETUP ERROR: cannot connect to Db2: {str(ex)[:300]}")
                return 2
            result["db"] = db_facts(conn)
            print("db facts:", json.dumps(result["db"], default=str)[:600], flush=True)
            result["explain"] = {
                "exact": explain(conn, vector_sql("EXACT", K), EXPLAIN_TAG + "EX"),
                "approx": explain(conn, vector_sql("APPROX", K), EXPLAIN_TAG + "AP"),
                "approx_b50": explain(conn, vector_sql("APPROX", K, FILTER_BUCKET_LT), EXPLAIN_TAG + "AF"),
                f"approx_depth{RRF_DEPTH}": explain(conn, vector_sql("APPROX", RRF_DEPTH), EXPLAIN_TAG + "AD"),
            }
            if all("error" in v for v in result["explain"].values()) and os.environ.get("DB2_ADMIN_USER") \
                    and os.environ.get("DB2_ADMIN_PASSWORD"):
                first_err = next(iter(result["explain"].values()))["error"]
                adm = connect(os.environ["DB2_ADMIN_USER"], os.environ["DB2_ADMIN_PASSWORD"])
                try:
                    result["explain"] = {
                        "exact": explain(adm, vector_sql("EXACT", K), EXPLAIN_TAG + "EX"),
                        "approx": explain(adm, vector_sql("APPROX", K), EXPLAIN_TAG + "AP"),
                    }
                finally:
                    adm.close()
                result["explain_note"] = (f"EXPLAIN as the eval user failed ({first_err[:160]}); explained as "
                                          f"{os.environ['DB2_ADMIN_USER']} (same statement text; the RCAC row "
                                          f"permission applies to every user, so the plan carries the same predicate)")
            for k_, v in result["explain"].items():
                print(f"EXPLAIN {k_}: vector_index_in_plan={v.get('vector_index_in_plan')} "
                      f"ops={[o[1] for o in v.get('operators', [])]} err={v.get('error')}", flush=True)
            rets = {}
            for r in wanted:
                try:
                    if r == "bm25":
                        rets[r] = Bm25Leg(conn, K, args.triage_depth)
                    elif r == "exact":
                        rets[r] = VectorLeg(conn, r, "EXACT")
                    elif r == "approx":
                        rets[r] = VectorLeg(conn, r, "APPROX")
                    elif r == "exact_b50":
                        rets[r] = VectorLeg(conn, r, "EXACT", K, FILTER_BUCKET_LT)
                    elif r == "approx_b50":
                        rets[r] = VectorLeg(conn, r, "APPROX", K, FILTER_BUCKET_LT)
                    elif r == "rrf_client":
                        rets[r] = RrfClient(conn)
                    elif r == "triage":
                        rets[r] = TriageProc(conn, args.triage_depth)
                    elif r == "db2vs":
                        rets[r] = Db2vsBaseline(conn, url, model, qvecs, queries)
                except Exception as ex:  # noqa: BLE001
                    result["retrievers"][r] = {"status": "unavailable", "reason": f"{type(ex).__name__}: {str(ex)[:300]}"}
                    print(f"retriever {r} unavailable: {str(ex)[:200]}", flush=True)

        for r, ret in rets.items():
            # probe: skip a retriever whose first query fails (missing table/procedure)
            if not args.mock:
                try:
                    ret.search(queries[0], qvecs[queries[0]["qid"]])
                except Exception as ex:  # noqa: BLE001
                    result["retrievers"][r] = {"status": "unavailable", "reason": f"{type(ex).__name__}: {str(ex)[:300]}"}
                    print(f"retriever {r} unavailable: {str(ex)[:200]}", flush=True)
                    continue
            t0 = time.time()
            bl = FILTER_BUCKET_LT if r.endswith("_b50") else None
            rows_by_ret[r] = run_retriever(ret, queries, qvecs, bl)
            info = {"status": "ok", "seconds": round(time.time() - t0, 1)}
            if isinstance(ret, TriageProc):
                info["via"] = ret.via
            if isinstance(ret, Db2vsBaseline):
                info["setup"] = ret.setup
                info["note"] = ("DB2VS inlines the query vector into the SQL text, runs exact FETCH FIRST k, "
                                "and calls embed_documents once per search for its dimension check "
                                "(one extra Ollama call inside the measured latency).")
            result["retrievers"][r] = info
            print(f"{r}: {len(rows_by_ret[r])} queries in {info['seconds']}s", flush=True)
    finally:
        if conn is not None:
            conn.close()

    # ---- summaries
    bucket_of = load_bucket_map() if any(r.endswith("_b50") for r in rows_by_ret) else {}
    rel: dict = {}
    for r, rows in rows_by_ret.items():
        rel[r] = {"all": summarize_relevance(rows)}
        for s in slices:
            rel[r][s] = summarize_relevance([x for x in rows if x["slice"] == s])
        if r.endswith("_b50"):
            viol = sum(1 for x in rows for a in x["ranked"] if bucket_of.get(a, 999) >= FILTER_BUCKET_LT)
            rel[r]["filter_check"] = {"predicate": f"ROW_BUCKET < {FILTER_BUCKET_LT}",
                                      "returned_rows": sum(len(x["ranked"]) for x in rows),
                                      "rows_violating_filter": viol}
    result["relevance"] = rel

    fid: dict = {}
    for a_name, e_name in (("approx", "exact"), ("approx_b50", "exact_b50")):
        if a_name in rows_by_ret and e_name in rows_by_ret:
            e_by = {x["qid"]: x["ranked"] for x in rows_by_ret[e_name]}
            per = [(x["slice"], overlap_at(x["ranked"], e_by.get(x["qid"], [])), x["ranked"] == e_by.get(x["qid"]))
                   for x in rows_by_ret[a_name]]
            block = {}
            for s in ["all", *slices]:
                vals = [o for sl, o, _ in per if o is not None and (s == "all" or sl == s)]
                same = [eq for sl, _, eq in per if s == "all" or sl == s]
                block[s] = {"n": len(vals), "overlap@10_mean": round(sum(vals) / len(vals), 4) if vals else None,
                            "overlap@10_min": round(min(vals), 4) if vals else None,
                            "identical_lists_share": round(sum(same) / len(same), 4) if same else None}
            fid[f"{a_name}_vs_{e_name}"] = block
    result["ann_fidelity"] = fid

    router: dict = {}
    if isinstance(rets.get("triage"), TriageProc) and rets["triage"].choice is not None:
        router["triage_choice"] = rets["triage"].choice
    for r in ("triage", "bm25"):
        if r in rows_by_ret:
            hist: dict = {}
            for x in rows_by_ret[r]:
                d = (x.get("meta") or {}).get("depth")
                hist[str(d)] = hist.get(str(d), 0) + 1
            router[f"{r}_answered_depth_counts"] = hist
    result["router"] = router

    emb = (result.get("db") or {}).get("embargoed_visible_adv_ids")
    if isinstance(emb, list):
        es = set(emb)
        hit = [q["qid"] for q in queries if es & set(q["gt"])]
        only = [q["qid"] for q in queries if q["gt"] and set(q["gt"]) <= es]
        result["embargo"] = {"embargoed_rows_visible_to_session_user": len(es),
                             "queries_with_embargoed_gt": len(hit), "queries_with_only_embargoed_gt": len(only),
                             "qids": hit}
    result["canonical"] = bool(args.canonical)
    result["supersedes"] = [x for x in args.supersedes.split(",") if x]
    result["per_query"] = {r: rows for r, rows in rows_by_ret.items()}

    # ---- gate
    g = rel.get(args.gate_retriever, {}).get(GATE_SLICE, {}).get(GATE_METRIC)
    if g is None:
        status, code = "not_evaluated", (0 if args.no_gate else 3)
    elif g < args.gate_min:
        status, code = "failed", (0 if args.no_gate else 1)
    else:
        status, code = "passed", 0
    result["gate"].update({"value": g, "status": status, "enforced": not args.no_gate})
    result["finished_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    RDIR.mkdir(parents=True, exist_ok=True)
    out = RDIR / f"{run_id}.json"
    out.write_text(json.dumps(result, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")

    # ---- charts (mock/smoke runs get run-id-prefixed file names and a stamp in the title)
    if not args.no_charts:
        for p in render_charts(result):
            print(f"wrote {p}")

    # ---- console tables
    print(f"\nRELEVANCE (canon_id ground truth), run {run_id}")
    print(f"{'retriever':<12}{'slice':<11}{'n':>4}{'R@1':>7}{'R@3':>7}{'R@10':>7}{'MRR':>7}{'p50ms':>8}{'p95ms':>8}{'err':>5}")
    for r, v in rel.items():
        for s in slices:
            m = v[s]
            print(f"{r:<12}{s:<11}{m['n']:>4}{_f(m['recall@1'])}{_f(m['recall@3'])}{_f(m['recall@10'])}"
                  f"{_f(m['mrr@10'])}{_f(m['latency_p50_ms'], 8, 1)}{_f(m['latency_p95_ms'], 8, 1)}{m['errors']:>5}")
        if "filter_check" in v:
            print(f"{'':<12}filter check: {v['filter_check']}")
    if fid:
        print("\nANN FIDELITY (APPROX vs EXACT, same vector)")
        for name, block in fid.items():
            for s, m in block.items():
                print(f"{name:<24}{s:<11} n={m['n']:>4} overlap@10={m['overlap@10_mean']} "
                      f"min={m['overlap@10_min']} identical={m['identical_lists_share']}")
    for r, v in result["retrievers"].items():
        if v.get("status") != "ok":
            print(f"SKIPPED {r}: {v.get('reason')}")
    print(f"\ngate: {args.gate_retriever} {GATE_SLICE} {GATE_METRIC} = {g} (min {args.gate_min}) -> {status}"
          f"{' (not enforced)' if args.no_gate else ''}")
    print(f"wrote {out}")
    return code


def _f(x, w=7, nd=3):
    return f"{'-':>{w}}" if x is None else f"{x:>{w}.{nd}f}"


if __name__ == "__main__":
    sys.exit(main())
