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
    def exact(self, *, bad_sql: str, dialect: str) -> str | None:
        """The verified repair of exactly this statement, if one is stored.

        A plain Db2 predicate over the stored JSON, not a similarity search:
        "have we fixed this very statement before" has a yes-or-no answer, and
        a nearest neighbour is the wrong tool for it. The answer is what lets a
        repeat failure be repaired with no rule and no model call. It is still
        only a proposal; Db2 compiles and proves it again like any other.
        """
        try:
            row = db.fetch_one(
                self.conn,
                f"""
                SELECT JSON_VALUE(METADATA, '$.fixed_sql' RETURNING VARCHAR(4000))
                  FROM {self.table_name}
                 WHERE JSON_VALUE(METADATA, '$.dialect' RETURNING VARCHAR(16))   = ?
                   AND JSON_VALUE(METADATA, '$.bad_sql' RETURNING VARCHAR(4000)) = ?
                 FETCH FIRST 1 ROW ONLY
                """,
                (dialect, bad_sql),
            )
        except db.Db2Error:
            return None
        return str(row[0]) if row and row[0] else None

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

    def recall_approx(
        self, *, bad_sql: str, sqlcode: int | None, error_text: str, dialect: str, k: int = 3
    ) -> tuple[list[RecalledFix], bool]:
        """The same hybrid recall, served by Db2's approximate vector index.

        ``FETCH APPROX FIRST n ROWS ONLY`` tells Db2 it may answer from the
        vector index instead of distancing every row. The fix memory is small
        enough that this is not about speed today; it is about the shape of the
        thing being right when it is not small, because the usual alternative --
        a bolt-on vector store with the relational filter applied *after* the
        top-k -- loses recall exactly when the filter is selective, which is
        every time it matters here.

        Measured on CE 12.1.5: with a 1%-selective filter, Db2's approximate
        index returned the same top-10 as the exact scan, because the filter is
        evaluated inside the index search rather than after it.

        Returns the hits and whether the approximate path was actually
        available. That second value is checked against the catalog, not against
        whether the clause parsed: Db2 accepts ``FETCH APPROX FIRST`` with no
        vector index present and quietly answers exactly, so "the statement ran"
        is not evidence that an index served it.
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
             FETCH APPROX FIRST {int(k)} ROWS ONLY
        """
        try:
            rows = db.fetch_all(self.conn, sql, (literal, dialect))
            approximate = self.has_vector_index()
        except db.Db2Error:
            # No vector index, or this build does not accept APPROX. Fall back
            # to the exact scan and say so, rather than reporting an index-served
            # answer that was not.
            return (
                self.recall_sql(
                    bad_sql=bad_sql,
                    sqlcode=sqlcode,
                    error_text=error_text,
                    dialect=dialect,
                    k=k,
                ),
                False,
            )
        return (
            [
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
            ],
            approximate,
        )

    def has_vector_index(self) -> bool:
        # Db2 12.1 records an approximate vector index as INDEXTYPE 'VANN'
        # (vector approximate nearest neighbour); 'VECT' is accepted here too so
        # the check does not depend on one build's spelling.
        row = db.fetch_one(
            self.conn,
            "SELECT COUNT(*) FROM SYSCAT.INDEXES "
            " WHERE TABSCHEMA = CURRENT SCHEMA AND TABNAME = ? "
            "   AND INDEXTYPE IN ('VANN', 'VECT')",
            (self.table_name.split(".")[-1],),
        )
        return bool(row and int(row[0]))

    def count(self) -> int:
        row = db.fetch_one(self.conn, f"SELECT COUNT(*) FROM {self.table_name}")
        return int(row[0]) if row else 0


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


#: Name of the approximate vector index on the fix memory's embeddings.
VECTOR_INDEX = "IX_FIX_MEMORY_VEC"

#: A 32K-page tablespace, created by ``scripts/create_db2_users.sh``. Required
#: for the vector index -- see :func:`ensure_vector_index`.
VECTOR_TABLESPACE = "PPVEC"

#: Embedding width of all-MiniLM-L6-v2, and the width DB2VS declares.
EMBEDDING_DIMENSIONS = 384


def _tablespace_available(conn, name: str) -> bool:
    row = db.fetch_one(
        conn,
        "SELECT COUNT(*) FROM SYSCAT.TABLESPACES WHERE TBSPACE = ?",
        (name,),
    )
    return bool(row and int(row[0]))


def ensure_vector_index(conn, table_name: str = TABLE) -> str:
    """Build Db2's approximate vector index over the fix memory, if it can.

    This one needs a word about page size, because the obvious attempt fails and
    the failure is not about vectors at all.

    Measured on CE 12.1.5: ``CREATE VECTOR INDEX ... WITH DISTANCE COSINE`` over
    a ``VECTOR(384, FLOAT32)`` column in ``USERSPACE1`` fails with **SQL0614N**,
    "the combined length of the specified columns is too long". USERSPACE1 has
    4K pages, which caps an index key at 1024 bytes; 384 FLOAT32 values are
    1536. The same statement succeeds in a 32K-page tablespace, where the cap is
    8192 (``SYSCAT.INDEXES.INDEXTYPE`` then reads ``VANN``).

    So the index is a property of where the table lives, and the table has to be
    placed before it is created -- see :func:`ensure_table`. ``CREATE BUFFERPOOL``
    needs an authority PortProof's owner identity deliberately does not hold, so
    the 32K tablespace is created by ``scripts/create_db2_users.sh`` as the
    instance owner.

    And even in that tablespace, this statement fails for ``PPOWN`` with
    **SQL0551N**: *Authorization ID "PPOWN". Operation: "CREATE TABLE". Object:
    "SYSIBM.AGT..."*. Building the index implicitly creates a helper table in
    the ``SYSIBM`` schema, which an owner that is deliberately not ``DBADM``
    cannot write to. Granting that for the sake of one index would undo the
    privilege split, so the index is built by
    ``scripts/create_vector_index.sh`` as the instance owner instead, and
    everything here degrades to exact vector search with a stated reason.

    The distance metric must match the one the queries use (COSINE, the same as
    ``DistanceStrategy.COSINE`` in :attr:`FixMemory.store`); an index built for
    another metric is simply never chosen.
    """
    table = table_name.split(".")[-1]
    try:
        db.execute(
            conn,
            f"CREATE VECTOR INDEX {VECTOR_INDEX} ON {table} (EMBEDDING) "
            "WITH DISTANCE COSINE",
        )
        return f"{VECTOR_INDEX}: created (approximate nearest neighbour, COSINE)"
    except db.Db2Error as exc:
        if exc.sqlcode == -601:
            return f"{VECTOR_INDEX}: already present"
        if exc.sqlcode == -614:
            return (
                f"{VECTOR_INDEX}: not created (SQLCODE=-614): a "
                f"{EMBEDDING_DIMENSIONS}-dimension FLOAT32 key is "
                f"{EMBEDDING_DIMENSIONS * 4} bytes and the table's tablespace "
                f"has 4K pages (1024-byte index key limit). Run "
                f"scripts/create_db2_users.sh to create the 32K "
                f"{VECTOR_TABLESPACE} tablespace, then re-run setup. Exact "
                "vector search is used meanwhile and is correct, just unindexed"
            )
        return f"{VECTOR_INDEX}: not available (SQLCODE={exc.sqlcode}); exact search is used"


def ensure_table(conn, embeddings: Any | None = None, table_name: str = TABLE) -> str:
    """Create the DB2VS table if it does not exist, and report its DDL shape.

    The table is pre-created in the 32K-page tablespace when that exists, with
    exactly the columns DB2VS expects, so that DB2VS adopts it instead of
    building its own in the 4K default -- which is the only reason the vector
    index can exist at all (see :func:`ensure_vector_index`). Where the
    tablespace is absent, DB2VS creates the table as it always did.
    """
    table = table_name.split(".")[-1]
    if _tablespace_available(conn, VECTOR_TABLESPACE):
        try:
            db.execute(
                conn,
                f"""
                CREATE TABLE {table} (
                  ID        CHAR(16) NOT NULL PRIMARY KEY,
                  TEXT      CLOB(1048576),
                  METADATA  BLOB(1048576),
                  EMBEDDING VECTOR({EMBEDDING_DIMENSIONS}, FLOAT32)
                ) IN {VECTOR_TABLESPACE}
                """,
            )
        except db.Db2Error as exc:
            if exc.sqlcode != -601:  # already exists is the normal case
                raise

    memory = FixMemory(conn, embeddings=embeddings, table_name=table_name)
    _ = memory.store  # DB2VS creates the table if it is still absent
    cols = db.fetch_all(
        conn,
        "SELECT COLNAME, TYPENAME, LENGTH FROM SYSCAT.COLUMNS "
        "WHERE TABSCHEMA = CURRENT SCHEMA AND TABNAME = ? ORDER BY COLNO",
        (table_name.split(".")[-1],),
    )
    return ", ".join(f"{c.strip()} {t.strip()}({l})" for c, t, l in cols)
