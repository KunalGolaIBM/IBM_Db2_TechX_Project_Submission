"""BM25 parity: needle.bm25 reference scorer and the SQL keyword leg (NEEDLE.BM25_SEARCH) vs rank_bm25.

The SQL implements rank_bm25.BM25Okapi exactly (k1=1.2, b=0.75, epsilon=0.25), including its IDF variant:
    idf = ln(N - df + 0.5) - ln(df + 0.5); negative idf -> epsilon * mean(raw idf over the vocabulary).
So no IDF formula difference is expected. Two documented conventions:
  * query terms are de-duplicated (rank_bm25 adds a repeated query term twice) -> tests pass distinct terms;
  * the SQL keeps at most 64 query terms (lowest df) -> tests pass the same pruned list to rank_bm25.
Ranking: score DESC, then ADV_ID ASC. Only documents with score > 0 are ranked.

Unit parts run without a DB. The DB part is marked @pytest.mark.db (run: pytest -m db).
"""
import json
import random
import sys
from pathlib import Path

import pytest
from rank_bm25 import BM25Okapi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from needle.bm25 import B, EPSILON, K1, Bm25Index, doc_terms, load_bm25_docs, prune_query_terms, query_terms  # noqa: E402

TOL = 1e-9
DOCS_JSONL = ROOT / "data" / "docs.jsonl"

SMALL = [
    ("GHSA-0001", "PyYAML arbitrary code execution", "PyYAML full_load and FullLoader allow arbitrary code execution "
     "via python/object/new constructor. Upgrade pyyaml to 5.4.", ["pyyaml"], ["CVE-2020-14343"]),
    ("GHSA-0002", "log4j-core JNDI lookup remote code execution", "Apache Log4j2 JNDI features do not protect "
     "against attacker controlled LDAP endpoints. log4j-core 2.15.0 fixes it.", ["log4j-core"], ["CVE-2021-44228"]),
    ("PYSEC-0003", "Django SQL injection in QuerySet.order_by", "Django allows SQL injection via order_by on "
     "column aliases. django.db.models is affected.", ["django"], ["CVE-2021-35042"]),
    ("MAL-0004", "Malicious code in requestz (PyPI)", "The package requestz steals Discord tokens and browser "
     "passwords. Malicious code executes on install.", ["requestz"], []),
    ("MAL-0005", "Malicious code in pyyamll (PyPI)", "Typosquat of pyyaml. Malicious code downloads a remote "
     "payload on install and steals tokens.", ["pyyamll"], []),
    ("GHSA-0006", "Requests leaks Proxy-Authorization header", "Requests forwards the Proxy-Authorization header "
     "to destination servers on HTTPS redirect.", ["requests"], ["CVE-2023-32681"]),
    ("GHSA-0007", "Pillow buffer overflow in TIFF decoder", "Pillow before 8.1.1 has a heap buffer overflow in "
     "the TIFF decoder. Remote attackers cause a crash with a crafted image.", ["pillow"], ["CVE-2021-25289"]),
    ("GHSA-0008", "Jinja2 sandbox escape", "Jinja2 sandbox escape through format_map allows remote code "
     "execution in templates.", ["jinja2"], ["CVE-2019-10906"]),
    ("MAL-0009", "Malicious code in djangoo (PyPI)", "Malicious code steals environment variables. Typosquat "
     "of django.", ["djangoo"], []),
    ("GHSA-0010", "urllib3 Cookie header kept on cross-origin redirect", "urllib3 does not strip the Cookie "
     "header on cross-origin redirects.", ["urllib3"], ["CVE-2023-43804"]),
    ("MAL-0011", "Malicious code in pillow-sdk (PyPI)", "Malicious code steals Discord tokens.", ["pillow-sdk"], []),
    ("GHSA-0012", "Code injection in pyyaml load", "yaml.load without Loader allows code injection in pyyaml "
     "before 5.1.", ["pyyaml"], ["CVE-2017-18342"]),
]

SMALL_QUERIES = [
    "pyyaml remote code execution", "log4j-core cve-2021-44228", "malicious code steals discord tokens",
    "sql injection django order_by", "proxy-authorization header redirect", "heap buffer overflow tiff image",
    "sandbox escape templates", "typosquat pyyaml malicious", "cookie cross-origin redirect urllib3",
    "code", "malicious code", "nothing-matches-here",
]

REAL_QUERIES = [
    "pyyaml full_load arbitrary code execution", "log4j-core jndi lookup", "cve-2021-44228",
    "django sql injection", "malicious package stealing discord tokens", "requests proxy-authorization header leak",
    "pillow heap buffer overflow", "jinja2 sandbox escape", "urllib3 cookie redirect",
    "tensorflow null pointer dereference", "path traversal in zip extraction", "server-side request forgery redirect",
    "denial of service regular expression", "open redirect login", "deserialization pickle remote code execution",
]


def _small_docs():
    return {aid: doc_terms({"adv_id": aid, "aliases": al, "packages": pk, "summary": s, "details": d})
            for aid, s, d, pk, al in SMALL}


def _rank_bm25_top(okapi, ids, terms, k):
    scores = okapi.get_scores(list(terms))
    ranked = sorted(((ids[i], float(s)) for i, s in enumerate(scores) if s > 0), key=lambda x: (-x[1], x[0]))
    return ranked[:k]


def assert_same_ranking(got, exp, k=10):
    """Same top-k: equal scores (TOL) position by position; ids may differ only inside a score tie group."""
    assert len(got) == len(exp), (got, exp)
    for (ga, gs), (ea, es) in zip(got, exp):
        assert abs(gs - es) <= TOL * max(1.0, abs(es)), (ga, gs, ea, es)
    i = 0
    while i < len(exp):  # compare id sets per tie group
        j = i
        while j + 1 < len(exp) and abs(exp[j + 1][1] - exp[i][1]) <= TOL * max(1.0, abs(exp[i][1])):
            j += 1
        if j + 1 < len(exp) or len(exp) < k:
            assert {a for a, _ in got[i:j + 1]} == {a for a, _ in exp[i:j + 1]}, (got[i:j + 1], exp[i:j + 1])
        i = j + 1


def test_small_corpus_matches_rank_bm25():
    docs = _small_docs()
    ids = sorted(docs)
    idx = Bm25Index(docs)
    okapi = BM25Okapi([docs[a] for a in ids], k1=K1, b=B, epsilon=EPSILON)
    assert abs(okapi.avgdl - idx.avgdl) < 1e-12 and abs(okapi.average_idf - idx.avg_idf) < 1e-12
    assert any(v < 0 for v in (idx.avg_idf,)) or any(idx.idf[t] == EPSILON * idx.avg_idf for t in idx.idf), \
        "the small corpus must exercise the epsilon floor (a term with df > N/2)"
    for q in SMALL_QUERIES:
        terms = prune_query_terms(query_terms(q), idx.df)
        assert_same_ranking(idx.top(terms, 10), _rank_bm25_top(okapi, ids, terms, 10))


@pytest.fixture(scope="module")
def real_index():
    if not DOCS_JSONL.exists():
        pytest.skip("data/docs.jsonl not built")
    docs, _ = load_bm25_docs(str(DOCS_JSONL))
    return docs, Bm25Index(docs)


def _real_queries(docs_meta_path=DOCS_JSONL, n_sampled=10, seed=20261109):
    """Hand-written queries + summaries of n_sampled seeded random non-withdrawn advisories."""
    summaries = []
    with open(docs_meta_path, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if not d.get("withdrawn") and d.get("summary"):
                summaries.append((d["adv_id"], d["summary"]))
    rnd = random.Random(seed)
    return REAL_QUERIES + [s for _, s in rnd.sample(summaries, n_sampled)]


def test_real_corpus_matches_rank_bm25(real_index):
    docs, idx = real_index
    ids = sorted(docs)
    okapi = BM25Okapi([docs[a] for a in ids], k1=K1, b=B, epsilon=EPSILON)
    assert abs(okapi.avgdl - idx.avgdl) < 1e-9 and abs(okapi.average_idf - idx.avg_idf) < 1e-9
    for q in _real_queries():
        terms = prune_query_terms(query_terms(q), idx.df)
        assert_same_ranking(idx.top(terms, 10), _rank_bm25_top(okapi, ids, terms, 10))


PUBLIC = "(EMBARGO_UNTIL IS NULL OR EMBARGO_UNTIL <= CURRENT TIMESTAMP)"


@pytest.mark.db
def test_sql_bm25_matches_rank_bm25(real_index):
    """SQL keyword leg vs rank_bm25 over the PUBLIC corpus.

    NEEDLE.TERM_DF / CORPUS_STATS are public-only statistics (review C1 fix), so the reference corpus excludes the
    advisories under an active embargo, and the SQL runs as NDL_JUNIOR (MAX_BUCKET 100, SEES_EMBARGO 0: sees exactly
    the public rows; EXECUTE on BM25_SEARCH only, no SELECT on the statistics tables)."""
    import os

    from needle.triage import connect

    pw = os.environ.get("NDL_JUNIOR_PASSWORD")
    if not pw:
        from dotenv import dotenv_values
        pw = dotenv_values(ROOT / ".env").get("NDL_JUNIOR_PASSWORD")
    if not pw:
        pytest.skip("NDL_JUNIOR_PASSWORD not set")
    all_docs, _ = real_index
    admin = connect()
    try:
        cur = admin.cursor()
        try:
            cur.execute(f"SELECT ADV_ID FROM NEEDLE.ADV_DOC WHERE NOT {PUBLIC}")
            embargoed = {str(r[0]).strip() for r in cur.fetchall()}
            cur.execute("SELECT N, AVGDL, AVG_IDF FROM NEEDLE.CORPUS_STATS WHERE ID = 1")
            n, avgdl, avg_idf = cur.fetchone()
        finally:
            cur.close()
    finally:
        admin.close()
    docs = {a: t for a, t in all_docs.items() if a not in embargoed}
    idx = Bm25Index(docs)
    ids = sorted(docs)
    okapi = BM25Okapi([docs[a] for a in ids], k1=K1, b=B, epsilon=EPSILON)
    assert n == idx.n and abs(avgdl - idx.avgdl) < 1e-9 and abs(avg_idf - idx.avg_idf) < 1e-9
    conn = connect(user="NDL_JUNIOR", password=pw)
    try:
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM NEEDLE.ADV_DOC")
            assert cur.fetchone()[0] == len(docs), "NDL_JUNIOR must see exactly the public advisories"
            for q in _real_queries():
                terms = query_terms(q)
                cur.execute("SELECT ADV_ID, KW_SCORE, KW_RANK FROM TABLE(NEEDLE.BM25_SEARCH("
                            "CAST(? AS CLOB(32K)), 10)) AS B ORDER BY KW_RANK", (json.dumps(terms),))
                got = [(str(a).strip(), float(s)) for a, s, _ in cur.fetchall()]
                pruned = prune_query_terms(terms, idx.df)
                assert_same_ranking(got, _rank_bm25_top(okapi, ids, pruned, 10))
        finally:
            cur.close()
    finally:
        conn.close()
