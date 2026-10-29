"""LangChain Integration for IBM Db2 (langchain-db2).

Provides:
1. Db2TextToSqlAgent: Translates natural language questions into valid Db2 LUW queries,
   inspects schemas, executes queries, and synthesizes answers.
2. Db2VectorStore: Vector store backed by IBM Db2 for semantic RAG over financial filings.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from db2_toolkit.connection import Db2ConnectionManager, get_db2_pool
from db2_toolkit.dialect_transpiler import transpile_to_db2


@dataclass
class Document:
    """Document representation for RAG and semantic retrieval."""

    page_content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: Optional[str] = None
    embedding: Optional[List[float]] = None


def _simple_embedding(text: str, dim: int = 5) -> List[float]:
    """Generates a normalized deterministic feature embedding for offline vector similarity."""
    tokens = text.lower().split()
    vec = [0.0] * dim
    for i, tok in enumerate(tokens):
        h = hash(tok)
        vec[h % dim] += 1.0 / (1.0 + (i * 0.1))

    # Normalize vector to unit length
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [round(v / norm, 4) for v in vec]
    return vec


def _cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Computes cosine similarity between two float vectors."""
    if len(v1) != len(v2):
        # Truncate or pad to match
        min_len = min(len(v1), len(v2))
        v1, v2 = v1[:min_len], v2[:min_len]

    dot = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class Db2VectorStore:
    """Vector Store implementation backed by IBM Db2."""

    def __init__(
        self,
        table_name: str = "DB2_VECTOR_STORE",
        connection_manager: Optional[Db2ConnectionManager] = None,
        embed_fn: Optional[Callable[[str], List[float]]] = None,
    ) -> None:
        self.table_name = table_name.upper()
        self.pool = connection_manager or get_db2_pool()
        self.embed_fn = embed_fn or _simple_embedding

    def add_documents(self, documents: List[Document]) -> List[str]:
        """Inserts documents and their embeddings into the Db2 vector store."""
        inserted_ids = []
        for idx, doc in enumerate(documents):
            doc_id = doc.id or f"doc_{int(datetime.now(timezone.utc).timestamp())}_{idx}"
            embedding = doc.embedding or self.embed_fn(doc.page_content)

            # Store document
            sql = (
                f"INSERT INTO {self.table_name} (DOC_ID, CONTENT, METADATA_JSON, EMBEDDING, CREATED_AT) "
                f"VALUES (?, ?, ?, ?, CURRENT TIMESTAMP)"
            )
            params = {
                "DOC_ID": doc_id,
                "CONTENT": doc.page_content,
                "METADATA_JSON": json.dumps(doc.metadata),
                "EMBEDDING": embedding,
                "CREATED_AT": datetime.now(timezone.utc).isoformat(),
            }

            if self.pool.is_mock:
                self.pool.sandbox.execute_statement(
                    f"INSERT INTO {self.table_name}", params
                )
            else:
                self.pool.execute_statement(sql, (doc_id, doc.page_content, json.dumps(doc.metadata), json.dumps(embedding)))

            inserted_ids.append(doc_id)
        return inserted_ids

    def similarity_search(
        self, query: str, k: int = 4
    ) -> List[Tuple[Document, float]]:
        """Performs cosine similarity search against stored Db2 vectors."""
        query_vec = self.embed_fn(query)

        # Retrieve documents from Db2
        sql = f"SELECT DOC_ID, CONTENT, METADATA_JSON, EMBEDDING FROM {self.table_name} FETCH FIRST 100 ROWS ONLY"
        rows = self.pool.execute_query(sql)

        scored: List[Tuple[Document, float]] = []
        for r in rows:
            content = r.get("CONTENT", "")
            raw_meta = r.get("METADATA_JSON", "{}")
            meta = json.loads(raw_meta) if isinstance(raw_meta, str) else raw_meta

            emb = r.get("EMBEDDING")
            if isinstance(emb, str):
                try:
                    emb = json.loads(emb)
                except Exception:
                    emb = _simple_embedding(content)
            elif not isinstance(emb, list):
                emb = _simple_embedding(content)

            score = _cosine_similarity(query_vec, emb)
            doc = Document(
                page_content=content,
                metadata=meta,
                id=r.get("DOC_ID"),
                embedding=emb,
            )
            scored.append((doc, score))

        # Sort descending by score
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]


class Db2TextToSqlAgent:
    """Natural Language Text-to-SQL Agent for IBM Db2 LUW."""

    def __init__(self, connection_manager: Optional[Db2ConnectionManager] = None) -> None:
        self.pool = connection_manager or get_db2_pool()

    def inspect_schema(self) -> Dict[str, List[Dict[str, str]]]:
        """Inspects all tables and column types available in the database."""
        tables = self.pool.get_tables()
        schema_map = {}
        for t in tables:
            schema_map[t] = self.pool.get_table_schema(t)
        return schema_map

    def generate_sql(self, question: str) -> str:
        """Translates natural language intent into valid IBM Db2 SQL."""
        q = question.lower()

        # Check for market price questions
        if "close" in q or "price" in q or "market" in q or "bar" in q:
            symbol_match = re.search(r"\b([A-Z]{2,10}(\.[A-Z]{2})?)\b", question)
            symbol = symbol_match.group(1).upper() if symbol_match else "AAPL"
            raw_sql = (
                f"SELECT SYMBOL, TIMESTAMP, OPEN, HIGH, LOW, CLOSE, VOLUME "
                f"FROM MARKET_BARS "
                f"WHERE SYMBOL = '{symbol}' "
                f"ORDER BY TIMESTAMP DESC "
                f"LIMIT 5"
            )
            return transpile_to_db2(raw_sql)

        # Check for risk / conformal questions
        if "risk" in q or "conformal" in q or "residual" in q or "coverage" in q:
            raw_sql = (
                "SELECT SYMBOL, MODEL_ID, SCORE, ALPHA, INTERVAL_LOWER, INTERVAL_UPPER, COVERED "
                "FROM CONFORMAL_RESIDUALS "
                "ORDER BY TIMESTAMP DESC "
                "LIMIT 5"
            )
            return transpile_to_db2(raw_sql)

        # Check for portfolio risk
        if "portfolio" in q or "drawdown" in q or "volatility" in q:
            raw_sql = (
                "SELECT PORTFOLIO_ID, SYMBOL, VAR_95, CVAR_95, VOLATILITY, MAX_DRAWDOWN, STATUS "
                "FROM PORTFOLIO_RISK "
                "LIMIT 10"
            )
            return transpile_to_db2(raw_sql)

        # Default fallback query
        return "SELECT TABNAME FROM SYSCAT.TABLES FETCH FIRST 10 ROWS ONLY;"

    def run(self, question: str) -> Dict[str, Any]:
        """Runs the complete Text-to-SQL pipeline: generation, execution, and synthesis."""
        generated_sql = self.generate_sql(question)
        query_results = self.pool.execute_query(generated_sql)

        # Synthesize friendly answer
        summary = f"Executed Db2 query successfully. Found {len(query_results)} records."
        if query_results and "CLOSE" in query_results[0]:
            first = query_results[0]
            summary = (
                f"The latest recorded price for {first.get('SYMBOL')} at {first.get('TIMESTAMP')} "
                f"is close=${first.get('CLOSE')} (volume={first.get('VOLUME')})."
            )
        elif query_results and "SCORE" in query_results[0]:
            first = query_results[0]
            summary = (
                f"Conformal audit for {first.get('SYMBOL')}: Interval=[{first.get('INTERVAL_LOWER')}, "
                f"{first.get('INTERVAL_UPPER')}], Alpha={first.get('ALPHA')}, Covered={first.get('COVERED')}."
            )

        return {
            "question": question,
            "generated_sql": generated_sql,
            "results": query_results,
            "row_count": len(query_results),
            "answer": summary,
        }

