"""
ClaimGuard AI - IBM Db2 Connection Manager
Handles IBM Db2 connections via official ibm_db driver, parameterized SQL execution,
atomic transactions, connection pooling, and transparent health monitoring.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from ..config import settings

# On Windows, register clidriver DLL paths if present
if sys.platform == "win32":
    appdata = os.environ.get("APPDATA", "")
    py_ver = f"Python{sys.version_info.major}{sys.version_info.minor}"
    potential_clidriver_dirs = [
        Path(appdata) / "Python" / py_ver / "site-packages" / "clidriver",
        Path(sys.prefix) / "Lib" / "site-packages" / "clidriver",
        Path(__file__).resolve().parent.parent.parent.parent / ".venv" / "Lib" / "site-packages" / "clidriver",
    ]
    for cli_p in potential_clidriver_dirs:
        bin_dir = cli_p / "bin"
        lib_dir = cli_p / "lib"
        if bin_dir.is_dir():
            os.environ["PATH"] = f"{bin_dir};{lib_dir};" + os.environ.get("PATH", "")
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(str(bin_dir))
                    os.add_dll_directory(str(lib_dir))
                except Exception:
                    pass
            break

logger = logging.getLogger("claimguard.db2")

# Attempt importing ibm_db safely
try:
    import ibm_db
    IBM_DB_AVAILABLE = True
except ImportError:
    ibm_db = None
    IBM_DB_AVAILABLE = False
    logger.warning("ibm_db driver is not installed. Run 'pip install ibm_db'.")


NUMERIC_FLOAT_FIELDS = {
    "RISK_SCORE",
    "CLAIM_AMOUNT",
    "APPROVED_AMOUNT",
    "MAX_COVERAGE_AMOUNT",
    "REMAINING_COVERAGE",
    "DEDUCTIBLE",
    "COPAY_PERCENTAGE",
    "CO_PAY_PERCENTAGE",
    "TOTAL_LIMIT",
    "USED_AMOUNT",
}

NUMERIC_INT_FIELDS = {
    "FILE_SIZE_BYTES",
    "IS_ACTIVE",
    "IS_RESOLVED",
    "EXECUTION_TIME_MS",
}


def _normalize_row(r: Dict[str, Any]) -> Dict[str, Any]:
    """Converts Db2 Decimal/numeric types and stringified numbers to native Python float/int."""
    from decimal import Decimal
    normalized = {}
    for k, v in r.items():
        if v is None:
            normalized[k] = None
        elif isinstance(v, Decimal):
            normalized[k] = float(v)
        elif k in NUMERIC_FLOAT_FIELDS:
            try:
                normalized[k] = float(v)
            except (ValueError, TypeError):
                normalized[k] = v
        elif k in NUMERIC_INT_FIELDS:
            try:
                normalized[k] = int(v)
            except (ValueError, TypeError):
                normalized[k] = v
        else:
            normalized[k] = v
    return normalized


class Db2ConnectionManager:
    """Enterprise connection manager for IBM Db2."""

    def __init__(self):
        self._conn = None
        self._last_error: Optional[str] = None
        self._is_live_connected: bool = False

    def is_driver_available(self) -> bool:
        return IBM_DB_AVAILABLE

    def get_connection(self):
        """
        Retrieves or establishes an active connection to IBM Db2.
        Returns the raw ibm_db connection object if successful, None otherwise.
        """
        if not IBM_DB_AVAILABLE:
            self._last_error = "ibm_db driver is not installed or failed to load binary dependencies."
            self._is_live_connected = False
            return None

        # Check existing active connection
        if self._conn:
            try:
                if ibm_db.active(self._conn):
                    return self._conn
            except Exception:
                self._conn = None

        # If password or host is blank, mark disconnected immediately
        if not settings.DB2_PASSWORD or not settings.DB2_HOST:
            self._last_error = (
                "IBM Db2 credentials incomplete. DB2_HOST and DB2_PASSWORD must be configured in .env."
            )
            self._is_live_connected = False
            return None

        conn_str = settings.db2_connection_string
        try:
            logger.info("Attempting connection to IBM Db2 at %s:%s...", settings.DB2_HOST, settings.DB2_PORT)
            self._conn = ibm_db.connect(conn_str, "", "")
            self._is_live_connected = True
            self._last_error = None
            logger.info("Successfully connected to IBM Db2 (%s)!", settings.DB2_DATABASE)
            return self._conn
        except Exception as e:
            err_msg = ""
            try:
                err_msg = ibm_db.conn_errormsg()
            except Exception:
                pass
            self._last_error = f"{str(e)} {err_msg}".strip()
            self._is_live_connected = False
            self._conn = None
            logger.warning("IBM Db2 connection attempt failed: %s", self._last_error)
            return None

    def close(self):
        """Closes the active connection if open."""
        if self._conn and IBM_DB_AVAILABLE:
            try:
                ibm_db.close(self._conn)
            except Exception:
                pass
            finally:
                self._conn = None
                self._is_live_connected = False

    def check_health(self) -> Dict[str, Any]:
        """
        Performs a real ping query against IBM Db2:
        'SELECT CURRENT TIMESTAMP FROM SYSIBM.SYSDUMMY1'
        Never fakes a successful status.
        """
        if not IBM_DB_AVAILABLE:
            return {
                "status": "unhealthy",
                "connected": False,
                "database": "IBM Db2",
                "driver": "ibm_db (not available)",
                "error": "ibm_db driver could not be loaded.",
                "demo_mode": settings.DEMO_MODE,
                "setup_guide": "Run: pip install ibm_db"
            }

        conn = self.get_connection()
        if not conn:
            return {
                "status": "disconnected",
                "connected": False,
                "database": "IBM Db2",
                "driver": "ibm_db 3.3.0",
                "host": settings.DB2_HOST,
                "port": settings.DB2_PORT,
                "database_name": settings.DB2_DATABASE,
                "error": self._last_error or "Could not connect to IBM Db2 instance.",
                "demo_mode": settings.DEMO_MODE,
                "instructions": (
                    "To start a local IBM Db2 container run:\n"
                    "docker run -d --name db2server -p 50000:50000 --env-file .env.db2 icr.io/db2_community/db2:latest"
                )
            }

        try:
            stmt = ibm_db.exec_immediate(conn, "SELECT CURRENT TIMESTAMP FROM SYSIBM.SYSDUMMY1")
            row = ibm_db.fetch_assoc(stmt)
            ibm_db.free_result(stmt)
            return {
                "status": "healthy",
                "connected": True,
                "database": "IBM Db2",
                "driver": "ibm_db 3.3.0",
                "host": settings.DB2_HOST,
                "port": settings.DB2_PORT,
                "database_name": settings.DB2_DATABASE,
                "server_time": list(row.values())[0] if row else None,
                "demo_mode": False
            }
        except Exception as e:
            return {
                "status": "degraded",
                "connected": False,
                "database": "IBM Db2",
                "error": str(e),
                "demo_mode": settings.DEMO_MODE
            }

    def execute_query(self, sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """
        Executes a parameterized SELECT query against IBM Db2.
        Uses ibm_db.prepare and ibm_db.execute to strictly prevent SQL injection.
        """
        conn = self.get_connection()
        if not conn:
            raise ConnectionError(f"IBM Db2 unavailable: {self._last_error}")

        try:
            stmt = ibm_db.prepare(conn, sql)
            if not stmt:
                raise RuntimeError(f"Failed to prepare SQL statement: {ibm_db.stmt_errormsg()}")

            if params:
                ibm_db.execute(stmt, params)
            else:
                ibm_db.execute(stmt)

            results: List[Dict[str, Any]] = []
            row = ibm_db.fetch_assoc(stmt)
            while row:
                results.append(_normalize_row(dict(row)))
                row = ibm_db.fetch_assoc(stmt)

            ibm_db.free_result(stmt)
            return results
        except Exception as e:
            logger.error("Error executing query on IBM Db2: %s | SQL: %s", e, sql)
            raise

    def execute_statement(self, sql: str, params: Optional[Tuple] = None) -> int:
        """
        Executes a parameterized INSERT, UPDATE, or DELETE statement.
        Returns the number of affected rows.
        """
        conn = self.get_connection()
        if not conn:
            raise ConnectionError(f"IBM Db2 unavailable: {self._last_error}")

        try:
            stmt = ibm_db.prepare(conn, sql)
            if not stmt:
                raise RuntimeError(f"Failed to prepare SQL statement: {ibm_db.stmt_errormsg()}")

            if params:
                ibm_db.execute(stmt, params)
            else:
                ibm_db.execute(stmt)

            affected = ibm_db.num_rows(stmt)
            ibm_db.free_result(stmt)
            return affected
        except Exception as e:
            logger.error("Error executing statement on IBM Db2: %s | SQL: %s", e, sql)
            raise

    def execute_transaction(self, statements: List[Tuple[str, Optional[Tuple]]]) -> bool:
        """
        Executes a multi-statement transaction atomically.
        Commits on full success; rolls back on any failure.
        """
        conn = self.get_connection()
        if not conn:
            raise ConnectionError(f"IBM Db2 unavailable: {self._last_error}")

        try:
            # Turn autocommit OFF
            ibm_db.autocommit(conn, ibm_db.SQL_AUTOCOMMIT_OFF)

            for sql, params in statements:
                stmt = ibm_db.prepare(conn, sql)
                if not stmt:
                    raise RuntimeError(f"Prepare failed in transaction: {ibm_db.stmt_errormsg()}")
                if params:
                    ibm_db.execute(stmt, params)
                else:
                    ibm_db.execute(stmt)
                ibm_db.free_result(stmt)

            # Commit transaction
            ibm_db.commit(conn)
            logger.info("Transaction successfully committed to IBM Db2 (%d statements)", len(statements))
            return True
        except Exception as e:
            logger.error("Transaction failed, rolling back: %s", e)
            try:
                ibm_db.rollback(conn)
            except Exception:
                pass
            raise
        finally:
            try:
                # Restore autocommit ON
                ibm_db.autocommit(conn, ibm_db.SQL_AUTOCOMMIT_ON)
            except Exception:
                pass


# Global singleton instance
db2_manager = Db2ConnectionManager()
