"""Build the landing page's point cloud (web/public/cloud/) from the real corpus. Run where the data lives:

    PYTHONPATH=src python scripts/build_hero_cloud.py --emb data/load/emb.jsonl.gz --queries scripts/hero_queries.json --out web/public/cloud

scripts/hero_queries.json holds the two sample questions and their nomic-embed-text 'search_query: ' vectors.

Each public advisory becomes one point: its 768-dim nomic-embed-text vector projected to 3D with PCA (no other
shaping). Embargoed advisories are LEFT OUT, so the public page cannot leak them. ROW_BUCKET (0-99) comes from
NEEDLE.ADV_DOC (read as the admin user) so the page can show which rows a 10% analyst may see
(permission: ROW_BUCKET < MAX_BUCKET, 10 for NDL_P10). For each sample query: its exact cosine top 10 among public
rows, the 21 nearest (the size of the vector index's first batch for k = 10 under the shared plan,
eval/results/rcac_ffsource.json) and how many of those a 10% analyst may see, and the top 10 among that analyst's
rows. Exact cosine here; Db2's DiskANN index approximates it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
from pathlib import Path

import numpy as np

P10_MAX_BUCKET = 10
BATCH = 21


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--emb", required=True)
    ap.add_argument("--queries", required=True, help="JSON list of {key, text, vec} (search_query: embeddings)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    import ibm_db

    from needle.sbom import connect_as

    conn = connect_as(None)
    meta: dict[str, tuple[int, int]] = {}
    try:
        st = ibm_db.exec_immediate(conn, "SELECT ADV_ID, ROW_BUCKET, CASE WHEN EMBARGO_UNTIL > CURRENT TIMESTAMP "
                                         "THEN 1 ELSE 0 END FROM NEEDLE.ADV_DOC")
        r = ibm_db.fetch_tuple(st)
        while r:
            meta[r[0].strip()] = (int(r[1]), int(r[2]))
            r = ibm_db.fetch_tuple(st)
    finally:
        ibm_db.close(conn)

    ids, vecs, buckets = [], [], []
    with gzip.open(a.emb, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            m = meta.get(d["adv_id"])
            if m is None or m[1] == 1:  # not in ADV_DOC (withdrawn) or embargoed: never on the public page
                continue
            ids.append(d["adv_id"])
            vecs.append(d["emb"])
            buckets.append(m[0])
    X = np.asarray(vecs, dtype=np.float64)
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    mean = X.mean(axis=0)
    C = (X - mean).T @ (X - mean) / len(X)
    w, V = np.linalg.eigh(C)
    W = V[:, np.argsort(w)[::-1][:3]]
    P = (X - mean) @ W
    scale = np.percentile(np.abs(P), 99, axis=0)
    P = np.clip(P / scale, -1.6, 1.6)
    bucket = np.asarray(buckets, dtype=np.uint8)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    q16 = np.round(P / 1.6 * 32767).astype("<i2")
    (out / "cloud.bin").write_bytes(q16.tobytes() + bucket.tobytes())

    queries = []
    for q in json.loads(Path(a.queries).read_text()):
        v = np.asarray(q["vec"], dtype=np.float64)
        v /= np.linalg.norm(v)
        sim = X @ v
        order = np.argsort(-sim)
        top10 = order[:10]
        batch = order[:BATCH]
        p10_rows = np.where(bucket < P10_MAX_BUCKET)[0]
        p10_top = p10_rows[np.argsort(-sim[p10_rows])[:10]]
        pos = np.clip(((v - mean) @ W) / scale, -1.6, 1.6)
        queries.append({
            "key": q["key"], "text": q["text"], "pos": [round(float(x), 4) for x in pos],
            "top10": [int(i) for i in top10], "top10_ids": [ids[i] for i in top10],
            "batch": [int(i) for i in batch], "batch_visible_p10": int((bucket[batch] < P10_MAX_BUCKET).sum()),
            "p10_top10": [int(i) for i in p10_top], "p10_top10_ids": [ids[i] for i in p10_top],
        })
    info = {
        "n": len(ids), "excluded_embargoed": sum(1 for b, e in meta.values() if e == 1),
        "p10_max_bucket": P10_MAX_BUCKET, "p10_visible": int((bucket < P10_MAX_BUCKET).sum()), "batch": BATCH,
        "pca_explained": [round(float(x), 4) for x in (np.sort(w)[::-1][:3] / w.sum())],
        "format": "cloud.bin = n x 3 int16 little-endian (x,y,z scaled by 1.6/32767), then n uint8 ROW_BUCKET",
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "scripts/build_hero_cloud.py over data/load/emb.jsonl.gz (release needle-data-2026-11-09) and NEEDLE.ADV_DOC",
        "queries": queries,
    }
    (out / "cloud.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    print(f"points={len(ids)} excluded_embargoed={info['excluded_embargoed']} p10_visible={info['p10_visible']} "
          f"pca_explained={info['pca_explained']}")
    for q in queries:
        print(f"{q['key']}: top1={q['top10_ids'][0]} batch21 visible to P10={q['batch_visible_p10']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
