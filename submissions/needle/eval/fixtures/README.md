# NEEDLE sample-mode fixtures (no Ollama, no download)

A frozen, deterministic sample of the NEEDLE corpus. It lets a reviewer run the whole Db2 pipeline
(schema, load, vector index, BM25 postings, row permissions, `NEEDLE.TRIAGE`, the exposure join) without
Ollama, without a GPU and without downloading the OSV export. Use it with the README section
"Sample mode". Built by [`eval/build_fixtures.py`](../build_fixtures.py); counts and SHA-256 values are in
[`manifest.json`](manifest.json).

## Contents

| File | What it holds |
|---|---|
| `docs.jsonl.gz` | 2,000 non-withdrawn OSV PyPI advisories in the `data/docs.jsonl` format (normalized fields; lines copied verbatim from the full file) |
| `emb.jsonl.gz` | Their precomputed 768-dim document embeddings (Ollama `nomic-embed-text`, prefix `search_document: `), copied verbatim from `data/emb.jsonl.gz` |
| `raw.jsonl.gz` | The unchanged raw OSV JSON of the same 2,000 records, with SHA-256 (loaded into `NEEDLE.ADV_RAW`) |
| `postings.jsonl.gz`, `corpus_stats.json` | BM25 postings and statistics of the sample (`needle.bm25.build` on `docs.jsonl.gz`) |
| `queries.jsonl.gz` | 9 demo queries: text, BM25 terms and a precomputed 768-dim query vector (`nomic-embed-text`, prefix `search_query: `). 5 demo queries without ground truth, plus the first 2 queries of the frozen `named` and `paraphrase` eval slices with their ground truth |
| `manifest.json` | Seed, selection counts, embedding model digest, SHA-256 of every file and of the full source files |

Size: about 10.3 MB in total (gzip; the files are written with gzip mtime 0, so a rebuild from the same inputs
gives the same bytes for the corpus files).

Composition: GHSA 810, PYSEC 804, MAL 386 (1,213 alias groups). Selection, seed 20261109, whole alias groups only:
1. every ground-truth advisory of the 450 frozen eval queries (`eval/queries/*.jsonl`);
2. every advisory that lists a package version deployed in the synthetic service fleet (`needle.sbom`), so the
   exposure join finds matches;
3. every PyYAML advisory (the app's demo query);
4. a seeded random fill toward 40% GHSA, 40% PYSEC, 20% MAL.

The sample is therefore biased toward the evaluation targets and the fleet packages. It is a functional test
set, not a representative corpus.

## What sample mode does not show

- **The vector index is likely not used at this size.** The Db2 optimizer is cost-based. At about 2,000 rows a
  table scan with a sort is cheap, so `FETCH APPROX` can run as an exact scan. During development, EXPLAIN chose
  TBSCAN + SORT at 3,000 rows and the vector index (IXSCAN on `NEEDLE.ADV_DOC_VIX`) on the full corpus of 26,210
  rows (`docs/evidence/g1_vector_index.md`). `scripts/run_sample_queries.py` prints the plan it gets; in the
  clean-host run on this sample it was TBSCAN + SORT, vector index not used (`docs/evidence/clean_host_run.md`).
  Use the full corpus for every vector-index and ANN-recall claim.
- **No result in README "Results" comes from the sample.** BM25 statistics, RCAC visible fractions and recall
  all differ from the full corpus. Sample mode proves the pipeline runs; it does not reproduce the measurements.

## Rebuild

Needs the full data files (`data/docs.jsonl`, `data/emb.jsonl.gz`, `data/raw.jsonl.gz`) and Ollama with
`nomic-embed-text` for the query vectors:

```bash
PYTHONPATH=src python eval/build_fixtures.py
```

Ollama embeddings can differ in the last digits between runs or GPUs, so `queries.jsonl.gz` is not guaranteed to
be byte-identical after a rebuild. The other files are.

## Attribution and licences

The advisory data comes from the [OSV.dev](https://osv.dev) PyPI export
(`https://osv-vulnerabilities.storage.googleapis.com/PyPI/all.zip`, the same export as the full NEEDLE corpus;
source file hashes in `manifest.json`). OSV states licences per
source ([OSV data sources](https://google.github.io/osv.dev/data/)):

| ID prefix | Source | Licence | Records here |
|---|---|---|---|
| `GHSA-` | [GitHub Advisory Database](https://github.com/github/advisory-database) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | 810 |
| `PYSEC-` | [PyPI Advisory Database](https://github.com/pypa/advisory-database) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | 804 |
| `MAL-` | [OpenSSF Malicious Packages](https://github.com/ossf/malicious-packages) | [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0) | 386 |

Changes: `raw.jsonl.gz` holds the records unchanged (with their IDs and a SHA-256 of each record).
`docs.jsonl.gz` holds fields derived from them by `src/needle/ingest_osv.py` (normalized package names, flattened
affected versions, alias lists, a hash bucket). `emb.jsonl.gz`, `postings.jsonl.gz` and `queries.jsonl.gz` are
derived data computed by NEEDLE. The embeddings were produced with the
[`nomic-embed-text`](https://ollama.com/library/nomic-embed-text) model (Apache 2.0) through Ollama.
The 9 query texts are ours (5 demo queries) or come from the frozen eval slices; the `paraphrase` queries are
synthetic rewrites, as labelled in `eval/queries/paraphrase.manifest.json`.
