"""Build the frozen sample-mode fixtures in eval/fixtures/ (requirement R18) from the full NEEDLE data files.

Build-time inputs (not needed to USE the fixtures): data/docs.jsonl, data/emb.jsonl.gz, data/raw.jsonl.gz,
eval/queries/{named,paraphrase,masked}.jsonl, and Ollama nomic-embed-text for the few demo query vectors.
Sample mode itself needs neither Ollama nor data/.

Run from the needle/ folder:
    PYTHONPATH=src python eval/build_fixtures.py

Selection (deterministic, seed 20261109). Only non-withdrawn advisories (the set in NEEDLE.ADV_DOC). Every
advisory is taken together with its whole canon_id group (GHSA/PYSEC copies of one vulnerability).
  must-include  (a) every ground-truth adv_id of every frozen eval query (eval/queries/*.jsonl, 450 queries)
                (b) every advisory that lists a (package, version) of the synthetic fleet (needle.sbom), so the
                    exposure join has matches
                (c) every advisory that names pyyaml (the app's demo query)
  fill          seeded shuffle per kind until the sample holds about TARGET advisories with the kind shares
                SHARES (biased toward GHSA/PYSEC, some MAL).
Outputs (gzip with mtime 0, so the bytes are reproducible): docs.jsonl.gz, emb.jsonl.gz, raw.jsonl.gz (lines copied
verbatim from the full files), postings.jsonl.gz + corpus_stats.json (needle.bm25.build on the sample),
queries.jsonl.gz (demo queries, BM25 terms, precomputed 768-dim query vectors), manifest.json.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import random
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from needle.bm25 import build as bm25_build, query_terms  # noqa: E402
from needle.sbom import generate_fleet, normalize_pkg  # noqa: E402

DATA = ROOT / "data"
OUT = ROOT / "eval" / "fixtures"
SEED = 20261109
TARGET = 2000
SHARES = {"GHSA": 0.40, "PYSEC": 0.40, "MAL": 0.20}

# The app's demo text (src/needle/app.py SAMPLE), copied verbatim.
APP_SAMPLE = ("heads up from #platform-sec: someone says the yaml loader we use in a few python services can run "
              "arbitrary code when it parses an untrusted config file. no CVE number in the thread. are we exposed?")
# Short demo queries (also used in data/triage_cases.json during development). No ground truth: smoke checks only.
DEMO_QUERIES = [
    ("demo:app_sample", APP_SAMPLE),
    ("demo:pyyaml", "pyyaml full_load arbitrary code execution"),
    ("demo:django_sqli", "django sql injection"),
    ("demo:mal_discord", "malicious package stealing discord tokens"),
    ("demo:redirect_creds", "http client leaks credentials when following redirects to another host"),
]
EVAL_SLICES_FOR_QUERIES = ("named", "paraphrase")   # the first 2 queries of each slice, with their ground truth
N_PER_SLICE = 2


def gz_bytes(text_lines: list[str]) -> bytes:
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0, compresslevel=9) as g:
        for ln in text_lines:
            g.write(ln.encode("utf-8"))
    return buf.getvalue()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    docs_path = DATA / "docs.jsonl"
    docs: dict[str, dict] = {}
    order: list[str] = []
    with open(docs_path, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d.get("withdrawn"):
                continue
            docs[d["adv_id"]] = d
            order.append(d["adv_id"])
    groups: dict[str, list[str]] = defaultdict(list)
    for a in order:
        groups[docs[a]["canon_id"]].append(a)

    sel: set[str] = set()
    why = Counter()

    def add_group(adv_id: str, reason: str) -> None:
        if adv_id not in docs:
            return
        for a in groups[docs[adv_id]["canon_id"]]:
            if a not in sel:
                sel.add(a)
                why[reason] += 1

    # (a) ground truth of every frozen eval query
    eval_queries: dict[str, list[dict]] = {}
    for sl in ("named", "masked", "paraphrase"):
        rows = [json.loads(x) for x in open(ROOT / "eval" / "queries" / f"{sl}.jsonl", encoding="utf-8")]
        eval_queries[sl] = rows
        for q in rows:
            for a in q["gt"]:
                add_group(a, "eval_ground_truth")
    # (b) advisories that list a deployed fleet (package, version)
    fleet = {(c.package, c.version) for c in generate_fleet()}
    for a in order:
        for eco, pkg, ver in docs[a].get("affected") or []:
            if eco == "PyPI" and (normalize_pkg(pkg), ver) in fleet:
                add_group(a, "fleet_version_listed")
                break
    # (c) every pyyaml advisory (demo query)
    for a in order:
        if any(normalize_pkg(p) == "pyyaml" for p in docs[a].get("packages") or []):
            add_group(a, "pyyaml_demo")

    must = len(sel)
    # fill: seeded shuffle per kind toward the target shares
    rng = random.Random(SEED)
    pools = {k: sorted(a for a in order if docs[a]["kind"] == k and a not in sel) for k in SHARES}
    for k in SHARES:
        rng.shuffle(pools[k])
    for k, share in SHARES.items():
        want = round(TARGET * share)
        for a in pools[k]:
            if sum(1 for x in sel if docs[x]["kind"] == k) >= want or len(sel) >= TARGET:
                break
            add_group(a, f"fill_{k}")
    # top up (any kind, same seeded order) if the shares left the sample short of TARGET
    rest = [a for k in SHARES for a in pools[k]]
    rng.shuffle(rest)
    for a in rest:
        if len(sel) >= TARGET:
            break
        add_group(a, "fill_topup")

    OUT.mkdir(parents=True, exist_ok=True)
    keep_order = [a for a in order if a in sel]

    # docs / emb / raw: verbatim lines of the full files, in the full files' order
    with open(docs_path, encoding="utf-8") as f:
        doc_lines = [ln for ln in f if json.loads(ln)["adv_id"] in sel and not json.loads(ln).get("withdrawn")]
    with gzip.open(DATA / "emb.jsonl.gz", "rt", encoding="utf-8") as f:
        emb_lines = [ln for ln in f if json.loads(ln)["adv_id"] in sel]
    with gzip.open(DATA / "raw.jsonl.gz", "rt", encoding="utf-8") as f:
        raw_lines = [ln for ln in f if json.loads(ln)["adv_id"] in sel]
    assert len(doc_lines) == len(sel) == len(emb_lines) == len(raw_lines), (len(doc_lines), len(sel), len(emb_lines), len(raw_lines))
    (OUT / "docs.jsonl.gz").write_bytes(gz_bytes(doc_lines))
    (OUT / "emb.jsonl.gz").write_bytes(gz_bytes(emb_lines))
    (OUT / "raw.jsonl.gz").write_bytes(gz_bytes(raw_lines))

    # BM25 postings for the sample (same code as the full corpus: needle.bm25.build)
    tmp = Path(tempfile.mkdtemp(prefix="needle_fx_"))
    try:
        (tmp / "docs.jsonl").write_text("".join(doc_lines), encoding="utf-8")
        st = bm25_build(str(tmp / "docs.jsonl"), str(tmp / "out"))
        with gzip.open(tmp / "out" / "postings.jsonl.gz", "rt", encoding="utf-8") as f:
            (OUT / "postings.jsonl.gz").write_bytes(gz_bytes(list(f)))
        shutil.copyfile(tmp / "out" / "corpus_stats.json", OUT / "corpus_stats.json")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # demo queries: BM25 terms + precomputed query vectors (Ollama, build time only)
    import requests
    from needle.embed import QUERY_PREFIX, embed_query

    url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    model = os.environ.get("EMBED_MODEL", "nomic-embed-text")
    tags = requests.get(f"{url}/api/tags", timeout=10).json()["models"]
    digest = next((m["digest"] for m in tags if m["name"].split(":")[0] == model.split(":")[0]), None)
    qrows = []
    for qid, text in DEMO_QUERIES:
        qrows.append({"qid": qid, "query": text, "gt": None, "synthetic": False,
                      "note": "demo query, no ground truth (smoke check)"})
    for sl in EVAL_SLICES_FOR_QUERIES:
        for q in eval_queries[sl][:N_PER_SLICE]:
            qrows.append({"qid": q["qid"], "query": q["query"], "gt": q["gt"], "synthetic": q["synthetic"],
                          "note": f"first {N_PER_SLICE} queries of eval/queries/{sl}.jsonl"})
    for r in qrows:
        r["terms"] = query_terms(r["query"])
        r["vec"] = embed_query(r["query"])
        assert len(r["vec"]) == 768
        if r["gt"]:
            assert all(a in sel for a in r["gt"]), r["qid"]
    (OUT / "queries.jsonl.gz").write_bytes(
        gz_bytes([json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in qrows]))

    kinds = Counter(docs[a]["kind"] for a in keep_order)
    buckets = Counter(int(docs[a]["row_bucket"]) < 10 for a in keep_order)
    files = {}
    for name in ("docs.jsonl.gz", "emb.jsonl.gz", "raw.jsonl.gz", "postings.jsonl.gz", "corpus_stats.json",
                 "queries.jsonl.gz"):
        p = OUT / name
        files[name] = {"bytes": p.stat().st_size, "sha256": sha256_file(p)}
    manifest = {
        "built_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "seed": SEED, "target": TARGET, "kind_shares": SHARES,
        "advisories": len(keep_order), "by_kind": dict(sorted(kinds.items())),
        "canon_groups": len({docs[a]["canon_id"] for a in keep_order}),
        "rows_with_row_bucket_below_10": buckets[True],
        "selected_by_rule": dict(why),
        "must_include": must,
        "bm25": {"n": st.n, "postings": st.postings, "vocab": st.vocab},
        "queries": len(qrows),
        "query_embedding": {"model": model, "ollama_digest": digest, "prefix": QUERY_PREFIX, "dim": 768},
        "source": {"docs.jsonl_sha256": sha256_file(docs_path),
                   "emb.jsonl.gz_sha256": sha256_file(DATA / "emb.jsonl.gz"),
                   "raw.jsonl.gz_sha256": sha256_file(DATA / "raw.jsonl.gz")},
        "files": files,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    total = sum(v["bytes"] for v in files.values())
    print(json.dumps({k: manifest[k] for k in ("advisories", "by_kind", "canon_groups", "selected_by_rule",
                                               "must_include", "bm25", "queries")}, indent=1))
    print(f"wrote {OUT} total {total/1e6:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
