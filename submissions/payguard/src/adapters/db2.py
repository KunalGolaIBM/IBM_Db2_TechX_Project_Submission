"""IBM Db2 data layer for PayGuard.

Everything PayGuard knows lives in Db2:
  PG_SCAM_PATTERNS  known fraud playbooks + VECTOR embeddings (hybrid vector + SQL filter search)
  PG_ENTITIES       emails / phones / domains / wallets with BLOCKED / SUSPECT / TRUSTED status
  PG_REPORTS        community scam reports + VECTOR embeddings ("others reported this message")
  PG_SCREENINGS     every payment screened, its verdict, reasons (JSON) and PayPal order state
  PG_META           key/value settings (embedding model in use)
Views PG_V_ENTITY_RISK and PG_V_DAILY_VERDICTS feed the analyst console.
"""
from __future__ import annotations

import datetime as dt
import decimal
import json
import logging
import time
from contextvars import ContextVar
from contextlib import contextmanager
from typing import Any, Iterator

from config import settings
from adapters.embeddings import to_db2_vector
from pool import ConnectionPool

log = logging.getLogger("payguard.db")

TABLES = ["PG_SCREENINGS", "PG_REPORTS", "PG_ENTITIES", "PG_SCAM_PATTERNS", "SCAM_EXAMPLES", "PG_META"]
VIEWS = ["PG_V_ENTITY_RISK", "PG_V_DAILY_VERDICTS"]


def _py(v: Any) -> Any:
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (dt.datetime, dt.date)):
        return v.isoformat()
    return v


class Db2Repository:
    """Db2 data access; every transaction exclusively leases a pooled connection."""

    def __init__(self, conn_str: str | None = None, pool: ConnectionPool | None = None):
        self._conn_str = conn_str or settings.db2_conn_str
        self._transaction: ContextVar[Any] = ContextVar("db2_transaction", default=None)
        self.pool = pool or ConnectionPool(
            self._connect, settings.db2_pool_min, settings.db2_pool_max,
            settings.db2_pool_timeout, self._healthcheck,
        )

    def _connect(self):
        import ibm_db
        import ibm_db_dbi

        conn = ibm_db_dbi.connect(self._conn_str, "", "")
        conn.set_autocommit(False)
        # Applies to every statement, including statements issued by LangChain DB2VS.
        conn.set_option({ibm_db.SQL_ATTR_QUERY_TIMEOUT: settings.db2_query_timeout})
        return conn

    @staticmethod
    def _healthcheck(conn):
        cur = conn.cursor()
        try:
            cur.execute("SELECT 1 FROM SYSIBM.SYSDUMMY1")
            cur.fetchone()
        finally:
            cur.close()
            conn.rollback()

    def close(self) -> None:
        self.pool.close()

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        current = self._transaction.get()
        if current is not None:
            yield current
            return
        with self.pool.connection() as conn:
            token = self._transaction.set(conn)
            try:
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
            finally:
                self._transaction.reset(token)

    @contextmanager
    def _cursor(self) -> Iterator[Any]:
        with self.transaction() as conn:
            cur = conn.cursor()
            try:
                yield cur
            finally:
                cur.close()

    def query(self, sql: str, params: tuple | list = ()) -> list[dict]:
        with self._cursor() as cur:
            cur.execute(sql, tuple(params))
            if cur.description is None:
                return []
            cols = [d[0].lower() for d in cur.description]
            return [{c: _py(v) for c, v in zip(cols, row)} for row in cur.fetchall()]

    def execute(self, sql: str, params: tuple | list = ()) -> None:
        with self._cursor() as cur:
            cur.execute(sql, tuple(params))

    def ping(self) -> bool:
        return bool(self.query("SELECT 1 AS OK FROM SYSIBM.SYSDUMMY1"))

    # ------------------------------------------------------------------ schema
    def init_schema(self, dim: int, reset: bool = False) -> None:
        if reset:
            for v in VIEWS:
                self._try(f"DROP VIEW {v}")
            for t in TABLES:
                self._try(f"DROP TABLE {t}")
        from migrations import migrate

        migrate(self, dim)

    def init_examples(self, dim: int) -> None:
        self._try(f"""CREATE TABLE SCAM_EXAMPLES (
            ID CHAR(64) NOT NULL PRIMARY KEY,
            LABEL VARCHAR(64) NOT NULL,
            TEXT VARCHAR(4000) NOT NULL,
            SOURCE VARCHAR(512) NOT NULL,
            METADATA BLOB,
            EMBEDDING VECTOR({int(dim)}, FLOAT32)
        )""", ignore=("42710",))

    def example_ids(self) -> set[str]:
        return {r["id"].strip() for r in self.query("SELECT ID FROM SCAM_EXAMPLES")}

    def delete_examples(self, row_ids: list[str]) -> None:
        with self.transaction():
            for row_id in row_ids:
                self.execute("DELETE FROM SCAM_EXAMPLES WHERE ID = ?", (row_id,))

    def insert_example(self, row_id: str, row: dict, vec: list[float]) -> None:
        metadata = json.dumps({"id": row_id, "label": row["label"], "source": row["source"]})
        self.execute(
            f"""INSERT INTO SCAM_EXAMPLES (ID, LABEL, TEXT, SOURCE, METADATA, EMBEDDING)
                SELECT ?, ?, ?, ?, SYSTOOLS.JSON2BSON(?),
                       VECTOR(CAST(? AS CLOB(100000)), {len(vec)}, FLOAT32)
                FROM SYSIBM.SYSDUMMY1 WHERE NOT EXISTS
                    (SELECT 1 FROM SCAM_EXAMPLES WHERE ID = ?)""",
            (row_id, row["label"], row["text"], row["source"], metadata, to_db2_vector(vec), row_id),
        )

    def search_examples(self, vec: list[float], k: int = 3) -> list[dict]:
        """LangChain DB2VS borrows exclusively from the repository's own pool."""
        from embeddings import get_embedder
        from langchain_db2_tools import example_vector_store

        with self.pool.connection() as conn:
            # A DB2VS instance is connection-bound. Reuse it only on that same
            # exclusive lease; dropped connections naturally get a fresh store.
            store = getattr(conn, "_payguard_example_store", None)
            if store is None:
                store = example_vector_store(conn, get_embedder())
                conn._payguard_example_store = store
            pairs = store.similarity_search_by_vector_with_relevance_scores(vec, k=max(1, int(k)))
            return [{**doc.metadata, "text": doc.page_content,
                     "similarity": round(1.0 - float(distance), 4)} for doc, distance in pairs]

    def _try(self, sql: str, ignore: tuple[str, ...] = ("42704",)) -> None:
        try:
            self.execute(sql)
        except Exception as exc:  # ibm_db_dbi raises ProgrammingError / Error
            if any(code in str(exc) for code in ignore):
                log.debug("ignored: %s", exc)
            else:
                raise

    def get_meta(self, key: str) -> str | None:
        rows = self.query("SELECT META_VALUE FROM PG_META WHERE META_KEY = ?", (key,))
        return rows[0]["meta_value"] if rows else None

    def set_meta(self, key: str, value: str) -> None:
        self.execute(
            """MERGE INTO PG_META T
               USING (VALUES (CAST(? AS VARCHAR(64)), CAST(? AS VARCHAR(512)))) AS S(K, V)
               ON T.META_KEY = S.K
               WHEN MATCHED THEN UPDATE SET META_VALUE = S.V
               WHEN NOT MATCHED THEN INSERT (META_KEY, META_VALUE) VALUES (S.K, S.V)""",
            (key, value),
        )

    # --------------------------------------------------------- scam patterns
    def insert_pattern(self, p: dict, vec: list[float]) -> int:
        rows = self.query(
            f"""SELECT ID FROM FINAL TABLE (
                  INSERT INTO PG_SCAM_PATTERNS
                    (TITLE, CATEGORY, CHANNEL, REGION, SEVERITY, DESCRIPTION, RED_FLAGS, ADVICE, EMBEDDING)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, VECTOR(?, {len(vec)}, FLOAT32)))""",
            (p["title"], p["category"], p["channel"], p.get("region", "GLOBAL"), p["severity"],
             p["description"], p.get("red_flags", ""), p.get("advice", ""), to_db2_vector(vec)),
        )
        return rows[0]["id"]

    def search_patterns(self, vec: list[float], region: str = "GLOBAL", k: int = 5) -> list[dict]:
        """Hybrid search: relational filter on REGION + cosine VECTOR_DISTANCE ranking in Db2."""
        v = to_db2_vector(vec)
        rows = self.query(
            f"""SELECT ID, TITLE, CATEGORY, CHANNEL, REGION, SEVERITY, DESCRIPTION, RED_FLAGS, ADVICE,
                       VECTOR_DISTANCE(EMBEDDING, VECTOR(CAST(? AS CLOB(100000)), {len(vec)}, FLOAT32), COSINE) AS DISTANCE
                FROM PG_SCAM_PATTERNS
                WHERE REGION IN ('GLOBAL', ?)
                ORDER BY DISTANCE
                FETCH FIRST {int(k)} ROWS ONLY""",
            (v, region.upper()),
        )
        for r in rows:
            r["similarity"] = round(1.0 - float(r.pop("distance")), 4)
        return rows

    def count_patterns(self) -> int:
        return self.query("SELECT COUNT(*) AS N FROM PG_SCAM_PATTERNS")[0]["n"]

    # --------------------------------------------------------------- entities
    def upsert_entity(self, etype: str, value: str, status: str = "SUSPECT",
                      notes: str = "", count_report: bool = True) -> int:
        """MERGE an entity. Each community report bumps REPORT_COUNT; 3+ reports auto-escalate to BLOCKED."""
        for attempt in range(5):
            try:
                with self.transaction():
                    return self._merge_entity(etype, value, status, notes, count_report)
            except Exception as exc:
                if self._transaction.get() is not None or not self._retryable(exc) or attempt == 4:
                    raise
                time.sleep(0.01 * (attempt + 1))
        raise RuntimeError("unreachable")

    @staticmethod
    def _retryable(exc: Exception) -> bool:
        return any(code in str(exc) for code in ("23505", "40001", "57033"))

    def _merge_entity(self, etype, value, status, notes, count_report):
        inc = 1 if count_report else 0
        self.execute(
            """MERGE INTO PG_ENTITIES T
               USING (VALUES (CAST(? AS VARCHAR(20)), CAST(? AS VARCHAR(320)),
                              CAST(? AS VARCHAR(12)), CAST(? AS VARCHAR(500)))) AS S(ETYPE, EVALUE, ESTATUS, ENOTES)
               ON T.ENTITY_TYPE = S.ETYPE AND T.ENTITY_VALUE = S.EVALUE
               WHEN MATCHED THEN UPDATE SET
                    REPORT_COUNT = T.REPORT_COUNT + ?,
                    LAST_SEEN = CURRENT TIMESTAMP,
                    STATUS = CASE
                        WHEN S.ESTATUS = 'BLOCKED' THEN 'BLOCKED'
                        WHEN T.STATUS = 'TRUSTED' THEN 'TRUSTED'
                        WHEN T.REPORT_COUNT + ? >= 3 THEN 'BLOCKED'
                        ELSE T.STATUS END
               WHEN NOT MATCHED THEN INSERT (ENTITY_TYPE, ENTITY_VALUE, STATUS, REPORT_COUNT, NOTES)
                    VALUES (S.ETYPE, S.EVALUE, S.ESTATUS, ?, S.ENOTES)""",
            (etype, value.lower(), status, notes[:500], inc, inc, inc),
        )
        return self.query(
            "SELECT ID FROM PG_ENTITIES WHERE ENTITY_TYPE = ? AND ENTITY_VALUE = ?", (etype, value.lower())
        )[0]["id"]

    def lookup_entities(self, entities: list[tuple[str, str]]) -> list[dict]:
        if not entities:
            return []
        clauses = " OR ".join(["(V.ENTITY_TYPE = ? AND V.ENTITY_VALUE = ?)"] * len(entities))
        params: list[str] = []
        for t, v in entities:
            params += [t, v.lower()]
        return self.query(
            f"""SELECT V.ENTITY_TYPE, V.ENTITY_VALUE, V.STATUS, V.REPORT_COUNT, V.REPORTED_LOSS, V.LAST_REPORT_AT,
                       E.NOTES
                FROM PG_V_ENTITY_RISK V JOIN PG_ENTITIES E ON E.ID = V.ID
                WHERE {clauses}""",
            params,
        )

    # ---------------------------------------------------------------- reports
    def add_report(self, entity_id: int, reporter: str, category: str, amount: float,
                   currency: str, narrative: str, vec: list[float]) -> int:
        rows = self.query(
            f"""SELECT ID FROM FINAL TABLE (
                  INSERT INTO PG_REPORTS (ENTITY_ID, REPORTER, CATEGORY, AMOUNT, CURRENCY, NARRATIVE, EMBEDDING)
                  VALUES (?, ?, ?, ?, ?, ?, VECTOR(?, {len(vec)}, FLOAT32)))""",
            (entity_id, reporter[:100], category, amount, currency, narrative[:2000], to_db2_vector(vec)),
        )
        return rows[0]["id"]

    def search_reports(self, vec: list[float], k: int = 3) -> list[dict]:
        v = to_db2_vector(vec)
        rows = self.query(
            f"""SELECT R.ID, R.CATEGORY, R.AMOUNT, R.CURRENCY, R.NARRATIVE, R.CREATED_AT,
                       E.ENTITY_TYPE, E.ENTITY_VALUE, E.STATUS,
                       VECTOR_DISTANCE(R.EMBEDDING, VECTOR(CAST(? AS CLOB(100000)), {len(vec)}, FLOAT32), COSINE) AS DISTANCE
                FROM PG_REPORTS R JOIN PG_ENTITIES E ON E.ID = R.ENTITY_ID
                ORDER BY DISTANCE
                FETCH FIRST {max(1, int(k))} ROWS ONLY""",
            (v,),
        )
        for r in rows:
            r["similarity"] = round(1.0 - float(r.pop("distance")), 4)
        return rows

    # ------------------------------------------------------------- screenings
    def payee_velocity(self, payee_email: str, hours: int = 24) -> dict:
        rows = self.query(
            """SELECT COUNT(*) AS ATTEMPTS,
                       COALESCE(SUM(CASE WHEN VERDICT = 'BLOCK' THEN 1 ELSE 0 END), 0) AS BLOCKED,
                       COALESCE(SUM(AMOUNT), 0) AS TOTAL_AMOUNT
                FROM PG_SCREENINGS
                WHERE PAYEE_EMAIL = ? AND CREATED_AT > CURRENT TIMESTAMP - ? HOURS""",
            (payee_email.lower(), max(1, min(8760, int(hours)))),
        )
        return rows[0]

    def insert_screening(self, s: dict) -> int:
        rows = self.query(
            """SELECT ID FROM FINAL TABLE (
                 INSERT INTO PG_SCREENINGS (MERCHANT, PAYEE_EMAIL, AMOUNT, CURRENCY, PAYMENT_METHOD, MESSAGE,
                                            RISK_SCORE, VERDICT, TOP_CATEGORY, REASONS_JSON, AI_SUMMARY)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?))""",
            (s.get("merchant", "")[:200], (s.get("payee_email") or "").lower()[:320], s.get("amount", 0),
             s.get("currency", "USD"), s.get("payment_method", "")[:40], (s.get("message") or "")[:4000],
             s["risk_score"], s["verdict"], s.get("top_category"), json.dumps(s.get("reasons", [])),
             (s.get("ai_summary") or "")[:4000]),
        )
        return rows[0]["id"]

    def update_screening_ai(self, screening_id: int, summary: str, risk_score: int, verdict: str) -> None:
        self.execute(
            "UPDATE PG_SCREENINGS SET AI_SUMMARY = ?, RISK_SCORE = ?, VERDICT = ? WHERE ID = ?",
            (summary[:4000], risk_score, verdict, screening_id),
        )

    def update_screening_paypal(self, screening_id: int, order_id: str, status: str) -> None:
        self.execute(
            "UPDATE PG_SCREENINGS SET PAYPAL_ORDER_ID = ?, PAYPAL_STATUS = ? WHERE ID = ?",
            (order_id, status, screening_id),
        )

    def get_screening(self, screening_id: int) -> dict | None:
        rows = self.query(
            """SELECT ID, CREATED_AT, MERCHANT, PAYEE_EMAIL, AMOUNT, CURRENCY, PAYMENT_METHOD, RISK_SCORE,
                      VERDICT, TOP_CATEGORY, REASONS_JSON, AI_SUMMARY, PAYPAL_ORDER_ID, PAYPAL_STATUS
               FROM PG_SCREENINGS WHERE ID = ?""",
            (screening_id,),
        )
        if not rows:
            return None
        row = rows[0]
        row["reasons"] = json.loads(row.pop("reasons_json") or "[]")
        return row

    def recent_screenings(self, n: int = 15) -> list[dict]:
        return self.query(
            f"""SELECT ID, CREATED_AT, MERCHANT, PAYEE_EMAIL, AMOUNT, CURRENCY, RISK_SCORE, VERDICT,
                       TOP_CATEGORY, PAYPAL_STATUS
                FROM PG_SCREENINGS ORDER BY CREATED_AT DESC FETCH FIRST {int(n)} ROWS ONLY"""
        )

    # ------------------------------------------------------------------ stats
    def stats(self) -> dict:
        totals = self.query(
            """SELECT COUNT(*) AS SCREENINGS,
                      COALESCE(SUM(CASE WHEN VERDICT = 'BLOCK'  THEN 1 ELSE 0 END), 0) AS BLOCKED,
                      COALESCE(SUM(CASE WHEN VERDICT = 'REVIEW' THEN 1 ELSE 0 END), 0) AS REVIEWED,
                      COALESCE(SUM(CASE WHEN VERDICT = 'ALLOW'  THEN 1 ELSE 0 END), 0) AS ALLOWED,
                      COALESCE(SUM(CASE WHEN VERDICT = 'BLOCK'  THEN AMOUNT ELSE 0 END), 0) AS MONEY_PROTECTED
               FROM PG_SCREENINGS"""
        )[0]
        categories = self.query(
            """SELECT TOP_CATEGORY AS CATEGORY, COUNT(*) AS N
               FROM PG_SCREENINGS WHERE VERDICT <> 'ALLOW' AND TOP_CATEGORY IS NOT NULL
               GROUP BY TOP_CATEGORY ORDER BY N DESC FETCH FIRST 6 ROWS ONLY"""
        )
        top_entities = self.query(
            """SELECT ENTITY_TYPE, ENTITY_VALUE, STATUS, REPORT_COUNT, REPORTED_LOSS
               FROM PG_V_ENTITY_RISK WHERE STATUS <> 'TRUSTED'
               ORDER BY REPORT_COUNT DESC, REPORTED_LOSS DESC FETCH FIRST 6 ROWS ONLY"""
        )
        daily = self.query(
            """SELECT SCREEN_DAY, VERDICT, SCREENINGS FROM PG_V_DAILY_VERDICTS
               WHERE SCREEN_DAY > CURRENT DATE - 14 DAYS ORDER BY SCREEN_DAY"""
        )
        kb = self.query(
            """SELECT (SELECT COUNT(*) FROM PG_SCAM_PATTERNS) AS PATTERNS,
                      (SELECT COUNT(*) FROM PG_ENTITIES) AS ENTITIES,
                      (SELECT COUNT(*) FROM PG_REPORTS) AS REPORTS
               FROM SYSIBM.SYSDUMMY1"""
        )[0]
        return {"totals": totals, "categories": categories, "top_entities": top_entities,
                "daily": daily, "knowledge_base": kb}

    # --------------------------------------------------------- analyst (NLâ†’SQL)
    def schema_description(self) -> str:
        rows = self.query(
            """SELECT TABNAME, COLNAME, TYPENAME
               FROM SYSCAT.COLUMNS
               WHERE TABSCHEMA = CURRENT SCHEMA AND TABNAME LIKE 'PG\\_%' ESCAPE '\\'
                 AND TABNAME <> 'PG_META' AND COLNAME <> 'EMBEDDING'
               ORDER BY TABNAME, COLNO"""
        )
        tables: dict[str, list[str]] = {}
        for r in rows:
            tables.setdefault(r["tabname"], []).append(f'{r["colname"]} {r["typename"]}')
        return "\n".join(f"{t}({', '.join(cols)})" for t, cols in tables.items())

    def run_readonly(self, sql: str) -> dict:
        """Read-only analyst query: guard again at the trust boundary, then rollback."""
        from analyst import guard_sql

        safe = guard_sql(sql)
        with self.pool.connection() as conn:
            cur = conn.cursor()
            try:
                cur.execute(safe)
                cols = [d[0].lower() for d in cur.description] if cur.description else []
                rows = [[_py(v) for v in row] for row in cur.fetchmany(100)] if cols else []
                return {"columns": cols, "rows": rows}
            finally:
                cur.close()
                conn.rollback()

    def file_report(self, etype: str, value: str, reporter: str, category: str, amount: float,
                    currency: str, narrative: str, vec: list[float]) -> dict:
        """One atomic unit: MERGE, report insert, and result. No partial report counts."""
        for attempt in range(5):
            try:
                with self.transaction():
                    eid = self._merge_entity(etype, value, "SUSPECT", "", True)
                    rid = self.add_report(eid, reporter, category, amount, currency, narrative, vec)
                    rows = self.lookup_entities([(etype, value)])
                    return {"report_id": rid, "entity": rows[0] if rows else None}
            except Exception as exc:
                if not self._retryable(exc) or attempt == 4:
                    raise
                time.sleep(0.01 * (attempt + 1))
        raise RuntimeError("unreachable")
