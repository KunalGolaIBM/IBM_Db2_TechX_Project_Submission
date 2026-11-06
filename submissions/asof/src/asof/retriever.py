"""Clauses in force on a date, ranked by meaning, in one Db2 query.

    FOR BUSINESS_TIME AS OF <customer's date>   which version applied to the customer
    FOR SYSTEM_TIME   AS OF <moment>            optional: what the database held then (replay)
    VECTOR_DISTANCE(..., COSINE)                semantic rank against the claim

Every value is a bound parameter. The schema is a validated constant.
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
from .schema import validate_schema

MAX_K = 10
_COLUMNS = (
    "c.CLAUSE_ID, c.AREA, c.TITLE, c.VERSION_LABEL, c.CLAUSE_TEXT, c.RULE_JSON, "
    "c.BUS_START, c.BUS_END, c.SYS_START, "
    f"VECTOR_DISTANCE(c.EMBEDDING, VECTOR(?, {DIM}, FLOAT32), COSINE) AS DIST"
)


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


def _sql(schema: str, replay: bool) -> str:
    validate_schema(schema)
    period = "FOR SYSTEM_TIME AS OF ? FOR BUSINESS_TIME AS OF ?" if replay else "FOR BUSINESS_TIME AS OF ?"
    return (
        f"SELECT {_COLUMNS} FROM {schema}.POLICY_CLAUSE {period} AS c "
        "WHERE c.DOC_ID = ? ORDER BY DIST FETCH FIRST ? ROWS ONLY"
    )


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
    if system_time is None:
        params: tuple = (vec, as_of, doc_id, k)
    else:
        params = (vec, system_time, as_of, doc_id, k)
    rows = db.query(conn, _sql(schema, system_time is not None), params)
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
