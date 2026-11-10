"""Load only data/handmade_all.csv into Db2; heldout_v1.csv is evaluation-only."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from config import settings
from db import Db2Repository
from embeddings import get_embedder

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TRAINING_CSV = DATA_DIR / "handmade_all.csv"


def read_examples(path: Path = TRAINING_CSV) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["label", "text", "source"]:
            raise ValueError("CSV must have columns label,text,source")
        rows = list(reader)
    for row in rows:
        if not all(isinstance(row.get(key), str) and row[key].strip() for key in ("label", "text", "source")):
            raise ValueError("Every example needs a nonempty label, text and source")
        if len(row["label"]) > 64 or len(row["text"].encode("utf-8")) > 4000 or len(row["source"]) > 512:
            raise ValueError("Example exceeds Db2 column limits")
    return rows


def example_id(row: dict) -> str:
    payload = json.dumps([row[key] for key in ("label", "text", "source")], ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_examples(repo, embedder) -> dict:
    """Fixed training-file input: never consume the evaluation CSV."""
    rows = read_examples()
    repo.init_examples(embedder.dim)
    stored = repo.get_meta("embedder")
    if stored and stored != embedder.name:
        raise ValueError("Embedding provider changed; run src/seed.py to rebuild consistently")
    repo.set_meta("embedder", embedder.name)
    existing = repo.example_ids()
    pending = {example_id(row): row for row in rows if example_id(row) not in existing}
    vectors = embedder.embed([row["text"] for row in pending.values()]) if pending else []
    if len(vectors) != len(pending):
        raise ValueError("Embedder returned an incomplete batch")
    for (row_id, row), vector in zip(pending.items(), vectors):
        repo.insert_example(row_id, row, vector)
    return {"rows": len(rows), "inserted": len(pending), "skipped": len(rows) - len(pending)}


if __name__ == "__main__":
    repository = Db2Repository()
    repository.init_schema(settings.embed_dim)
    print(load_examples(repository, get_embedder()))
