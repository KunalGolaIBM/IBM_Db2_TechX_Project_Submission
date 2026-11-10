import os
import datetime
import threading
from contextlib import contextmanager
from typing import Generator, Any
from dotenv import load_dotenv

# Load backend/.env or root .env
load_dotenv()

DB2_HOST = os.getenv("DB2_HOST", "127.0.0.1")
DB2_PORT = os.getenv("DB2_PORT", "50000")
DB2_DATABASE = os.getenv("DB2_DATABASE", "LOTLINE")
DB2_USER = os.getenv("DB2_USER", "db2inst1")
DB2_PASSWORD = os.getenv("DB2_PASSWORD", "ankush")
DB2_SCHEMA = os.getenv("DB2_SCHEMA", "LOTLINE_APP")

CONN_STR = (
    f"DATABASE={DB2_DATABASE};"
    f"HOSTNAME={DB2_HOST};"
    f"PORT={DB2_PORT};"
    f"PROTOCOL=TCPIP;"
    f"UID={DB2_USER};"
    f"PWD={DB2_PASSWORD};"
)

try:
    import ibm_db
    IBM_DB_AVAILABLE = True
except ImportError:
    ibm_db = None
    IBM_DB_AVAILABLE = False

# Lock to ensure thread-safe ibm_db connection handling
_db_lock = threading.Lock()


def serialize_val(val: Any) -> Any:
    if isinstance(val, (datetime.datetime, datetime.date)):
        return val.isoformat()
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return val


@contextmanager
def get_db_connection() -> Generator[Any, None, None]:
    if not IBM_DB_AVAILABLE:
        raise RuntimeError("ibm_db driver is not installed.")
    
    with _db_lock:
        conn = ibm_db.connect(CONN_STR, "", "")
        try:
            yield conn
        finally:
            try:
                ibm_db.close(conn)
            except Exception:
                pass


def query_all(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    with get_db_connection() as conn:
        stmt = ibm_db.prepare(conn, sql)
        if not stmt:
            raise RuntimeError(f"Prepare failed: {ibm_db.stmt_errormsg()}")
        
        res = ibm_db.execute(stmt, params)
        if not res:
            raise RuntimeError(f"Execute failed: {ibm_db.stmt_errormsg(stmt)}")
        
        results = []
        row = ibm_db.fetch_assoc(stmt)
        while row:
            clean_row = {k.lower(): serialize_val(v) for k, v in row.items()}
            results.append(clean_row)
            row = ibm_db.fetch_assoc(stmt)
        return results


def query_one(sql: str, params: tuple = ()) -> dict[str, Any] | None:
    rows = query_all(sql, params)
    return rows[0] if rows else None


def execute_transaction(operations: list[tuple[str, tuple]]) -> bool:
    with get_db_connection() as conn:
        ibm_db.autocommit(conn, ibm_db.SQL_AUTOCOMMIT_OFF)
        try:
            for sql, params in operations:
                stmt = ibm_db.prepare(conn, sql)
                if not stmt:
                    raise RuntimeError(f"Prepare failed: {ibm_db.stmt_errormsg()}")
                res = ibm_db.execute(stmt, params)
                if not res:
                    raise RuntimeError(f"Execute failed: {ibm_db.stmt_errormsg(stmt)}")
            ibm_db.commit(conn)
            return True
        except Exception as e:
            ibm_db.rollback(conn)
            raise e
