"""Import SciFact abstracts into IBM Db2 for evaluation.

The corpus is stored with source_type='scifact' and external_id=<SciFact doc_id>.
The UI document list excludes dataset documents by default, so importing the full
corpus does not pollute the research workspace.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.repository import Db2Repository  # noqa: E402
from app.services.document_processing import process_text  # noqa: E402
from experiments.scifact_loader import ScifactDocument, load_scifact_corpus  # noqa: E402

SOURCE_TYPE = "scifact"


def build_documents(corpus: list[ScifactDocument]) -> list[dict]:
    documents = []
    for item in corpus:
        processed = process_text(
            item.text.encode("utf-8"),
            filename=f"scifact-{item.doc_id}.txt",
            title=item.title,
        )
        documents.append(
            {
                "external_id": str(item.doc_id),
                "title": processed.title,
                "filename": processed.filename,
                "content_hash": processed.content_hash,
                "source_type": SOURCE_TYPE,
                "passages": processed.passages,
            }
        )
    return documents


def import_scifact_corpus(repository: Db2Repository, corpus_path: str | Path) -> dict:
    corpus = load_scifact_corpus(corpus_path)
    documents = build_documents(corpus)
    stats = repository.bulk_import_documents(documents)
    stats["corpus_documents"] = len(corpus)
    return stats


def scifact_document_map(repository: Db2Repository) -> dict[int, int]:
    """Return SciFact doc_id -> internal Db2 DOCUMENT_ID."""
    return repository.external_id_map(SOURCE_TYPE)
