"""IBM Db2 implementation of the repository interface (ibm_db / ibm_db_dbi).

* One DB-API connection per thread (ibm_db connections are not thread-safe).
* Autocommit is off; every write is committed explicitly or inside transaction().
* All statements use '?' parameter markers — user input is never interpolated.
"""
from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from typing import Any, Iterator, Sequence

from app.core.config import Settings

from .base import Database, DatabaseError, IntegrityViolation, rows_to_dicts, split_sql

log = logging.getLogger("recallguard.db2")

# SQLSTATE class 23 = integrity constraint violation (PK/FK/UNIQUE/CHECK)
_INTEGRITY_SQLSTATES = ("23",)


def _wrap(exc: Exception) -> DatabaseError:
    msg = str(exc)
    if any(f"SQLSTATE={s}" in msg for s in _INTEGRITY_SQLSTATES) or "SQL0803N" in msg or "SQL0530N" in msg or "SQL0545N" in msg:
        return IntegrityViolation(msg)
    return DatabaseError(msg)


class Db2Database(Database):
    mode = "db2"
    label = "IBM Db2"

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        try:
            import ibm_db  # noqa: F401
            import ibm_db_dbi  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise DatabaseError("ibm_db is not installed: pip install ibm_db") from exc
        self.settings = settings
        self._local = threading.local()

    # ---------------------------------------------------------------- connect
    def _conn_str(self) -> str:
        s = self.settings
        parts = [
            f"DATABASE={s.db2_database}",
            f"HOSTNAME={s.db2_host}",
            f"PORT={s.db2_port}",
            "PROTOCOL=TCPIP",
            f"UID={s.db2_user}",
            f"PWD={s.db2_password}",
        ]
        if s.db2_security:
            parts.append(f"SECURITY={s.db2_security}")
        if s.db2_schema:
            parts.append(f"CURRENTSCHEMA={s.db2_schema.upper()}")
        return ";".join(parts) + ";"

    def _connect(self):
        import ibm_db_dbi

        last: Exception | None = None
        for attempt in range(3):
            try:
                conn = ibm_db_dbi.connect(self._conn_str(), "", "")
                conn.set_autocommit(False)
                return conn
            except Exception as exc:  # driver raises its own hierarchy
                last = exc
                time.sleep(0.5 * (attempt + 1))
        raise DatabaseError(f"Cannot connect to IBM Db2 at {self.settings.db2_host}:{self.settings.db2_port}/"
                            f"{self.settings.db2_database}: {last}")

    @property
    def conn(self):
        c = getattr(self._local, "conn", None)
        if c is None:
            c = self._connect()
            self._local.conn = c
        return c

    def raw_connection(self):
        """Expose the ibm_db_dbi connection (used by langchain-db2 DB2VS)."""
        return self.conn

    # ---------------------------------------------------------------- execute
    def _in_tx(self) -> bool:
        return getattr(self._tx, "depth", 0) > 0

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        cur = self.conn.cursor()
        try:
            cur.execute(sql, tuple(params))
            cols = [d[0] for d in (cur.description or [])]
            rows = cur.fetchall() if cols else []
            if not self._in_tx():
                self.conn.commit()  # release read locks
            return rows_to_dicts(cols, rows)
        except Exception as exc:
            self._reset_on_failure()
            raise _wrap(exc) from exc
        finally:
            try:
                cur.close()
            except Exception:
                pass

    def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        cur = self.conn.cursor()
        try:
            cur.execute(sql, tuple(params))
            n = cur.rowcount
            if not self._in_tx():
                self.conn.commit()
            return n
        except Exception as exc:
            self._reset_on_failure()
            raise _wrap(exc) from exc
        finally:
            try:
                cur.close()
            except Exception:
                pass

    def executemany(self, sql: str, seq: Sequence[Sequence[Any]]) -> None:
        cur = self.conn.cursor()
        try:
            cur.executemany(sql, [tuple(p) for p in seq])
            if not self._in_tx():
                self.conn.commit()
        except Exception as exc:
            self._reset_on_failure()
            raise _wrap(exc) from exc
        finally:
            cur.close()

    def execute_script(self, script: str) -> int:
        n = 0
        with self.transaction():
            for stmt in split_sql(script):
                self.execute(stmt)
                n += 1
        return n

    def _reset_on_failure(self) -> None:
        if not self._in_tx():
            try:
                self.conn.rollback()
            except Exception:
                self._local.conn = None

    @contextmanager
    def transaction(self) -> Iterator[None]:
        depth = getattr(self._tx, "depth", 0)
        self._tx.depth = depth + 1
        try:
            yield
            if depth == 0:
                self.conn.commit()
        except Exception:
            if depth == 0:
                try:
                    self.conn.rollback()
                except Exception:
                    self._local.conn = None
            raise
        finally:
            self._tx.depth = depth

    # ---------------------------------------------------------------- misc
    def table_exists(self, name: str) -> bool:
        row = self.query_one(
            "SELECT COUNT(*) AS n FROM SYSCAT.TABLES WHERE TABNAME = ? AND TABSCHEMA = CURRENT SCHEMA",
            (name.upper(),),
        )
        return bool(row and row["n"])

    def ping(self) -> dict[str, Any]:
        t0 = time.perf_counter()
        row = self.query_one(
            "SELECT SERVICE_LEVEL, FIXPACK_NUM FROM TABLE(SYSPROC.ENV_GET_INST_INFO()) AS t"
        )
        return {
            "ok": True,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
            "server": (row or {}).get("service_level"),
            "fixpack": (row or {}).get("fixpack_num"),
        }

    def supports_vector(self) -> bool:
        """Probe for the Db2 12.1.2+ VECTOR type (needed by langchain-db2 DB2VS)."""
        try:
            self.query("VALUES VECTOR('[1.0, 2.0]', 2, FLOAT32)")
            return True
        except DatabaseError:
            return False

    def close(self) -> None:
        c = getattr(self._local, "conn", None)
        if c is not None:
            try:
                c.close()
            finally:
                self._local.conn = None
