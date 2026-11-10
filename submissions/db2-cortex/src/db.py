"""Thin IBM Db2 access layer (ibm_db / ibm_db_dbi)."""
import threading
import ibm_db
import ibm_db_dbi
from config import DB

_lock = threading.RLock()
_conn = None


def conn():
    global _conn
    if _conn is None:
        dsn = (f"DATABASE={DB['database']};HOSTNAME={DB['host']};PORT={DB['port']};"
               f"PROTOCOL=TCPIP;UID={DB['user']};PWD={DB['password']};")
        _conn = ibm_db_dbi.connect(dsn, "", "")
    return _conn


def query(sql, params=()):
    with _lock:
        cur = conn().cursor()
        try:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            rows = [list(r) for r in cur.fetchall()]
            conn().rollback()  # read paths never leave a transaction open
            return cols, rows
        finally:
            cur.close()


def execute(sql, params=()):
    with _lock:
        cur = conn().cursor()
        try:
            cur.execute(sql, params)
            conn().commit()
        except Exception:
            conn().rollback()
            raise
        finally:
            cur.close()


def executemany(sql, seq):
    with _lock:
        cur = conn().cursor()
        try:
            cur.executemany(sql, seq)
            conn().commit()
        finally:
            cur.close()


def prepare_ok(sql):
    """Ask the Db2 optimizer/parser to PREPARE the statement without running it."""
    with _lock:
        stmt = ibm_db.prepare(conn().conn_handler, sql)
        return bool(stmt)


def vec(v):
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def vlit(v):
    """Inline VECTOR literal (numbers only, injection-safe)."""
    from config import EMBED_DIM
    return f"VECTOR('{vec(v)}', {EMBED_DIM}, FLOAT32)"


def version():
    try:
        _, r = query("SELECT SERVICE_LEVEL FROM TABLE(SYSPROC.ENV_GET_INST_INFO())")
        return r[0][0]
    except Exception:
        return "Db2 (connected)"
