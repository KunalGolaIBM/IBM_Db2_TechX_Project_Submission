"""BM25 keyword index for NEEDLE (owner: bm25 agent).

Builds the rows of NEEDLE.POSTING from ``data/docs.jsonl`` and holds the reference BM25 scorer
that the SQL in ``sql/02_bm25.sql`` / ``sql/03_triage_proc.sql`` must reproduce.

Analyzer (one definition, used for documents AND queries):
1. ``needle.tokenize.tokenize`` on ``needle.tokenize.index_text(doc)`` (the shared tokenizer; not forked).
   Identifiers stay whole and their parts are added: ``log4j-core`` -> ``log4j-core``, ``log4j``, ``core``.
2. Drop English stop words and 1-character tokens (``keep()``).
3. Per-document cap: a document keeps at most ``MAX_TERMS_PER_DOC`` distinct terms (highest tf first,
   ties by first position). Tokens of dropped terms are removed from the document. The cap changes
   352 of 26,210 documents at 512 (measured before the stop-word filter).

The BM25 "document" is the token list after steps 1-3. Its length is ``BM25_DL`` (stored on every
posting row so the keyword leg never joins ADV_DOC). Note: ADV_DOC.DOC_LEN is the shared, unfiltered
token count and is NOT the BM25 length.

Scoring = rank_bm25.BM25Okapi exactly (k1=1.2, b=0.75, epsilon=0.25):
    idf(t)   = ln(N - df + 0.5) - ln(df + 0.5)
    idf(t)   = EPSILON * AVG_IDF            if idf(t) < 0   (AVG_IDF = mean raw idf over the vocabulary)
    score(d) = sum over DISTINCT query terms t in d of  idf(t) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl / avgdl))
Query terms are de-duplicated (no query-term-frequency factor). The SQL keyword leg also keeps at most
``MAX_QUERY_TERMS`` query terms (the ones with the lowest df, ties by term) to bound cost for pasted
advisories; ``prune_query_terms`` mirrors that rule.

CLI:
    python -m needle.bm25 build [--docs data/docs.jsonl] [--out data]
        -> data/postings.jsonl.gz (sorted by term, adv_id), data/term_df.jsonl.gz, data/corpus_stats.json
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import time
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Iterator

from needle.tokenize import index_text, tokenize

K1 = 1.2
B = 0.75
EPSILON = 0.25
MAX_TERMS_PER_DOC = 512
MAX_QUERY_TERMS = 64
MAX_TERM_LEN = 128  # NEEDLE.POSTING.TERM VARCHAR(128); the tokenizer enforces it in characters

# Standard English function words. Domain words (code, package, malicious, pypi, ...) are kept on purpose:
# IDF down-weights them and they still help the long-query case.
STOPWORDS: frozenset[str] = frozenset("""
a about above after again against all also am an and any are aren't as at be because been before being
below between both but by can cannot could did do does doing don down during each either etc few for from
further had has have having he her here hers herself him himself his how however i if in into is it its
itself just let may me might more most must my myself no nor not now of off on once only or other our ours
ourselves out over own per same shall she should so some such than that the their theirs them themselves
then there these they this those through thus to too under until up upon us very via was we were what when
where whether which while who whom whose why will with within without would yet you your yours yourself
yourselves
""".split())


def keep(tok: str) -> bool:
    """True if a token from the shared tokenizer is indexed (not a stop word, length >= 2, <= 128 bytes)."""
    return len(tok) >= 2 and tok not in STOPWORDS and len(tok.encode("utf-8")) <= MAX_TERM_LEN


def analyze(text: str | None) -> list[str]:
    """Shared tokenizer + stop-word filter, duplicates kept (no per-document cap)."""
    return [t for t in tokenize(text) if keep(t)]


def doc_terms(doc: dict, max_terms: int = MAX_TERMS_PER_DOC) -> list[str]:
    """The BM25 document of one docs.jsonl record: analyzed tokens after the distinct-term cap."""
    toks = analyze(index_text(doc))
    tf = Counter(toks)
    if len(tf) <= max_terms:
        return toks
    first: dict[str, int] = {}
    for i, t in enumerate(toks):
        first.setdefault(t, i)
    kept = set(sorted(tf, key=lambda t: (-tf[t], first[t]))[:max_terms])
    return [t for t in toks if t in kept]


def query_terms(text: str | None) -> list[str]:
    """Distinct analyzed query terms, in first-occurrence order (the JSON array passed to NEEDLE.TRIAGE)."""
    seen: dict[str, None] = {}
    for t in analyze(text):
        seen.setdefault(t, None)
    return list(seen)


def prune_query_terms(terms: Iterable[str], df: dict[str, int], max_terms: int = MAX_QUERY_TERMS) -> list[str]:
    """Mirror of the SQL rule: keep only terms present in the index, then the ``max_terms`` lowest-df ones."""
    present = sorted({t for t in terms if t in df}, key=lambda t: (df[t], t))
    return present[:max_terms]


def raw_idf(n: int, df: int) -> float:
    return math.log(n - df + 0.5) - math.log(df + 0.5)


@dataclass(frozen=True)
class CorpusStats:
    n: int
    avgdl: float
    avg_idf: float
    vocab: int
    postings: int


class Bm25Index:
    """In-memory BM25Okapi over BM25 documents (reference implementation of the SQL)."""

    def __init__(self, docs: dict[str, list[str]], k1: float = K1, b: float = B, epsilon: float = EPSILON):
        self.k1, self.b, self.epsilon = k1, b, epsilon
        self.tf: dict[str, Counter] = {aid: Counter(toks) for aid, toks in docs.items()}
        self.dl: dict[str, int] = {aid: len(toks) for aid, toks in docs.items()}
        self.n = len(docs)
        self.avgdl = sum(self.dl.values()) / self.n if self.n else 0.0
        self.df: Counter = Counter()
        for c in self.tf.values():
            self.df.update(c.keys())
        raw = {t: raw_idf(self.n, d) for t, d in self.df.items()}
        self.avg_idf = sum(raw.values()) / len(raw) if raw else 0.0
        floor = self.epsilon * self.avg_idf
        self.idf = {t: (floor if v < 0 else v) for t, v in raw.items()}
        self.postings: dict[str, list[tuple[str, int]]] = {}
        for aid in sorted(self.tf):
            for t, f in self.tf[aid].items():
                self.postings.setdefault(t, []).append((aid, f))

    def stats(self) -> CorpusStats:
        return CorpusStats(self.n, self.avgdl, self.avg_idf, len(self.df), sum(len(c) for c in self.tf.values()))

    def scores(self, terms: Iterable[str]) -> dict[str, float]:
        out: dict[str, float] = {}
        for t in dict.fromkeys(terms):  # distinct, order kept
            idf = self.idf.get(t)
            if idf is None:
                continue
            for aid, f in self.postings[t]:
                norm = f + self.k1 * (1 - self.b + self.b * self.dl[aid] / self.avgdl)
                out[aid] = out.get(aid, 0.0) + idf * f * (self.k1 + 1) / norm
        return out

    def top(self, terms: Iterable[str], k: int = 10, prune: bool = True) -> list[tuple[str, float]]:
        """Top-k (adv_id, score) with score > 0, ordered by round(score, 9) DESC then adv_id ASC (as in SQL)."""
        terms = list(terms)
        if prune:
            terms = prune_query_terms(terms, self.df)
        sc = self.scores(terms)
        ranked = sorted(((a, s) for a, s in sc.items() if s > 0), key=lambda x: (-round(x[1], 9), x[0]))
        return ranked[:k]


def iter_docs(path: str, include_withdrawn: bool = False) -> Iterator[dict]:
    """Yield docs.jsonl records. Default: only non-withdrawn records (the set in NEEDLE.ADV_DOC)."""
    with open(path, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d.get("withdrawn") and not include_withdrawn:
                continue
            yield d


def load_bm25_docs(path: str) -> tuple[dict[str, list[str]], dict[str, dict]]:
    """Return ({adv_id: BM25 document}, {adv_id: {row_bucket, embargo_until}})."""
    docs, meta = {}, {}
    for d in iter_docs(path):
        docs[d["adv_id"]] = doc_terms(d)
        meta[d["adv_id"]] = {"row_bucket": int(d["row_bucket"]), "embargo_until": d.get("embargo_until")}
    return docs, meta


def build(docs_path: str, out_dir: str) -> CorpusStats:
    t0 = time.time()
    docs, meta = load_bm25_docs(docs_path)
    idx = Bm25Index(docs)
    st = idx.stats()
    os.makedirs(out_dir, exist_ok=True)
    p_path = os.path.join(out_dir, "postings.jsonl.gz")
    with gzip.open(p_path, "wt", encoding="utf-8", compresslevel=6) as f:
        for term in sorted(idx.postings):
            for aid, tf in idx.postings[term]:  # already sorted by adv_id
                m = meta[aid]
                f.write(json.dumps({"term": term, "adv_id": aid, "tf": tf, "dl": idx.dl[aid],
                                    "row_bucket": m["row_bucket"], "embargo_until": m["embargo_until"]},
                                   ensure_ascii=False, separators=(",", ":")) + "\n")
    with gzip.open(os.path.join(out_dir, "term_df.jsonl.gz"), "wt", encoding="utf-8") as f:
        for term in sorted(idx.df):
            f.write(json.dumps({"term": term, "df": idx.df[term]}, ensure_ascii=False, separators=(",", ":")) + "\n")
    with open(os.path.join(out_dir, "corpus_stats.json"), "w", encoding="utf-8") as f:
        json.dump({"n": st.n, "avgdl": st.avgdl, "avg_idf": st.avg_idf, "vocab": st.vocab, "postings": st.postings,
                   "k1": K1, "b": B, "epsilon": EPSILON, "max_terms_per_doc": MAX_TERMS_PER_DOC,
                   "max_query_terms": MAX_QUERY_TERMS}, f, indent=2)
    print(f"built {st.postings} postings, vocab {st.vocab}, N {st.n}, avgdl {st.avgdl:.4f}, "
          f"avg_idf {st.avg_idf:.6f} in {time.time()-t0:.1f}s -> {p_path}")
    return st


def main() -> None:
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build"])
    ap.add_argument("--docs", default=os.path.join(here, "data", "docs.jsonl"))
    ap.add_argument("--out", default=os.path.join(here, "data"))
    a = ap.parse_args()
    build(a.docs, a.out)


if __name__ == "__main__":
    main()
