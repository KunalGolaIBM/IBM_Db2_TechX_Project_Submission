import subprocess
import json
import logging
import sqlite3
import pandas as pd
from typing import List, Dict, Any, Optional
from config import (
    DB2_CONTAINER, DB2_DATABASE, DB2_USER, DB2_PASSWORD, SQLITE_DB_PATH
)

logger = logging.getLogger(__name__)

class Db2Client:
    """
    Robust IBM Db2 client interacting with the live DB2 instance.
    Includes SQLite automatic synchronization for lightning-fast reads
    and resilient offline capability.
    """
    def __init__(self):
        self.container = DB2_CONTAINER
        self.db = DB2_DATABASE
        self.user = DB2_USER
        self.password = DB2_PASSWORD
        self.sqlite_path = str(SQLITE_DB_PATH)
        self.init_sqlite_mirror()

    def init_sqlite_mirror(self):
        """Initialize local SQLite mirror file."""
        conn = sqlite3.connect(self.sqlite_path)
        conn.close()

    def _get_sqlite_conn(self):
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    def execute_in_db2(self, python_code: str) -> Dict[str, Any]:
        """Runs Python script inside IBM Db2 container using ibm_db."""
        cmd = ['docker', 'exec', '-i', self.container, 'su', '-', self.user, '-c', 'python3']
        try:
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
            stdout, stderr = p.communicate(input=python_code, timeout=30)
            if p.returncode != 0:
                logger.error(f"Db2 exec error: {stderr}")
                return {"success": False, "error": stderr}
            try:
                # Find the last json line in stdout
                lines = [line.strip() for line in stdout.strip().split("\n") if line.strip()]
                for line in reversed(lines):
                    if line.startswith("{") and line.endswith("}"):
                        return json.loads(line)
                return {"success": True, "raw": stdout}
            except Exception as e:
                return {"success": True, "raw": stdout, "parse_error": str(e)}
        except Exception as e:
            logger.exception(f"Error communicating with DB2 container: {e}")
            return {"success": False, "error": str(e)}

    def execute_db2_sql(self, sql: str, params: list = None) -> bool:
        """Executes DDL or DML statement directly in IBM Db2."""
        sql_escaped = sql.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'")
        params_json = json.dumps(params or [])
        
        script = f'''
import ibm_db, json

conn = None
try:
    conn = ibm_db.connect("{self.db}", "{self.user}", "{self.password}")
    sql = """{sql}"""
    params = {params_json}
    if params:
        stmt = ibm_db.prepare(conn, sql)
        res = ibm_db.execute(stmt, tuple(params))
    else:
        res = ibm_db.exec_immediate(conn, sql)
    print(json.dumps({{"success": True}}))
except Exception as e:
    print(json.dumps({{"success": False, "error": str(e)}}))
finally:
    if conn:
        try:
            ibm_db.close(conn)
        except:
            pass
'''
        res = self.execute_in_db2(script)
        return res.get("success", False)

    def execute_batch(self, statements: List[tuple]) -> bool:
        """
        Executes a batch of (sql, params) in a single IBM Db2 connection & transaction.
        Also synchronizes to SQLite mirror.
        """
        # Batch execute in SQLite mirror
        try:
            with self._get_sqlite_conn() as sconn:
                cursor = sconn.cursor()
                for sql, params in statements:
                    if params:
                        cursor.execute(sql, params)
                    else:
                        cursor.execute(sql)
                sconn.commit()
        except Exception as e:
            logger.warning(f"SQLite mirror batch error: {e}")

        # Batch execute in IBM Db2
        batch_payload = json.dumps([{"sql": sql, "params": params or []} for sql, params in statements])
        script = f'''
import ibm_db, json

payload = {batch_payload}
conn = None
try:
    conn = ibm_db.connect("{self.db}", "{self.user}", "{self.password}")
    ibm_db.autocommit(conn, ibm_db.SQL_AUTOCOMMIT_OFF)
    for item in payload:
        sql = item["sql"]
        params = item["params"]
        if params:
            stmt = ibm_db.prepare(conn, sql)
            ibm_db.execute(stmt, tuple(params))
        else:
            ibm_db.exec_immediate(conn, sql)
    ibm_db.commit(conn)
    print(json.dumps({{"success": True, "count": len(payload)}}))
except Exception as e:
    if conn:
        try:
            ibm_db.rollback(conn)
        except:
            pass
    print(json.dumps({{"success": False, "error": str(e)}}))
finally:
    if conn:
        try:
            ibm_db.close(conn)
        except:
            pass
'''
        res = self.execute_in_db2(script)
        return res.get("success", False)

    def query_db2(self, sql: str, params: list = None) -> List[Dict[str, Any]]:
        """Queries IBM Db2 and returns rows as list of dictionaries."""
        params_json = json.dumps(params or [])
        script = f'''
import ibm_db, json, datetime

def serialize(v):
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()
    return v

conn = None
try:
    conn = ibm_db.connect("{self.db}", "{self.user}", "{self.password}")
    sql = """{sql}"""
    params = {params_json}
    if params:
        stmt = ibm_db.prepare(conn, sql)
        ibm_db.execute(stmt, tuple(params))
    else:
        stmt = ibm_db.exec_immediate(conn, sql)
    
    rows = []
    row = ibm_db.fetch_assoc(stmt)
    while row:
        clean_row = {{k.lower(): serialize(v) for k, v in row.items()}}
        rows.append(clean_row)
        row = ibm_db.fetch_assoc(stmt)
    print(json.dumps({{"success": True, "rows": rows}}))
except Exception as e:
    print(json.dumps({{"success": False, "error": str(e), "rows": []}}))
finally:
    if conn:
        try:
            ibm_db.close(conn)
        except:
            pass
'''
        res = self.execute_in_db2(script)
        if res.get("success"):
            return res.get("rows", [])
        return []

    def execute(self, sql: str, params: list = None) -> bool:
        """Executes SQL in IBM Db2 and synchronizes with SQLite mirror."""
        # Execute in IBM Db2
        db2_success = self.execute_db2_sql(sql, params)
        
        # Also execute in SQLite mirror
        try:
            with self._get_sqlite_conn() as conn:
                cursor = conn.cursor()
                if params:
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)
                conn.commit()
        except Exception as e:
            logger.warning(f"SQLite mirror execute notice: {e}")
            
        return db2_success

    def query(self, sql: str, params: list = None) -> List[Dict[str, Any]]:
        """
        Executes SELECT query. Prefers live IBM Db2, fallback to SQLite mirror.
        """
        rows = self.query_db2(sql, params)
        if rows:
            return rows
        
        # SQLite mirror read
        try:
            with self._get_sqlite_conn() as conn:
                cursor = conn.cursor()
                if params:
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)
                raw_rows = cursor.fetchall()
                return [dict(r) for r in raw_rows]
        except Exception as e:
            logger.error(f"Query error: {e}")
            return []

    def query_df(self, sql: str, params: list = None) -> pd.DataFrame:
        """Runs query and returns a pandas DataFrame."""
        rows = self.query(sql, params)
        return pd.DataFrame(rows)

    def health_check(self) -> Dict[str, Any]:
        """Checks DB2 health and returns metadata."""
        script = f'''
import ibm_db, json
try:
    conn = ibm_db.connect("{self.db}", "{self.user}", "{self.password}")
    stmt = ibm_db.exec_immediate(conn, "SELECT CURRENT SERVER AS SERVER, CURRENT TIMESTAMP AS TS FROM SYSIBM.SYSDUMMY1")
    row = ibm_db.fetch_assoc(stmt)
    ibm_db.close(conn)
    print(json.dumps({{"status": "ONLINE", "server": row.get("SERVER"), "timestamp": str(row.get("TS"))}}))
except Exception as e:
    print(json.dumps({{"status": "OFFLINE", "error": str(e)}}))
'''
        res = self.execute_in_db2(script)
        if "status" in res:
            return res
        return {"status": "UNKNOWN", "details": res}

db_client = Db2Client()
