"""IBM Db2 Connection Manager and Connection Pooling.

Handles thread-safe connection pooling, automated retries with exponential backoff,
parameterized query preparation, transaction boundaries, and seamless failover
to MockDb2Sandbox when live credentials are unconfigured or offline.
"""

from __future__ import annotations

import contextlib
import logging
import threading
import time
from typing import Any, Dict, Generator, List, Optional, Tuple, Union

from db2_toolkit.config import Db2Config, get_db2_config
from db2_toolkit.mock_db2_sandbox import MockDb2Sandbox

logger = logging.getLogger("db2_toolkit.connection")

# Check if native ibm_db is installed
try:
    import ibm_db  # type: ignore[import-untyped]
    import ibm_db_dbi  # type: ignore[import-untyped]
    HAS_IBM_DB = True
except ImportError:
    ibm_db = None
    ibm_db_dbi = None
    HAS_IBM_DB = False


class Db2ConnectionManager:
    """Thread-safe Connection Manager for IBM Db2 with Mock Sandbox Fallback."""

    def __init__(self, config: Optional[Db2Config] = None) -> None:
        self.config = config or get_db2_config()
        self._lock = threading.Lock()
        self._pool: List[Any] = []
        self._active_connections = 0
        self._is_mock_mode = False
        self._mock_sandbox: Optional[MockDb2Sandbox] = None

        # Check driver availability and test live connection
        if not HAS_IBM_DB or self.config.mock_fallback:
            self._init_connection_mode()

    def _init_connection_mode(self) -> None:
        """Determines if live Db2 is reachable or switches to mock sandbox."""
        if not HAS_IBM_DB:
            logger.info("ibm_db driver not found in environment; activating MockDb2Sandbox.")
            self._is_mock_mode = True
            self._mock_sandbox = MockDb2Sandbox(dbname=self.config.database)
            return

        # If ibm_db is present, try testing live connection
        try:
            conn_str = self.config.build_connection_string()
            test_conn = ibm_db.connect(conn_str, "", "")
            ibm_db.close(test_conn)
            logger.info("Successfully established connection to IBM Db2 at %s:%s", self.config.hostname, self.config.port)
            self._is_mock_mode = False
        except Exception as exc:
            if self.config.mock_fallback:
                logger.warning(
                    "Live IBM Db2 connection failed (%s); seamlessly falling back to MockDb2Sandbox.", exc
                )
                self._is_mock_mode = True
                self._mock_sandbox = MockDb2Sandbox(dbname=self.config.database)
            else:
                raise

    @property
    def is_mock(self) -> bool:
        """Whether current manager operates against the mock engine."""
        return self._is_mock_mode

    @property
    def sandbox(self) -> MockDb2Sandbox:
        """Returns the underlying mock sandbox instance if in mock mode."""
        if not self._mock_sandbox:
            self._mock_sandbox = MockDb2Sandbox(dbname=self.config.database)
        return self._mock_sandbox

    def _acquire_raw_connection(self) -> Any:
        """Acquires a raw connection from the pool or opens a new one."""
        with self._lock:
            if self._pool:
                return self._pool.pop()

        if self._is_mock_mode:
            return self.sandbox

        conn_str = self.config.build_connection_string()
        return ibm_db_dbi.connect(conn_str, "", "")

    def _release_raw_connection(self, conn: Any) -> None:
        """Returns a connection to the pool or closes it if pool is full."""
        if self._is_mock_mode:
            return

        with self._lock:
            if len(self._pool) < self.config.pool_size:
                self._pool.append(conn)
            else:
                try:
                    conn.close()
                except Exception:
                    pass

    @contextlib.contextmanager
    def get_connection(self) -> Generator[Any, None, None]:
        """Context manager yielding a healthy connection with automatic release."""
        conn = self._acquire_raw_connection()
        try:
            yield conn
        finally:
            self._release_raw_connection(conn)

    def execute_query(
        self,
        sql: str,
        params: Optional[Union[Tuple[Any, ...], List[Any], Dict[str, Any]]] = None,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """Executes a SELECT query with retry logic and returns list of dict records."""
        if self._is_mock_mode:
            return self.sandbox.execute_query(sql, params)

        last_error = None
        for attempt in range(max_retries):
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    if params:
                        cursor.execute(sql, params)
                    else:
                        cursor.execute(sql)

                    columns = [desc[0] for desc in cursor.description] if cursor.description else []
                    rows = cursor.fetchall()
                    cursor.close()
                    return [dict(zip(columns, row)) for row in rows]
            except Exception as err:
                last_error = err
                time.sleep(backoff_factor * (2**attempt))

        raise RuntimeError(f"Db2 query execution failed after {max_retries} retries: {last_error}")

    def execute_statement(
        self,
        sql: str,
        params: Optional[Union[Tuple[Any, ...], List[Any], Dict[str, Any]]] = None,
    ) -> int:
        """Executes a DDL or DML statement (INSERT, UPDATE, DELETE) and returns affected row count."""
        if self._is_mock_mode:
            return self.sandbox.execute_statement(sql, params)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            rowcount = cursor.rowcount
            conn.commit()
            cursor.close()
            return rowcount

    @contextlib.contextmanager
    def transaction(self) -> Generator[Any, None, None]:
        """Provides an atomic transaction block with commit/rollback."""
        if self._is_mock_mode:
            yield self.sandbox
            return

        with self.get_connection() as conn:
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def ping(self) -> Dict[str, Any]:
        """Health check verifying database responsiveness."""
        start = time.perf_counter()
        if self._is_mock_mode:
            res = self.sandbox.execute_query("SELECT 1 FROM SYSIBM.SYSDUMMY1")
            elapsed = (time.perf_counter() - start) * 1000
            return {
                "status": "healthy",
                "mode": "mock_sandbox",
                "database": self.config.database,
                "latency_ms": round(elapsed, 2),
                "driver": "MockDb2Sandbox",
                "tables_count": len(self.sandbox.list_tables()),
            }

        try:
            self.execute_query("SELECT 1 FROM SYSIBM.SYSDUMMY1")
            elapsed = (time.perf_counter() - start) * 1000
            return {
                "status": "healthy",
                "mode": "live",
                "database": self.config.database,
                "hostname": self.config.hostname,
                "latency_ms": round(elapsed, 2),
                "driver": "ibm_db",
            }
        except Exception as exc:
            return {
                "status": "unhealthy",
                "mode": "live",
                "error": str(exc),
                "driver": "ibm_db",
            }

    def get_tables(self) -> List[str]:
        """Lists user tables."""
        if self._is_mock_mode:
            return self.sandbox.list_tables()

        sql = "SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TYPE = 'T' ORDER BY TABNAME"
        res = self.execute_query(sql, (self.config.uid.upper(),))
        return [row["TABNAME"] for row in res]

    def get_table_schema(self, table_name: str) -> List[Dict[str, str]]:
        """Describes columns and data types for a given table."""
        if self._is_mock_mode:
            return self.sandbox.describe_table(table_name)

        sql = (
            "SELECT COLNAME, TYPENAME, LENGTH, SCALE, NULLS "
            "FROM SYSCAT.COLUMNS "
            "WHERE TABNAME = ? ORDER BY COLNO"
        )
        return self.execute_query(sql, (table_name.upper(),))


_GLOBAL_POOL: Optional[Db2ConnectionManager] = None


def get_db2_pool(config: Optional[Db2Config] = None) -> Db2ConnectionManager:
    """Returns singleton Db2ConnectionManager instance."""
    global _GLOBAL_POOL
    if _GLOBAL_POOL is None:
        _GLOBAL_POOL = Db2ConnectionManager(config)
    return _GLOBAL_POOL

