"""The fix memory: Db2 as the vector store behind PortProof's repair loop.

Every repair Db2 has *verified* is embedded and kept, so the next time a similar
translation fails with a similar SQLCODE the repair prompt is grounded in fixes
that are already known to work. The store is IBM's official LangChain
integration (``langchain_db2.DB2VS``); the hybrid recall in
:meth:`FixMemory.recall_sql` additionally shows the Db2-native form, where the
vector distance and a relational predicate are evaluated in one statement.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from langchain_db2.db2vs import DB2VS, DistanceStrategy

from . import db
from .embeddings import LocalEmbeddings

TABLE = "FIX_MEMORY"


@dataclass(frozen=True)
class RecalledFix:
    """A past repair that Db2 verified."""

    bad_sql: str
    fixed_sql: str
    sqlcode: int | None
    error_text: str
    dialect: str
    distance: float | None = None

    def as_prompt_line(self) -> str:
        return (
            f"- previously, {self.dialect} SQL failing with SQLCODE={self.sqlcode} "
            f"({self.error_text[:90]})\n"
            f"  was fixed by rewriting it as: {self.fixed_sql}"
        )


def _doc_text(bad_sql: str, sqlcode: int | None, error_text: str) -> str:
    """What gets embedded: the failure, not the fix."""
    return f"SQLCODE={sqlcode} :: {error_text.strip()} :: {' '.join(bad_sql.split())}"


class FixMemory:
    """Vector-recall of verified repairs, stored in Db2."""

    def __init__(self, conn, embeddings: Any | None = None, table_name: str = TABLE):
        self.conn = conn
        self.table_name = table_name
        self.embeddings = embeddings or LocalEmbeddings()
        self._store: DB2VS | None = None

    @property
    def store(self) -> DB2VS:
        if self._store is None:
            # DB2VS drives a DB-API cursor, so wrap the same underlying
            # connection rather than opening a second one.
            import ibm_db_dbi

            self._store = DB2VS(
                embedding_function=self.embeddings,
                table_name=self.table_name,
                client=ibm_db_dbi.Connection(self.conn),
                distance_strategy=DistanceStrategy.COSINE,
            )
        return self._store

    # -- writing ---------------------------------------------------------
    def remember(
        self,
        *,
        bad_sql: str,
        fixed_sql: str,
        sqlcode: int | None,
        error_text: str,
        dialect: str,
        case_name: str = "",
    ) -> bool:
        """Store a repair Db2 has verified. Returns False if it was already known.

        Without this check every run re-stores the same repairs, and recall then
        returns the same fix three times at an identical distance -- which looks
        like three corroborating precedents while actually being one. The
        de-duplication is a Db2 predicate over the stored JSON metadata, so it
        costs one indexless lookup rather than a second store.
        """
        if self._already_known(bad_sql=bad_sql, fixed_sql=fixed_sql, dialect=dialect):
            return False
        self.store.add_texts(
            [_doc_text(bad_sql, sqlcode, error_text)],
            metadatas=[
                {
                    "bad_sql": bad_sql,
                    "fixed_sql": fixed_sql,
                    "sqlcode": sqlcode if sqlcode is not None else 0,
                    "error_text": error_text[:400],
                    "dialect": dialect,
                    "case_name": case_name,
                }
            ],
        )
        return True

    def _already_known(self, *, bad_sql: str, fixed_sql: str, dialect: str) -> bool:
        row = db.fetch_one(
            self.conn,
            f"""
            SELECT 1 FROM {self.table_name}
             WHERE JSON_VALUE(METADATA, '$.dialect'   RETURNING VARCHAR(16))   = ?
               AND JSON_VALUE(METADATA, '$.bad_sql'   RETURNING VARCHAR(4000)) = ?
               AND JSON_VALUE(METADATA, '$.fixed_sql' RETURNING VARCHAR(4000)) = ?
             FETCH FIRST 1 ROW ONLY
            """,
            (dialect, bad_sql, fixed_sql),
        )
        return row is not None

    # -- reading ---------------------------------------------------------
    def recall(
        self, *, bad_sql: str, sqlcode: int | None, error_text: str, k: int = 3
    ) -> list[RecalledFix]:
        """Vector-recall the most similar past failures through DB2VS."""
        query = _doc_text(bad_sql, sqlcode, error_text)
        try:
            hits = self.store.similarity_search_with_score(query, k=k)
        except Exception:
            return []
        out: list[RecalledFix] = []
        for doc, score in hits:
            meta = doc.metadata or {}
            if not meta.get("fixed_sql"):
                continue
            out.append(
                RecalledFix(
                    bad_sql=meta.get("bad_sql", ""),
                    fixed_sql=meta["fixed_sql"],
                    sqlcode=_as_int(meta.get("sqlcode")),
                    error_text=str(meta.get("error_text", "")),
                    dialect=str(meta.get("dialect", "")),
                    distance=float(score) if score is not None else None,
                )
            )
        return out

    def recall_sql(
        self, *, bad_sql: str, sqlcode: int | None, error_text: str, dialect: str, k: int = 3
    ) -> list[RecalledFix]:
        """The same recall, but as one Db2 statement combining vector + relational.

        This is the part that would not survive a swap to a bolt-on vector
        store: the semantic ranking and the structured filter (same source
        dialect, same SQLCODE family) are evaluated together, in the engine,
        with every value bound.
        """
        vector = self.embeddings.embed_query(_doc_text(bad_sql, sqlcode, error_text))
        literal = "[" + ",".join(f"{v:.6f}" for v in vector) + "]"
        sql = f"""
            SELECT JSON_VALUE(METADATA, '$.bad_sql'    RETURNING VARCHAR(4000)),
                   JSON_VALUE(METADATA, '$.fixed_sql'  RETURNING VARCHAR(4000)),
                   JSON_VALUE(METADATA, '$.sqlcode'    RETURNING INTEGER),
                   JSON_VALUE(METADATA, '$.error_text' RETURNING VARCHAR(400)),
                   JSON_VALUE(METADATA, '$.dialect'    RETURNING VARCHAR(16)),
                   VECTOR_DISTANCE(EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) AS DIST
              FROM {self.table_name}
             WHERE JSON_VALUE(METADATA, '$.dialect' RETURNING VARCHAR(16)) = ?
             ORDER BY DIST
             FETCH FIRST {int(k)} ROWS ONLY
        """
        rows = db.fetch_all(self.conn, sql, (literal, dialect))
        return [
            RecalledFix(
                bad_sql=r[0] or "",
                fixed_sql=r[1] or "",
                sqlcode=_as_int(r[2]),
                error_text=r[3] or "",
                dialect=(r[4] or "").strip(),
                distance=float(r[5]) if r[5] is not None else None,
            )
            for r in rows
            if r[1]
        ]

    def count(self) -> int:
        row = db.fetch_one(self.conn, f"SELECT COUNT(*) FROM {self.table_name}")
        return int(row[0]) if row else 0


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def ensure_table(conn, embeddings: Any | None = None, table_name: str = TABLE) -> str:
    """Create the DB2VS table if it does not exist, and report its DDL shape."""
    memory = FixMemory(conn, embeddings=embeddings, table_name=table_name)
    _ = memory.store  # DB2VS creates the table on construction
    cols = db.fetch_all(
        conn,
        "SELECT COLNAME, TYPENAME, LENGTH FROM SYSCAT.COLUMNS "
        "WHERE TABSCHEMA = CURRENT SCHEMA AND TABNAME = ? ORDER BY COLNO",
        (table_name.split(".")[-1],),
    )
    return ", ".join(f"{c.strip()} {t.strip()}({l})" for c, t, l in cols)
