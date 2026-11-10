"""Tiny Db2 helper (ibm_db). Connection settings come from environment variables."""
import os, re
import ibm_db, ibm_db_dbi

def dsn(user=None, password=None):
    return (f"DATABASE={os.getenv('DB2_DATABASE','AQIDB')};HOSTNAME={os.getenv('DB2_HOST','localhost')};"
            f"PORT={os.getenv('DB2_PORT','50000')};PROTOCOL=TCPIP;UID={user or os.getenv('DB2_USER','db2inst1')};"
            f"PWD={password or os.environ['DB2_PASSWORD']};")

def connect(user=None, password=None, autocommit=True):
    """The loader and scripts connect as the schema owner (DB2_USER); pass user/password for another ID."""
    opts = {} if autocommit else {ibm_db.SQL_ATTR_AUTOCOMMIT: ibm_db.SQL_AUTOCOMMIT_OFF}
    return ibm_db_dbi.Connection(ibm_db.connect(dsn(user, password), "", "", opts))

def connect_app():
    """The web app's ID, AQAPP: it can read the audit and append explanations and question-log rows, but holds no
    DELETE, UPDATE, ALTER or CONTROL privilege, so it cannot truncate or rewrite the evidence (triggers do not fire on
    TRUNCATE). Falls back to the owner when no app user is configured (local development)."""
    if os.getenv("DB2_APP_PASSWORD"):
        return connect(os.getenv("DB2_APP_USER", "aqapp"), os.environ["DB2_APP_PASSWORD"])
    return connect()

def run_script(conn, path, schema=None):
    """Run a '@'-terminated SQL script, optionally rewriting schema AQ -> `schema`."""
    sql = open(path, encoding="utf-8").read()
    if schema:
        sql = re.sub(r"\bAQ\.", schema + ".", sql).replace("CREATE SCHEMA AQ@", f"CREATE SCHEMA {schema}@")
    cur = conn.cursor()
    for stmt in [s.strip() for s in sql.split("@")]:
        body = "\n".join(l for l in stmt.splitlines() if not l.strip().startswith("--")).strip()
        if body:
            cur.execute(stmt)
    conn.commit()

def rows(conn, sql, params=()):
    cur = conn.cursor(); cur.execute(sql, params); return cur.fetchall()
