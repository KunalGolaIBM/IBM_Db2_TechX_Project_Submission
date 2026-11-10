"""Local side of the in-codespace TRIAGE check (run from needle/ with PYTHONPATH=src).

  prepare : query list (tests/test_bm25_parity.py real queries + vague paraphrases) -> analyzed terms + Ollama
            query embeddings -> data/triage_cases.json  (copy to the codespace, run scripts/triage_check_in_codespace.py)
  compare : data/triage_check_out.json (copied back) vs rank_bm25.BM25Okapi on the same corpus -> parity report.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

VAGUE = [
    "a yaml parsing library lets attackers run code when loading untrusted files",
    "image processing library crashes or overflows on a crafted file",
    "a package on pypi that steals browser passwords and discord tokens after install",
    "web framework lets users inject sql through an ordering parameter",
    "http client leaks credentials when following redirects to another host",
]


def prepare(out_path: Path) -> None:
    from needle.bm25 import query_terms
    from needle.embed import embed_query
    from test_bm25_parity import _real_queries

    cases = []
    for q in _real_queries() + VAGUE:
        cases.append({"q": q, "terms": query_terms(q), "vec": [round(x, 6) for x in embed_query(q)]})
    out_path.write_text(json.dumps(cases), encoding="utf-8")
    print(f"wrote {len(cases)} cases -> {out_path}")


def compare(res_path: Path) -> int:
    from rank_bm25 import BM25Okapi

    from needle.bm25 import B, EPSILON, K1, Bm25Index, load_bm25_docs, prune_query_terms, query_terms
    from test_bm25_parity import TOL, _rank_bm25_top

    docs, _ = load_bm25_docs(str(ROOT / "data" / "docs.jsonl"))
    idx = Bm25Index(docs)
    ids = sorted(docs)
    okapi = BM25Okapi([docs[a] for a in ids], k1=K1, b=B, epsilon=EPSILON)
    res = json.loads(res_path.read_text(encoding="utf-8"))
    bad = 0
    for name in ("kw",):
        exact = tie_only = mism = 0
        for c in res["cases"]:
            if name not in c:
                continue
            got = [(r[0], r[1]) for r in c[name]]
            exp = _rank_bm25_top(okapi, ids, prune_query_terms(query_terms(c["q"]), idx.df), 10)
            same_scores = len(got) == len(exp) and all(abs(g[1] - e[1]) <= TOL * max(1, abs(e[1]))
                                                       for g, e in zip(got, exp))
            if same_scores and [g[0] for g in got] == [e[0] for e in exp]:
                exact += 1
            elif same_scores:
                tie_only += 1  # same scores, ids differ only inside an equal-score group
            else:
                mism += 1
                print(f"MISMATCH {name}: {c['q'][:50]}\n  got {got[:4]}\n  exp {exp[:4]}")
        print(f"{name}: queries={exact + tie_only + mism} exact_top10={exact} tie_order_only={tie_only} "
              f"mismatch={mism}")
        bad += mism
    same = sum(1 for c in res["cases"] if [r[0] for r in c["triage"]] == [r[0] for r in c["triage_mode_HYBRID"]])
    print(f"NEEDLE.TRIAGE == TRIAGE_MODE(HYBRID): {same}/{len(res['cases'])} queries")
    kw_ok = sum(1 for c in res["cases"]
                if [r[0] for r in c["triage_mode_KW"]] == [r[0] for r in c["kw"]][:res["k"]])
    print(f"TRIAGE_MODE(KW) order == BM25_SEARCH order: {kw_ok}/{len(res['cases'])} queries")
    for name, s in res["timing"].items():
        print(f"TIMING {name:<28} {s}")
    if "dbi_check" in res:
        print(f"DBI_CHECK {res['dbi_check']}")
    return 1 if bad else 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prepare", "compare"])
    ap.add_argument("--cases", default=str(ROOT / "data" / "triage_cases.json"))
    ap.add_argument("--result", default=str(ROOT / "data" / "triage_check_out.json"))
    a = ap.parse_args()
    if a.cmd == "prepare":
        prepare(Path(a.cases))
    else:
        sys.exit(compare(Path(a.result)))


if __name__ == "__main__":
    main()
