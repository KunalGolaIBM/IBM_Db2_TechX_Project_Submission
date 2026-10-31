"""IBM Db2 Connection Management and Transaction Handling.

Encapsulates low-level ibm_db driver operations, connection pooling/lifecycle,
parameterized statement execution, and atomic transaction context management.
"""

from contextlib import contextmanager
from typing import Any, Generator, Optional

try:
    import ibm_db
except ImportError:  # pragma: no cover
    ibm_db = None  # type: ignore

from backend.app.db2.config import Db2Config


class Db2Error(Exception):
    """Base exception for all Db2 operations."""
    pass


class Db2ConnectionError(Db2Error):
    """Raised when failing to establish or maintain connection to IBM Db2."""
    pass


class Db2ExecutionError(Db2Error):
    """Raised when statement preparation, binding, or execution fails."""
    pass


class Db2ConnectionManager:
    """Manages connections, execution lifecycle, and transactions with IBM Db2."""

    def __init__(self, config: Optional[Db2Config] = None) -> None:
        self.config = config or Db2Config.from_env()

    def get_driver(self) -> Any:
        """Validate and return the loaded ibm_db driver module."""
        if ibm_db is None:
            raise Db2ConnectionError(
                "The official 'ibm_db' Python driver is not installed. "
                "Install it using: pip install ibm_db"
            )
        return ibm_db

    def connect(self) -> Any:
        """Open a new connection to IBM Db2 using configured credentials."""
        driver = self.get_driver()
        conn_string = self.config.get_connection_string()
        try:
            conn = driver.connect(conn_string, "", "")
            if not conn:
                err_msg = driver.conn_errormsg() if hasattr(driver, "conn_errormsg") else "Unknown connection error"
                raise Db2ConnectionError(f"Failed to connect to IBM Db2: {err_msg}")
            return conn
        except Exception as exc:
            if isinstance(exc, Db2ConnectionError):
                raise
            raise Db2ConnectionError(f"Db2 connection attempt failed: {str(exc)}") from exc

    def close(self, conn: Any) -> None:
        """Safely close an open Db2 connection."""
        driver = self.get_driver()
        try:
            if conn:
                driver.close(conn)
        except Exception:
            pass

    def check_connection(self) -> bool:
        """Probe Db2 connectivity using the standard dummy table."""
        try:
            conn = self.connect()
            try:
                driver = self.get_driver()
                stmt = driver.prepare(conn, "SELECT 1 FROM SYSIBM.SYSDUMMY1")
                if stmt:
                    res = driver.execute(stmt)
                    return bool(res)
                return False
            finally:
                self.close(conn)
        except Exception:
            return False

    @contextmanager
    def transaction(self, conn: Optional[Any] = None) -> Generator[Any, None, None]:
        """Context manager providing ACID transaction boundary (commit on success, rollback on error)."""
        driver = self.get_driver()
        owned_connection = False

        if conn is None:
            conn = self.connect()
            owned_connection = True

        try:
            # Turn off autocommit for atomic multi-statement transaction
            driver.autocommit(conn, driver.SQL_AUTOCOMMIT_OFF)
            yield conn
            driver.commit(conn)
        except Exception as exc:
            try:
                driver.rollback(conn)
            except Exception:
                pass
            raise exc
        finally:
            try:
                # Restore autocommit mode before returning or closing
                driver.autocommit(conn, driver.SQL_AUTOCOMMIT_ON)
            except Exception:
                pass
            if owned_connection:
                self.close(conn)

    def execute_statement(self, conn: Any, sql: str, params: Optional[tuple] = None) -> Any:
        """Prepare and execute a parameterized SQL statement with Db2."""
        driver = self.get_driver()
        try:
            stmt = driver.prepare(conn, sql)
            if not stmt:
                err_msg = driver.conn_errormsg(conn) if hasattr(driver, "conn_errormsg") else "Unknown prepare error"
                raise Db2ExecutionError(f"Db2 prepare failed: {err_msg} | SQL: {sql}")

            if params is not None:
                # Convert list/tuple values to ensure proper C driver binding
                res = driver.execute(stmt, tuple(params))
            else:
                res = driver.execute(stmt)

            if not res:
                err_msg = driver.stmt_errormsg(stmt) if hasattr(driver, "stmt_errormsg") else "Unknown execution error"
                raise Db2ExecutionError(f"Db2 execution failed: {err_msg} | SQL: {sql} | Params: {params}")

            return stmt
        except Exception as exc:
            if isinstance(exc, Db2ExecutionError):
                raise
            raise Db2ExecutionError(f"Error executing statement: {str(exc)} | SQL: {sql}") from exc

    def fetch_all_assoc(self, stmt: Any) -> list[dict[str, Any]]:
        """Fetch all rows from an executed statement as lowercase-keyed dictionaries."""
        driver = self.get_driver()
        rows: list[dict[str, Any]] = []
        try:
            row = driver.fetch_assoc(stmt)
            while row:
                rows.append({str(k).lower(): v for k, v in row.items()})
                row = driver.fetch_assoc(stmt)
        except Exception as exc:
            raise Db2ExecutionError(f"Error fetching result rows: {str(exc)}") from exc
        return rows

    def fetch_one_assoc(self, stmt: Any) -> Optional[dict[str, Any]]:
        """Fetch a single row from an executed statement as a lowercase-keyed dictionary."""
        driver = self.get_driver()
        try:
            row = driver.fetch_assoc(stmt)
            if row:
                return {str(k).lower(): v for k, v in row.items()}
            return None
        except Exception as exc:
            raise Db2ExecutionError(f"Error fetching result row: {str(exc)}") from exc
