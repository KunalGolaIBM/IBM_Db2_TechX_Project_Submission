"""Db2 connections. Every end user gets their OWN Db2 connection (their own authorization ID),
so RCAC, GRANTs and row permissions are enforced by the engine, not by this code."""
import os
from pathlib import Path

from dotenv import load_dotenv

if os.name == "nt" and "IBM_DB_HOME" not in os.environ:  # Windows wheel ships its clidriver DLLs
    import importlib.util
    _spec = importlib.util.find_spec("ibm_db")
    _cli = Path(_spec.origin).parent / "clidriver" / "bin"
    if _cli.is_dir():
        os.add_dll_directory(str(_cli))
import ibm_db_dbi  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

# The gateway's own identity (control plane) and the two demo humans.
USERS = {
    "DB2INST1": "DB2_PASSWORD",
    "PRIYA": "PRIYA_PASSWORD",
    "ARJUN": "ARJUN_PASSWORD",
}


def connect(user: str = "DB2INST1", autocommit: bool = True):
    user = user.upper()
    if user not in USERS:
        raise ValueError(f"unknown user {user}")
    password = os.environ.get(USERS[user])
    if not password:
        raise RuntimeError(f"{USERS[user]} is not set (copy .env.example to .env)")
    dsn = (
        f"DATABASE={os.getenv('DB2_DATABASE', 'CUSTDB')};HOSTNAME={os.getenv('DB2_HOST', '127.0.0.1')};"
        f"PORT={os.getenv('DB2_PORT', '50000')};PROTOCOL=TCPIP;UID={user.lower()};PWD={password};"
    )
    conn = ibm_db_dbi.connect(dsn, "", "")
    conn.set_autocommit(autocommit)
    cur = conn.cursor()
    cur.execute("SET SCHEMA BANK")  # unqualified agent SQL resolves to the BANK tables
    cur.close()
    return conn


def query(conn, sql: str, params=(), limit: int | None = None):
    """Run a statement, return (columns, rows). rows is [] for statements without a result set."""
    cur = conn.cursor()
    try:
        cur.execute(sql, tuple(params))
        if not cur.description:
            return [], []
        cols = [d[0] for d in cur.description]
        rows = cur.fetchmany(limit) if limit else cur.fetchall()
        return cols, [list(r) for r in rows]
    finally:
        cur.close()


def scalar(conn, sql: str, params=()):
    _, rows = query(conn, sql, params)
    return rows[0][0] if rows else None
