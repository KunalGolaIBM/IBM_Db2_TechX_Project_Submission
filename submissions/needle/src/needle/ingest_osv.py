"""Normalize the OSV PyPI export into data/docs.jsonl (+ data/raw.jsonl.gz for NEEDLE.ADV_RAW).

Run from the needle/ folder:
    .venv\\Scripts\\python -m needle.ingest_osv        (with PYTHONPATH=src)

Input : every *.json file in OSV_DATA_DIR (needle/.env). Files are untrusted data: parsed as JSON only.
Output: data/docs.jsonl     one JSON object per record (fields documented in FIELDS below)
        data/raw.jsonl.gz   {"adv_id", "raw", "raw_sha256"} per record (raw file text, for ADV_RAW)

canon_id: union-find over each record id and its aliases (CVE ids join groups too).
          canonical id = lexicographically smallest GHSA id among the group's RECORD ids,
          else the smallest record id in the group (so canon_id is always a real ADV_ID).
row_bucket = int(sha256(canon_id).hexdigest(), 16) % 100.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from needle.tokenize import index_text, tokenize

ROOT = Path(__file__).resolve().parents[2]  # needle/
DATA = ROOT / "data"
EMBED_TEXT_MAX = 2000

FIELDS = [
    "adv_id", "canon_id", "kind", "summary", "details", "packages", "published", "modified",
    "withdrawn", "cvss", "affected", "aliases", "embed_text", "doc_len", "row_bucket", "raw_sha256",
]


def _win_path(p: str) -> Path:
    """Accept Git-Bash style /c/Users/... paths from .env on Windows."""
    m = re.match(r"^/([a-zA-Z])/(.*)$", p)
    if m and os.name == "nt":
        p = f"{m.group(1).upper()}:/{m.group(2)}"
    return Path(p)


def normalize_pkg(name: str) -> str:
    """PEP 503 normalized PyPI name (lowercase, runs of -_. -> '-')."""
    return re.sub(r"[-_.]+", "-", name).lower()


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:  # path compression
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            if rb < ra:
                ra, rb = rb, ra
            self.parent[rb] = ra


def pick_cvss(rec: dict) -> str | None:
    sev = list(rec.get("severity") or [])
    for aff in rec.get("affected") or []:
        sev.extend(aff.get("severity") or [])
    if not sev:
        return None
    order = {"CVSS_V3": 0, "CVSS_V4": 1, "CVSS_V2": 2}
    sev = sorted(sev, key=lambda s: order.get(s.get("type"), 9))
    score = sev[0].get("score")
    return str(score)[:200] if score else None


def main() -> int:
    load_dotenv(ROOT / ".env")
    src = _win_path(os.environ["OSV_DATA_DIR"])
    DATA.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    files = sorted(src.glob("*.json"))
    recs: list[tuple[dict, str, str]] = []  # (record, raw_text, sha256)
    bad = 0
    for f in files:
        try:
            raw_bytes = f.read_bytes()
            raw_text = raw_bytes.decode("utf-8")
            rec = json.loads(raw_text)
            if not isinstance(rec, dict) or not isinstance(rec.get("id"), str):
                raise ValueError("no id")
        except Exception:
            bad += 1
            continue
        recs.append((rec, raw_text, hashlib.sha256(raw_bytes).hexdigest()))

    # Duplicate ids (should not happen): keep the first file in sorted order.
    seen: set[str] = set()
    uniq = []
    for r in recs:
        if r[0]["id"] in seen:
            bad += 1
            continue
        seen.add(r[0]["id"])
        uniq.append(r)
    recs = uniq
    record_ids = seen

    uf = UnionFind()
    for rec, _, _ in recs:
        uf.find(rec["id"])
        for a in rec.get("aliases") or []:
            if isinstance(a, str) and a:
                uf.union(rec["id"], a)
    groups: dict[str, list[str]] = {}
    for rid in record_ids:
        groups.setdefault(uf.find(rid), []).append(rid)
    canon_of_root: dict[str, str] = {}
    for root, members in groups.items():
        ghsa = sorted(m for m in members if m.startswith("GHSA-"))
        canon_of_root[root] = ghsa[0] if ghsa else min(members)

    counts = {"records": 0, "withdrawn": 0, "with_affected_versions": 0, "affected_rows": 0,
              "with_cvss": 0, "groups": len(groups), "multi_record_groups": 0}
    counts["multi_record_groups"] = sum(1 for m in groups.values() if len(m) > 1)
    kinds: dict[str, int] = {}

    docs_path = DATA / "docs.jsonl"
    raw_path = DATA / "raw.jsonl.gz"
    with open(docs_path, "w", encoding="utf-8", newline="\n") as fd, \
            gzip.open(raw_path, "wt", encoding="utf-8", newline="\n") as fr:
        for rec, raw_text, sha in sorted(recs, key=lambda r: r[0]["id"]):
            adv_id = rec["id"]
            canon = canon_of_root[uf.find(adv_id)]
            kind = adv_id.split("-", 1)[0][:8]
            summary = (rec.get("summary") or "").strip()
            details = (rec.get("details") or "").strip()
            affected_rows: list[list[str]] = []
            pkgs: set[str] = set()
            for aff in rec.get("affected") or []:
                pkg = (aff.get("package") or {})
                name = pkg.get("name")
                eco = pkg.get("ecosystem") or ""
                if not name:
                    continue
                pkgs.add(name)
                for v in aff.get("versions") or []:
                    affected_rows.append([eco, normalize_pkg(name), str(v)])
            affected_rows = sorted({tuple(r) for r in affected_rows})
            aliases = sorted({a for a in (rec.get("aliases") or []) if isinstance(a, str) and a})
            embed_text = (summary + "\n\n" + details).strip()[:EMBED_TEXT_MAX] if summary else details[:EMBED_TEXT_MAX]
            doc = {
                "adv_id": adv_id,
                "canon_id": canon,
                "kind": kind,
                "summary": summary or None,
                "details": details or None,
                "packages": sorted(pkgs),
                "published": rec.get("published"),
                "modified": rec.get("modified"),
                "withdrawn": rec.get("withdrawn"),
                "cvss": pick_cvss(rec),
                "affected": [list(r) for r in affected_rows],
                "aliases": aliases,
                "embed_text": embed_text,
            }
            doc["doc_len"] = len(tokenize(index_text(doc)))
            doc["row_bucket"] = int(hashlib.sha256(canon.encode("utf-8")).hexdigest(), 16) % 100
            doc["raw_sha256"] = sha
            assert list(doc) == FIELDS
            fd.write(json.dumps(doc, ensure_ascii=False) + "\n")
            fr.write(json.dumps({"adv_id": adv_id, "raw": raw_text, "raw_sha256": sha}, ensure_ascii=False) + "\n")

            counts["records"] += 1
            kinds[kind] = kinds.get(kind, 0) + 1
            counts["withdrawn"] += 1 if doc["withdrawn"] else 0
            counts["with_affected_versions"] += 1 if affected_rows else 0
            counts["affected_rows"] += len(affected_rows)
            counts["with_cvss"] += 1 if doc["cvss"] else 0

    print(f"files={len(files)} unreadable_or_duplicate={bad}")
    print("counts", json.dumps(counts))
    print("kinds", json.dumps(dict(sorted(kinds.items()))))
    print(f"wrote {docs_path} ({docs_path.stat().st_size/1e6:.1f} MB), {raw_path} ({raw_path.stat().st_size/1e6:.1f} MB)")
    print(f"elapsed {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
