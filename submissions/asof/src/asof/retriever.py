"""Clauses in force on a date, ranked by meaning, in one Db2 query.

    FOR BUSINESS_TIME AS OF <customer's date>   which version applied to the customer
    FOR SYSTEM_TIME   AS OF <moment>            optional: what the database held then (replay)
    VECTOR_DISTANCE(..., COSINE)                semantic rank against the claim

Both statements are literals and every value, the query vector included, is a bound
parameter. The schema is bound too, by db.use_schema() on the connection.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import ibm_db_dbi
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict, Field

from . import db
from .embeddings import DIM
from .prompts import ClauseView

MAX_K = 10
SQL_AS_OF = (
    "SELECT c.CLAUSE_ID, c.AREA, c.TITLE, c.VERSION_LABEL, c.CLAUSE_TEXT, c.RULE_JSON, "
    "c.BUS_START, c.BUS_END, c.SYS_START, "
    "VECTOR_DISTANCE(c.EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) AS DIST "
    "FROM POLICY_CLAUSE FOR BUSINESS_TIME AS OF ? AS c "
    "WHERE c.DOC_ID = ? ORDER BY DIST FETCH FIRST ? ROWS ONLY"
)
SQL_REPLAY = (
    "SELECT c.CLAUSE_ID, c.AREA, c.TITLE, c.VERSION_LABEL, c.CLAUSE_TEXT, c.RULE_JSON, "
    "c.BUS_START, c.BUS_END, c.SYS_START, "
    "VECTOR_DISTANCE(c.EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) AS DIST "
    "FROM POLICY_CLAUSE FOR SYSTEM_TIME AS OF ? FOR BUSINESS_TIME AS OF ? AS c "
    "WHERE c.DOC_ID = ? ORDER BY DIST FETCH FIRST ? ROWS ONLY"
)
assert DIM == 384, "SQL_AS_OF and SQL_REPLAY are written for 384-dimension embeddings"


@dataclass(frozen=True)
class RetrievedClause:
    clause_id: str
    area: str
    title: str
    version_label: str
    clause_text: str
    rule: dict[str, Any]
    bus_start: date
    bus_end: date
    sys_start: datetime
    distance: float

    def view(self) -> ClauseView:
        return ClauseView(self.clause_id, self.title, self.version_label, self.bus_start, self.bus_end, self.clause_text)


def clauses_as_of(
    conn: ibm_db_dbi.Connection,
    query_vector: list[float],
    as_of: date,
    doc_id: str,
    k: int = 5,
    system_time: datetime | None = None,
    schema: str = db.SCHEMA,
) -> list[RetrievedClause]:
    """Top-k clause versions in force on `as_of` for `doc_id`, nearest first.

    With `system_time`, answers from the database state at that moment instead of now.
    """
    if not 1 <= k <= MAX_K:
        raise ValueError(f"k must be between 1 and {MAX_K}")
    if len(query_vector) != DIM:
        raise ValueError(f"query vector must have {DIM} dimensions")
    vec = db.vector_literal(query_vector)
    db.use_schema(conn, schema)
    if system_time is None:
        rows = db.query(conn, SQL_AS_OF, (vec, as_of, doc_id, k))
    else:
        rows = db.query(conn, SQL_REPLAY, (vec, system_time, as_of, doc_id, k))
    return [
        RetrievedClause(
            clause_id=r[0], area=r[1], title=r[2], version_label=r[3], clause_text=r[4],
            rule=json.loads(r[5]), bus_start=r[6], bus_end=r[7], sys_start=r[8], distance=float(r[9]),
        )
        for r in rows
    ]


class AsOfClauseRetriever(BaseRetriever):
    """LangChain retriever: `retriever.invoke("claim text")` returns the clause versions
    in force on `as_of`, each as a Document with version metadata."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    connect: Callable[[], ibm_db_dbi.Connection]
    embeddings: Embeddings
    doc_id: str
    as_of: date
    k: int = Field(default=5, ge=1, le=MAX_K)
    system_time: datetime | None = None
    schema_name: str = db.SCHEMA

    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun) -> list[Document]:
        vector = self.embeddings.embed_query(query)
        conn = self.connect()
        try:
            found = clauses_as_of(conn, vector, self.as_of, self.doc_id, self.k, self.system_time, self.schema_name)
        finally:
            conn.close()
        return [
            Document(
                page_content=c.clause_text,
                metadata={
                    "clause_id": c.clause_id, "title": c.title, "area": c.area, "version": c.version_label,
                    "bus_start": c.bus_start.isoformat(), "bus_end": c.bus_end.isoformat(),
                    "sys_start": c.sys_start.isoformat(), "distance": c.distance, "rule": c.rule,
                },
            )
            for c in found
        ]
