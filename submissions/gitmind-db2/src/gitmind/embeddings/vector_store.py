"""
GitMind 2.0 — Vector Store & Semantic Retrieval Interface

Connects LangChain agents to semantic knowledge bases:
- Primary production backend: IBM Db2 Vector Store (DB2VS)
- Repository-scoped isolation and deterministic filtering
- Legacy fallback to ChromaDB when STORAGE_BACKEND=chroma
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from langchain.tools import tool

import config
from utils.repo_utils import get_repo_id

logger = logging.getLogger("gitmind.embeddings")


class GitMindVectorStore:
    """
    Persistent vector store using ChromaDB for legacy/local development.
    """

    def __init__(self, collection_name: str = "gitmind", persist_dir: Optional[Path] = None):
        import chromadb
        from chromadb.api.shared_system_client import SharedSystemClient

        self._persist_dir = str(Path(persist_dir or config.CHROMA_PATH).resolve())
        self._collection_name = collection_name

        Path(self._persist_dir).mkdir(parents=True, exist_ok=True)

        try:
            self._chroma_client = chromadb.PersistentClient(path=self._persist_dir)
        except KeyError:
            SharedSystemClient._identifier_to_system.pop(self._persist_dir, None)
            self._chroma_client = chromadb.PersistentClient(path=self._persist_dir)

        self._collection = self._chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._embeddings = None

    def _get_embeddings(self):
        if self._embeddings is None:
            self._embeddings = config.get_embeddings()
        return self._embeddings

    def index_commits(self, commits: list[dict], repo_id: str = "default"):
        if not commits:
            return

        documents = []
        ids = []
        metadatas = []

        for commit in commits:
            doc_id = f"{repo_id}:commit:{commit['hash']}"
            text = f"Commit by {commit.get('author', 'unknown')}: {commit.get('message', '')}"

            documents.append(text)
            ids.append(doc_id)
            metadatas.append({
                "type": "commit",
                "hash": commit.get("hash", ""),
                "author": commit.get("author", ""),
                "date": str(commit.get("date", "")),
                "repo_id": repo_id,
            })

        embeddings_model = self._get_embeddings()
        batch_size = 50
        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i : i + batch_size]
            batch_ids = ids[i : i + batch_size]
            batch_meta = metadatas[i : i + batch_size]
            embeddings = embeddings_model.embed_documents(batch_docs)
            self._collection.upsert(
                ids=batch_ids,
                embeddings=embeddings,
                documents=batch_docs,
                metadatas=batch_meta,
            )

    def index_prs(self, prs: list[dict], repo_id: str = "default"):
        if not prs:
            return

        documents = []
        ids = []
        metadatas = []

        for pr in prs:
            doc_id = f"{repo_id}:pr:{pr['number']}"
            text = f"PR #{pr['number']}: {pr.get('title', '')}. {pr.get('body', '')[:500]}"

            documents.append(text)
            ids.append(doc_id)
            metadatas.append({
                "type": "pr",
                "number": str(pr.get("number", "")),
                "author": pr.get("author", ""),
                "state": pr.get("state", ""),
                "repo_id": repo_id,
            })

        embeddings_model = self._get_embeddings()
        batch_size = 50
        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i : i + batch_size]
            batch_ids = ids[i : i + batch_size]
            batch_meta = metadatas[i : i + batch_size]
            embeddings = embeddings_model.embed_documents(batch_docs)
            self._collection.upsert(
                ids=batch_ids,
                embeddings=embeddings,
                documents=batch_docs,
                metadatas=batch_meta,
            )

    def index_issues(self, issues: list[dict], repo_id: str = "default"):
        if not issues:
            return

        documents = []
        ids = []
        metadatas = []

        for issue in issues:
            doc_id = f"{repo_id}:issue:{issue['number']}"
            text = f"Issue #{issue['number']}: {issue.get('title', '')}. {issue.get('body', '')[:500]}"

            documents.append(text)
            ids.append(doc_id)
            metadatas.append({
                "type": "issue",
                "number": str(issue.get("number", "")),
                "author": issue.get("author", ""),
                "state": issue.get("state", ""),
                "repo_id": repo_id,
            })

        embeddings_model = self._get_embeddings()
        batch_size = 50
        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i : i + batch_size]
            batch_ids = ids[i : i + batch_size]
            batch_meta = metadatas[i : i + batch_size]
            embeddings = embeddings_model.embed_documents(batch_docs)
            self._collection.upsert(
                ids=batch_ids,
                embeddings=embeddings,
                documents=batch_docs,
                metadatas=batch_meta,
            )

    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_type: Optional[str] = None,
        repo_id: Optional[str] = None,
    ) -> list[dict]:
        embeddings_model = self._get_embeddings()
        query_embedding = embeddings_model.embed_query(query)

        where_filter = {}
        if filter_type:
            where_filter["type"] = filter_type
        if repo_id:
            where_filter["repo_id"] = repo_id

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter if where_filter else None,
        )

        formatted = []
        if results and results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                entry = {
                    "text": doc,
                    "score": 1 - results["distances"][0][i] if results["distances"] else None,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                }
                formatted.append(entry)

        return formatted

    def count(self) -> int:
        return self._collection.count()

    def clear(self):
        import chromadb

        self._chroma_client.delete_collection(self._collection_name)
        self._collection = self._chroma_client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )


# Singleton legacy store
_chroma_store: Optional[GitMindVectorStore] = None


def _get_vector_store() -> GitMindVectorStore:
    global _chroma_store
    if _chroma_store is None:
        _chroma_store = GitMindVectorStore()
    return _chroma_store


# ---------------------------------------------------------------------------
# LangChain Tool for Agents
# ---------------------------------------------------------------------------

@tool
def semantic_search(query: str, top_k: int = 5, filter_type: str = "") -> str:
    """
    Search the GitMind knowledge base for commits, PRs, and issues
    semantically related to the query. Use this when keyword search
    is insufficient — it understands meaning, not just exact words.

    filter_type can be: 'commit', 'pr', 'issue', 'doc', or '' for all.
    """
    # 1. Primary path: IBM Db2 Vector Store
    if config.STORAGE_BACKEND == "db2":
        try:
            from data.repository_memory import get_repository_memory

            repo_id = get_repo_id(".")
            memory = get_repository_memory()
            results = memory.search_repository_memory(
                query=query,
                repo_id=repo_id,
                top_k=top_k,
                filter_type=filter_type if filter_type else None,
            )

            if not results:
                return (
                    f"No semantically similar results found in IBM Db2 for repository '{repo_id}'. "
                    "If the repository was recently cloned or updated, run 'gitmind index'."
                )

            formatted = []
            for r in results:
                art_type = r.get("artifact_type", "doc").upper()
                score = r.get("score", 1.0)
                ref = r.get("commit_sha") or r.get("artifact_id") or r.get("file_path") or ""
                formatted.append(
                    f"[{art_type}] (Score: {score}, Ref: {ref})\n{r.get('text')}"
                )

            return "\n\n---\n\n".join(formatted)

        except Exception as e:
            logger.error(f"Db2 semantic search failed: {e}")
            raise RuntimeError(
                f"IBM Db2 semantic search failed: {e}. Check Db2 connection via 'gitmind db2 doctor'."
            ) from e

    # 2. Legacy fallback path: ChromaDB
    else:
        store = _get_vector_store()
        if store.count() == 0:
            return "Vector store is empty. Run indexing first with 'gitmind index'."

        results = store.search(
            query=query,
            top_k=top_k,
            filter_type=filter_type if filter_type else None,
        )

        if not results:
            return "No semantically similar results found."

        return str(results)


EMBEDDING_TOOLS = [semantic_search]
