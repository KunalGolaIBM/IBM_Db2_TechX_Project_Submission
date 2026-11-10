"""
Native ibm_db connection and query utilities for Db2 Copilot.
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    import ibm_db
except ImportError:
    ibm_db = None


def get_db2_params():
    """Retrieve Db2 configuration from environment variables."""
    host = os.getenv("DB2_HOST", "host.docker.internal")
    port = int(os.getenv("DB2_PORT", "50000"))
    database = os.getenv("DB2_DATABASE", "testdb")
    user = os.getenv("DB2_USER", "db2inst1")
    password = os.getenv("DB2_PASSWORD", "YourSecurePassword123!")
    security = os.getenv("DB2_SECURITY", "false").lower() in ("true", "1", "yes")

    conn_str = (
        f"DATABASE={database};"
        f"HOSTNAME={host};"
        f"PORT={port};"
        f"PROTOCOL=TCPIP;"
        f"UID={user};"
        f"PWD={password};"
    )
    if security:
        conn_str += "SECURITY=SSL;"

    return {
        "host": host,
        "port": port,
        "database": database,
        "user": user,
        "password": password,
        "conn_str": conn_str,
    }


def get_connection():
    """Establish and return an active native ibm_db connection."""
    if ibm_db is None:
        raise RuntimeError("ibm_db module is not installed or could not be loaded.")

    cfg = get_db2_params()
    try:
        conn = ibm_db.connect(cfg["conn_str"], "", "")
        return conn
    except Exception as e:
        # If host.docker.internal failed and DB2_HOST wasn't 172.17.0.2, try container bridge IP as fallback
        if cfg["host"] == "host.docker.internal":
            fallback_conn_str = cfg["conn_str"].replace("HOSTNAME=host.docker.internal", "HOSTNAME=172.17.0.2")
            try:
                conn = ibm_db.connect(fallback_conn_str, "", "")
                return conn
            except Exception:
                pass
        raise RuntimeError(f"Failed to connect to Db2 ({cfg['host']}:{cfg['port']}/{cfg['database']}): {e}")


def execute_query(conn, sql, params=None):
    """Execute a SELECT query and return list of dicts."""
    if params:
        stmt = ibm_db.prepare(conn, sql)
        ibm_db.execute(stmt, tuple(params))
    else:
        stmt = ibm_db.exec_immediate(conn, sql)

    rows = []
    row = ibm_db.fetch_assoc(stmt)
    while row:
        # Normalise key names to lowercase for consistency
        clean_row = {str(k).lower(): v for k, v in row.items()}
        rows.append(clean_row)
        row = ibm_db.fetch_assoc(stmt)
    return rows


def execute_non_query(conn, sql, params=None):
    """Execute an INSERT, UPDATE, DELETE, or DDL statement."""
    if params:
        stmt = ibm_db.prepare(conn, sql)
        res = ibm_db.execute(stmt, tuple(params))
        return ibm_db.num_rows(stmt)
    else:
        stmt = ibm_db.exec_immediate(conn, sql)
        try:
            return ibm_db.num_rows(stmt)
        except Exception:
            return 0

