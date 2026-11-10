"""Embed docs.jsonl embed_text with Ollama nomic-embed-text -> data/emb.jsonl.gz.

Run from the needle/ folder (PYTHONPATH=src):
    .venv\\Scripts\\python -m needle.embed [--batch 64] [--limit N]

- Embeds every NON-withdrawn record (MAL included), in docs.jsonl order.
- Document prefix: "search_document: " (queries must use "search_query: ").
- Output line: {"adv_id": ..., "emb": [768 floats rounded to 6 decimals]}.
- Resume-safe: ids already present in emb.jsonl.gz are skipped. Each batch is appended as its
  own gzip member; a truncated trailing member (killed run) is repaired on the next start.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
import zlib
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
DOC_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "
DIM = 768


def read_done(path: Path) -> tuple[set[str], list[str] | None]:
    """Return (ids already embedded, valid lines if the file needs repair else None)."""
    done: set[str] = set()
    if not path.exists():
        return done, None
    lines: list[str] = []
    broken = False
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                lines.append(line)
    except (EOFError, gzip.BadGzipFile, zlib.error, OSError):
        broken = True
    good = []
    for line in lines:
        if not line.endswith("\n"):
            broken = True
            continue
        try:
            obj = json.loads(line)
            if len(obj["emb"]) != DIM:
                raise ValueError
        except Exception:
            broken = True
            continue
        done.add(obj["adv_id"])
        good.append(line)
    return done, (good if broken else None)


def embed_batch(session: requests.Session, url: str, model: str, texts: list[str]) -> list[list[float]]:
    r = session.post(f"{url}/api/embed", json={"model": model, "input": texts, "truncate": True}, timeout=600)
    r.raise_for_status()
    embs = r.json()["embeddings"]
    if len(embs) != len(texts) or any(len(e) != DIM for e in embs):
        raise RuntimeError(f"bad embedding response: n={len(embs)} expected {len(texts)}")
    return embs


def embed_query(text: str) -> list[float]:
    """Embed one query string (adds the search_query prefix). For other modules."""
    load_dotenv(ROOT / ".env")
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    model = os.environ.get("EMBED_MODEL", "nomic-embed-text")
    with requests.Session() as s:
        return embed_batch(s, url, model, [QUERY_PREFIX + text])[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--limit", type=int, default=0, help="stop after N new embeddings (0 = all)")
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    model = os.environ.get("EMBED_MODEL", "nomic-embed-text")
    out = DATA / "emb.jsonl.gz"

    done, repair = read_done(out)
    if repair is not None:
        with gzip.open(out, "wt", encoding="utf-8", newline="\n") as f:
            f.writelines(repair)
        print(f"repaired {out}: kept {len(repair)} complete lines", flush=True)

    todo: list[tuple[str, str]] = []
    with open(DATA / "docs.jsonl", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d["withdrawn"] or d["adv_id"] in done:
                continue
            todo.append((d["adv_id"], DOC_PREFIX + (d["embed_text"] or d["adv_id"])))
    if args.limit:
        todo = todo[: args.limit]
    print(f"already={len(done)} todo={len(todo)} batch={args.batch} model={model}", flush=True)

    t0 = time.time()
    n = 0
    reported500 = False
    with requests.Session() as s:
        for i in range(0, len(todo), args.batch):
            chunk = todo[i: i + args.batch]
            embs = embed_batch(s, url, model, [t for _, t in chunk])
            with gzip.open(out, "at", encoding="utf-8", newline="\n") as f:
                for (adv_id, _), e in zip(chunk, embs):
                    f.write(json.dumps({"adv_id": adv_id, "emb": [round(x, 6) for x in e]}) + "\n")
            n += len(chunk)
            el = time.time() - t0
            if not reported500 and n >= 500:
                print(f"THROUGHPUT first {n} docs: {el:.1f}s = {n/el:.1f} docs/s", flush=True)
                reported500 = True
            if (i // args.batch) % 20 == 0:
                print(f"{n}/{len(todo)} {el:.0f}s {n/max(el,1e-9):.1f} docs/s", flush=True)
    el = time.time() - t0
    print(f"DONE new={n} total={len(done)+n} elapsed={el:.1f}s rate={n/max(el,1e-9):.1f} docs/s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
