"""IBM Db2 Database Connection and Utility Module for ColdChain Guardian.

Provides:
- Environment configuration loading from backend/.env
- Safe connection lifecycle using the official ibm_db driver
- Parameterised query execution (SELECT, DML, single row, batch)
- Transaction management and clean cursor/connection cleanup
"""

import os
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import ibm_db
from dotenv import load_dotenv

# Automatically load backend/.env if it exists
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"
if _ENV_FILE.exists():
    load_dotenv(dotenv_path=_ENV_FILE)
else:
    load_dotenv()


def get_db2_config() -> Dict[str, Any]:
    """Retrieve Db2 configuration from environment variables."""
    host = os.getenv("DB2_HOST", "localhost")
    port = os.getenv("DB2_PORT", "50000")
    database = os.getenv("DB2_DATABASE", "COLDCHN")
    # Accept either DB2_USER or DB2_USERNAME
    user = os.getenv("DB2_USER") or os.getenv("DB2_USERNAME", "db2inst1")
    password = os.getenv("DB2_PASSWORD", "")
    security = os.getenv("DB2_SECURITY", "false").lower() in ("true", "1", "yes", "ssl")

    if not password:
        raise ValueError("DB2_PASSWORD environment variable is required but not set.")

    return {
        "host": host,
        "port": port,
        "database": database,
        "user": user,
        "password": password,
        "security": security,
    }


def get_connection_string() -> str:
    """Build the ibm_db connection string without exposing sensitive info in logs."""
    config = get_db2_config()
    dsn = (
        f"DATABASE={config['database']};"
        f"HOSTNAME={config['host']};"
        f"PORT={config['port']};"
        f"PROTOCOL=TCPIP;"
        f"UID={config['user']};"
        f"PWD={config['password']};"
    )
    if config["security"]:
        dsn += "SECURITY=SSL;"
    return dsn


def get_connection():
    """Establish and return an active ibm_db connection."""
    dsn = get_connection_string()
    try:
        conn = ibm_db.connect(dsn, "", "")
        return conn
    except Exception as e:
        # Mask password in any exception string if present
        config = get_db2_config()
        err_msg = str(e).replace(config["password"], "********")
        raise ConnectionError(f"Failed to connect to IBM Db2 ({config['database']}): {err_msg}") from None


def normalize_db_value(value: Any) -> Any:
    """Convert Db2 driver values into JSON-safe Python values.

    Integers stay integers, timestamps become ISO-8601 strings, and
    integral decimals become ints so identity columns compare as ints.
    """
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (str, int, float)):
        return value
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _column_value(row: Optional[Dict[str, Any]], name: str) -> Any:
    """Read a fetch_assoc column without depending on driver key case."""
    if not row:
        return None
    target = name.lower()
    for key, value in row.items():
        if str(key).lower() == target:
            return value
    return None


def execute_query(sql: str, params: Optional[Tuple[Any, ...]] = None) -> List[Dict[str, Any]]:
    """Execute a SELECT query with parameters and return results as list of dicts."""
    conn = get_connection()
    try:
        stmt = ibm_db.prepare(conn, sql)
        if not stmt:
            raise RuntimeError(f"Db2 prepare failed: {ibm_db.stmt_errormsg(conn)}")

        if params:
            for idx, param in enumerate(params, start=1):
                ibm_db.bind_param(stmt, idx, param)

        rc = ibm_db.execute(stmt)
        if not rc:
            raise RuntimeError(f"Db2 execute failed: {ibm_db.stmt_errormsg(stmt)}")

        results: List[Dict[str, Any]] = []
        row = ibm_db.fetch_assoc(stmt)
        while row:
            clean_row = {}
            for k, v in row.items():
                clean_row[k.lower()] = normalize_db_value(v)
            results.append(clean_row)
            row = ibm_db.fetch_assoc(stmt)

        ibm_db.free_result(stmt)
        return results
    finally:
        ibm_db.close(conn)


def execute_query_one(sql: str, params: Optional[Tuple[Any, ...]] = None) -> Optional[Dict[str, Any]]:
    """Execute a SELECT query and return the first row or None."""
    rows = execute_query(sql, params)
    return rows[0] if rows else None


def execute_dml(sql: str, params: Optional[Tuple[Any, ...]] = None) -> int:
    """Execute an INSERT, UPDATE, or DELETE query and return the number of affected rows."""
    conn = get_connection()
    try:
        stmt = ibm_db.prepare(conn, sql)
        if not stmt:
            raise RuntimeError(f"Db2 prepare failed: {ibm_db.stmt_errormsg(conn)}")

        if params:
            for idx, param in enumerate(params, start=1):
                ibm_db.bind_param(stmt, idx, param)

        rc = ibm_db.execute(stmt)
        if not rc:
            raise RuntimeError(f"Db2 execute failed: {ibm_db.stmt_errormsg(stmt)}")

        rows_affected = ibm_db.num_rows(stmt)
        return rows_affected
    finally:
        ibm_db.close(conn)


def execute_insert_get_id(sql: str, params: Optional[Tuple[Any, ...]] = None) -> int:
    """Execute an INSERT on a table with an IDENTITY column and return the generated ID."""
    conn = get_connection()
    try:
        stmt = ibm_db.prepare(conn, sql)
        if not stmt:
            raise RuntimeError(f"Db2 prepare failed: {ibm_db.stmt_errormsg(conn)}")

        if params:
            for idx, param in enumerate(params, start=1):
                ibm_db.bind_param(stmt, idx, param)

        rc = ibm_db.execute(stmt)
        if not rc:
            raise RuntimeError(f"Db2 execute failed: {ibm_db.stmt_errormsg(stmt)}")

        id_stmt = ibm_db.exec_immediate(conn, "SELECT IDENTITY_VAL_LOCAL() AS NEW_ID FROM SYSIBM.SYSDUMMY1")
        row = ibm_db.fetch_assoc(id_stmt)
        ibm_db.free_result(id_stmt)
        # IDENTITY_VAL_LOCAL is only populated by a single-row INSERT ... VALUES.
        # INSERT ... SELECT leaves it null; callers must use VALUES or re-read the row.
        raw_id = _column_value(row, "NEW_ID")
        if raw_id is None:
            return 0
        try:
            return int(raw_id)
        except (TypeError, ValueError):
            return 0
    finally:
        ibm_db.close(conn)


def test_connection() -> Dict[str, Any]:
    """Test the database connection and return server timestamp and version info."""
    conn = get_connection()
    try:
        stmt = ibm_db.exec_immediate(conn, "SELECT CURRENT TIMESTAMP AS SERVER_TIME, CURRENT SERVER AS DB_NAME FROM SYSIBM.SYSDUMMY1")
        row = ibm_db.fetch_assoc(stmt)
        ibm_db.free_result(stmt)
        return {
            "status": "connected",
            "server_time": str(row.get("SERVER_TIME")),
            "database_name": str(row.get("DB_NAME")),
        }
    finally:
        ibm_db.close(conn)
