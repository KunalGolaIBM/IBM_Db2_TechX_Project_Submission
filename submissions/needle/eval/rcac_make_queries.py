"""Embed the RCAC sweep query set on this PC (Ollama) -> data/rcac_queries.json.

Queries = the 20 fixed G1 triage queries (scripts/g1_make_queries.py, for a line-for-line comparison with the
plain-WHERE baseline in docs/evidence/g1_vector_index.md) + the 150 paraphrase queries (eval/queries/paraphrase.jsonl).
Split: dev / heldout by sha256(qid) parity (deterministic). Router thresholds are fitted on dev only;
reported router numbers are heldout only. Recall here is ANN-vs-EXACT recall, not relevance.

Run from needle/:  PYTHONPATH=src .venv\\Scripts\\python -m eval.rcac_make_queries   (or python eval\\rcac_make_queries.py)
"""
import hashlib
import importlib.util
import json
from pathlib import Path

from needle.embed import embed_query

ROOT = Path(__file__).resolve().parents[1]


def _g1_queries() -> list[str]:
    spec = importlib.util.spec_from_file_location("g1q", ROOT / "scripts" / "g1_make_queries.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return list(mod.QUERIES)


def main() -> None:
    items = [{"qid": f"g1:{i:02d}", "text": t} for i, t in enumerate(_g1_queries())]
    with open(ROOT / "eval" / "queries" / "paraphrase.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            items.append({"qid": r["qid"], "text": r["query"]})
    for it in items:
        it["split"] = "dev" if int(hashlib.sha256(it["qid"].encode()).hexdigest(), 16) % 2 == 0 else "heldout"
        it["vec"] = [round(x, 6) for x in embed_query(it["text"])]
    out = ROOT / "data" / "rcac_queries.json"
    out.write_text(json.dumps(items), encoding="utf-8")
    n_dev = sum(1 for it in items if it["split"] == "dev")
    print(f"wrote {out} n={len(items)} dev={n_dev} heldout={len(items) - n_dev} dim={len(items[0]['vec'])}")


if __name__ == "__main__":
    main()
