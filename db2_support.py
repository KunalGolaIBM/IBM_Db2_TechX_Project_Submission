"""Small Db2-backed retrieval core for the Db2 Support RAG demo.

The embedding function is intentionally deterministic and dependency-free so the
example can be tested offline. Replace it with a sentence-transformer or
watsonx embedding model in production while keeping the Db2 query unchanged.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Iterable


VECTOR_DIMENSIONS = 8


@dataclass(frozen=True)
class Article:
    title: str
    body: str
    category: str


def embed(text: str) -> list[float]:
    """Return a stable, normalized 8-dimensional local embedding."""
    digest = hashlib.sha256(text.lower().encode("utf-8")).digest()
    values = [((byte / 255.0) * 2.0) - 1.0 for byte in digest[:VECTOR_DIMENSIONS]]
    norm = sum(value * value for value in values) ** 0.5 or 1.0
    return [round(value / norm, 7) for value in values]


def vector_literal(values: Iterable[float]) -> str:
    """Format a vector literal accepted by Db2's VECTOR function."""
    values = list(values)
    if len(values) != VECTOR_DIMENSIONS:
        raise ValueError(f"expected {VECTOR_DIMENSIONS} dimensions")
    return "[" + ",".join(f"{value:.7f}" for value in values) + "]"


def build_search_sql(table: str, category: str | None = None) -> str:
    """Build the parameterized retrieval statement; user text is never interpolated."""
    filter_sql = " AND category = ?" if category else ""
    return f"""SELECT title, body, category,
       VECTOR_DISTANCE(embedding, VECTOR(?, {VECTOR_DIMENSIONS}, FLOAT32), COSINE) AS distance
FROM {table}
WHERE 1 = 1{filter_sql}
ORDER BY distance
FETCH FIRST 5 ROWS ONLY"""


def connection_string() -> str:
    return ";".join(
        [
            f"DATABASE={os.getenv('DB2_DB', 'BLUDB')}",
            f"HOSTNAME={os.getenv('DB2_HOST', 'localhost')}",
            f"PORT={os.getenv('DB2_PORT', '50000')}",
            "PROTOCOL=TCPIP",
            f"UID={os.getenv('DB2_USERNAME', 'db2inst1')}",
            f"PWD={os.getenv('DB2_PASSWORD', '')}",
        ]
    )


def create_schema(db2, table: str) -> None:
    """Create the vector-enabled table if it does not already exist."""
    db2.exec_immediate(
        f"""CREATE TABLE {table} (
            id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            body CLOB NOT NULL,
            category VARCHAR(40) NOT NULL,
            embedding VECTOR({VECTOR_DIMENSIONS}, FLOAT32) NOT NULL
        )"""
    )


def insert_articles(db2, table: str, articles: Iterable[Article]) -> int:
    statement = f"INSERT INTO {table} (title, body, category, embedding) VALUES (?, ?, ?, VECTOR(?, {VECTOR_DIMENSIONS}, FLOAT32))"
    count = 0
    for article in articles:
        prepared = db2.prepare(statement)
        db2.bind_param(prepared, 1, article.title)
        db2.bind_param(prepared, 2, article.body)
        db2.bind_param(prepared, 3, article.category)
        db2.bind_param(prepared, 4, vector_literal(embed(article.title + " " + article.body)))
        db2.execute(prepared)
        count += 1
    return count


def search(db2, table: str, question: str, category: str | None = None) -> list[dict]:
    """Retrieve the five nearest articles; filtering and ranking happen in Db2."""
    statement = db2.prepare(build_search_sql(table, category))
    db2.bind_param(statement, 1, vector_literal(embed(question)))
    if category:
        db2.bind_param(statement, 2, category)
    db2.execute(statement)
    rows = db2.fetch_assoc(statement)
    results = []
    while rows:
        results.append(rows)
        rows = db2.fetch_assoc(statement)
    return results
