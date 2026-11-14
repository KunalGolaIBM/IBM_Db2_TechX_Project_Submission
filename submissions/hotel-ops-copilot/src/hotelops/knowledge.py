"""Policy knowledge base on IBM Db2 through IBM's official LangChain integration (`langchain-db2`).

`DB2VS` is a LangChain `VectorStore` backed by a Db2 table with a `VECTOR(384, FLOAT32)` column;
similarity search runs as `VECTOR_DISTANCE(..., COSINE)` inside Db2. The manager identity loads the
handbook at setup; the agent identity only needs SELECT on the table to search it.
"""
from __future__ import annotations

import re
from functools import lru_cache

from langchain_core.embeddings import Embeddings

from .config import PROJECT_ROOT, load_settings

TABLE = "POLICY_KB"
HANDBOOK = PROJECT_ROOT / "data" / "policies.md"
SECTION = re.compile(r"^## (POL-[A-Z]+-\d+) \| (.+)$", re.M)


class LocalBgeEmbeddings(Embeddings):
    """LangChain `Embeddings` adapter for the project's local BGE-small (fastembed / ONNX) model."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        from .embeddings import embed_documents

        return [list(map(float, v)) for v in embed_documents(texts)]

    def embed_query(self, text: str) -> list[float]:
        from .embeddings import embed_query

        return list(map(float, embed_query(text)))


def parse_handbook(text: str) -> list[tuple[str, str, str]]:
    """Split the handbook into (policy_id, title, body) sections."""
    parts = SECTION.split(text)
    return [(parts[i], parts[i + 1].strip(), parts[i + 2].strip()) for i in range(1, len(parts), 3)]


def _dbi(role: str):
    import ibm_db_dbi

    s = load_settings().db2
    user, pwd = (s.agent_user, s.agent_password) if role == "agent" else (s.admin_user, s.admin_password)
    return ibm_db_dbi.connect(s.conn_str(user, pwd), "", "")


def _store(client):
    from langchain_community.vectorstores.utils import DistanceStrategy
    from langchain_db2 import DB2VS

    return DB2VS(embedding_function=LocalBgeEmbeddings(), table_name=TABLE, client=client,
                 distance_strategy=DistanceStrategy.COSINE)


def load_handbook() -> int:
    """(Re)create POLICY_KB from data/policies.md with DB2VS.from_texts, as the manager identity."""
    from langchain_community.vectorstores.utils import DistanceStrategy
    from langchain_db2 import DB2VS

    sections = parse_handbook(HANDBOOK.read_text(encoding="utf-8"))
    DB2VS.from_texts(
        [f"{pid} {title}. {body}" for pid, title, body in sections],
        LocalBgeEmbeddings(),
        metadatas=[{"id": pid, "policy_id": pid, "title": title} for pid, title, _ in sections],
        client=_dbi("admin"), table_name=TABLE, distance_strategy=DistanceStrategy.COSINE)
    return len(sections)


@lru_cache(maxsize=1)
def _agent_conn():
    """The agent's ibm_db_dbi connection for langchain-db2 (read-only use)."""
    conn = _dbi("agent")
    conn.set_autocommit(True)
    return conn


@lru_cache(maxsize=1)
def agent_store():
    """Read-only DB2VS bound to the agent identity (the table already exists, so nothing is created)."""
    return _store(_agent_conn())


def search_policies(query: str, k: int = 3) -> list[dict]:
    try:
        hits = agent_store().similarity_search_with_score(query, k=max(1, min(int(k), 6)))
    finally:
        # ibm_db_dbi does not close the search cursor, which keeps the unit of work (and its POLICY_KB lock)
        # open until the process ends; that once blocked a schema reset while the app was running. End it here.
        _agent_conn().commit()
    return [{"policy_id": d.metadata.get("policy_id"), "title": d.metadata.get("title"),
             "text": d.page_content, "distance": round(float(score), 4)} for d, score in hits]
