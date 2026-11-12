"""Engineering-policy knowledge base on IBM Db2 vectors via LangChain.

Ingestion: Markdown policy files -> LangChain `MarkdownHeaderTextSplitter` +
`RecursiveCharacterTextSplitter` -> embeddings -> `langchain_db2.DB2VS`, which
stores each chunk in a native Db2 `VECTOR(n, FLOAT32)` column.

Retrieval: `DB2VS.similarity_search_with_score` runs `VECTOR_DISTANCE(...,
COSINE)` inside Db2, so ranking happens in the database, not in Python.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from ..db2.repository import Db2Repository
from ..db2.schema import VECTOR_TABLE
from .embeddings import build_embeddings

_FRONT_MATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)


def parse_policy_file(path: Path) -> Dict[str, Any]:
    """Read a policy Markdown file with a small `key: value` front-matter block."""
    text = path.read_text(encoding="utf-8")
    meta: Dict[str, str] = {}
    m = _FRONT_MATTER.match(text)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        text = text[m.end():]
    return {
        "doc_id": meta.get("id", path.stem.upper()),
        "title": meta.get("title", path.stem.replace("_", " ").title()),
        "category": meta.get("category", "general"),
        "version": meta.get("version", "1.0.0"),
        "source": f"policies/{path.name}",
        "content": text.strip(),
    }


class PolicyKnowledgeBase:
    """Ingests and retrieves engineering policies using langchain-db2 (DB2VS)."""

    def __init__(self, repository: Db2Repository, embedding_provider: str = "ollama", dimension: int = 384,
                 llm: Optional[Any] = None):
        from langchain_db2.db2vs import DistanceStrategy
        from langchain_db2 import DB2VS

        self.repository = repository
        self.embeddings = build_embeddings(embedding_provider, dimension, llm)
        self.store = DB2VS(
            embedding_function=self.embeddings,
            table_name=VECTOR_TABLE,
            client=repository.conn,
            distance_strategy=DistanceStrategy.COSINE,
        )
        self._header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("#", "h1"), ("##", "h2")], strip_headers=False
        )
        self._splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=80)

    def chunk_count(self) -> int:
        rows = self.repository._query("SELECT COUNT(*) AS N FROM POLICY_VECTORS")  # == VECTOR_TABLE
        return int(rows[0]["N"])

    def ingest_directory(self, policies_dir: str) -> Dict[str, int]:
        """(Re)build the vector store from every *.md file in `policies_dir`."""
        from langchain_db2.db2vs import clear_table

        files = sorted(Path(policies_dir).glob("*.md"))
        if not files:
            raise FileNotFoundError(f"No policy Markdown files found in {policies_dir}")
        clear_table(self.repository.conn, VECTOR_TABLE)

        stats: Dict[str, int] = {}
        for path in files:
            doc = parse_policy_file(path)
            sections = self._header_splitter.split_text(doc["content"])
            chunks = self._splitter.split_documents(sections)
            texts = [c.page_content for c in chunks]
            metadatas = [
                {
                    "id": f"{doc['doc_id']}#{i}",
                    "doc_id": doc["doc_id"],
                    "title": doc["title"],
                    "category": doc["category"],
                    "version": doc["version"],
                    "source": doc["source"],
                    "section": c.metadata.get("h2") or c.metadata.get("h1") or doc["title"],
                }
                for i, c in enumerate(chunks)
            ]
            self.store.add_texts(texts, metadatas=metadatas)
            self.repository.save_knowledge_doc(
                doc["doc_id"], doc["title"], doc["source"], doc["category"], doc["version"],
                doc["content"], len(texts),
            )
            stats[doc["doc_id"]] = len(texts)
        self.repository.conn.commit()
        return stats

    def ensure_ingested(self, policies_dir: str) -> None:
        if self.chunk_count() == 0:
            self.ingest_directory(policies_dir)

    def retrieve(self, query: str, top_k: int = 3, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Semantic search in Db2. Returns verbatim policy text with citations."""
        flt = {"category": [category]} if category else None
        # Over-fetch: DB2VS applies metadata filters after ranking, and we de-duplicate by document.
        results = self.store.similarity_search_with_score(query, k=max(top_k * 4, 30 if flt else 0), filter=flt)
        out: List[Dict[str, Any]] = []
        seen = set()
        for doc, distance in results:
            md = doc.metadata
            if md.get("doc_id") in seen:
                continue
            seen.add(md.get("doc_id"))
            out.append({
                "doc_id": md.get("doc_id"),
                "title": md.get("title"),
                "section": md.get("section"),
                "category": md.get("category"),
                "version": md.get("version"),
                "source": md.get("source"),
                "content": doc.page_content,
                "cosine_distance": round(float(distance), 4),
                "similarity": round(1.0 - float(distance), 4),
            })
            if len(out) >= top_k:
                break
        return out
