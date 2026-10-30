"""Ingest runbooks (Markdown + YAML front-matter) into Db2.

Examples:
    python ingest.py            # add/update runbooks
    python ingest.py --reset    # drop and recreate the table first
"""
import argparse
from pathlib import Path
from typing import Any

import yaml
from haystack import Document, Pipeline
from haystack.components.preprocessors import DocumentSplitter
from haystack.components.writers import DocumentWriter
from haystack.document_stores.types import DuplicatePolicy
from haystack_integrations.components.embedders.ollama import OllamaDocumentEmbedder

from config import EMBED_MODEL, OLLAMA_URL, get_document_store

RUNBOOK_DIR = Path(__file__).parent / "data" / "runbooks"
REQUIRED_KEYS = [
    "runbook_id", "title", "service", "environment",
    "severity", "status", "last_verified",
]


def parse_runbook(path: Path) -> Document:
    """Split front-matter from body and build one Document per file."""
    # "---" markers: text before the first is empty, then front-matter, then body.
    parts = path.read_text(encoding="utf-8").split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"{path.name}: missing YAML front-matter block")
    meta: dict[str, Any] = yaml.safe_load(parts[1])
    missing = [k for k in REQUIRED_KEYS if k not in meta]
    if missing:
        raise ValueError(f"{path.name}: missing front-matter keys {missing}")
    # YAML parses dates into date objects; Db2 metadata needs plain JSON-friendly strings.
    meta["last_verified"] = str(meta["last_verified"])
    meta["source_file"] = path.name
    # Title in the content so every chunk's first words carry the topic.
    content = f"# {meta['title']}\n\n{parts[2].strip()}"
    # Stable id per file would also work, but chunk ids derive from content,
    # which is why OVERWRITE is used below for re-ingestion.
    return Document(content=content, meta=meta)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="drop and recreate the table first")
    args = parser.parse_args()

    store = get_document_store(recreate_table=args.reset)

    docs = [parse_runbook(p) for p in sorted(RUNBOOK_DIR.glob("*.md"))]

    pipeline = Pipeline()
    pipeline.add_component("splitter", DocumentSplitter(split_by="word", split_length=220, split_overlap=30))
    # No prefix here: Granite is asymmetric and only queries get a prefix.
    pipeline.add_component("embedder", OllamaDocumentEmbedder(model=EMBED_MODEL, url=OLLAMA_URL))
    # OVERWRITE makes re-running ingest idempotent instead of failing on duplicate ids.
    pipeline.add_component("writer", DocumentWriter(document_store=store, policy=DuplicatePolicy.OVERWRITE))
    pipeline.connect("splitter.documents", "embedder.documents")
    pipeline.connect("embedder.documents", "writer.documents")

    result = pipeline.run({"splitter": {"documents": docs}})
    print(f"Chunks written: {result['writer']['documents_written']}")
    print(f"Total documents in table: {store.count_documents()}")
    for d in docs:
        m = d.meta
        print(f"  {m['runbook_id']}  {m['environment']:<5} {m['status']:<10} {m['title']}")


if __name__ == "__main__":
    main()
