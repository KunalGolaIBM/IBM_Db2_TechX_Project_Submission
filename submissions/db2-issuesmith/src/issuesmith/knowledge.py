"""Troubleshooting knowledge base stored in Db2 through LangChain's DB2VS.

Each markdown file in data/knowledge_base becomes one row in {schema}.KB_DOCS
(text CLOB, BSON metadata, VECTOR embedding). Retrieval uses Db2's
VECTOR_DISTANCE with the COSINE metric.
"""
from __future__ import annotations

import logging
from pathlib import Path

from langchain_core.embeddings import Embeddings

log = logging.getLogger(__name__)


def parse_kb_file(path: Path) -> tuple[str, dict]:
    """Files start with 'key: value' header lines, then a blank line, then the body."""
    meta: dict[str, str] = {"id": path.stem, "source": path.name}
    lines = path.read_text(encoding="utf-8").splitlines()
    body_start = 0
    for i, line in enumerate(lines):
        if not line.strip():
            body_start = i + 1
            break
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip().lower()] = v.strip()
    body = "\n".join(lines[body_start:]).strip()
    text = f"{meta.get('title', path.stem)}\n\n{body}"
    return text, meta


class KnowledgeBase:
    def __init__(self, conn, embeddings: Embeddings, schema: str = "ISSUESMITH") -> None:
        from langchain_community.vectorstores.utils import DistanceStrategy
        from langchain_db2.db2vs import DB2VS

        self.table = f"{schema.upper()}.KB_DOCS"
        self.conn = conn
        self.store = DB2VS(
            embedding_function=embeddings,
            table_name=self.table,
            client=conn,
            distance_strategy=DistanceStrategy.COSINE,
        )

    def seed(self, kb_dir: Path) -> int:
        from langchain_db2.db2vs import clear_table

        files = sorted(kb_dir.glob("*.md"))
        if not files:
            return 0
        clear_table(self.conn, self.table)
        texts, metas = zip(*(parse_kb_file(f) for f in files))
        self.store.add_texts(list(texts), metadatas=list(metas))
        return len(files)

    def count(self) -> int:
        cur = self.conn.cursor()
        try:
            cur.execute(f"SELECT COUNT(*) FROM {self.table}")
            return int(cur.fetchone()[0])
        finally:
            cur.close()

    def search(self, query: str, k: int = 3) -> list[dict]:
        results = self.store.similarity_search_with_score(query, k=k)
        return [
            {
                "title": doc.metadata.get("title", doc.metadata.get("id", "untitled")),
                "category": doc.metadata.get("category", ""),
                "source": doc.metadata.get("source", ""),
                "url": doc.metadata.get("url", ""),
                "text": doc.page_content,
                "distance": float(score),
            }
            for doc, score in results
        ]
