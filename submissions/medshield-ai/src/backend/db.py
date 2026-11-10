"""IBM Db2 persistence with SQLite demo fallback."""
import os, sqlite3
from dotenv import load_dotenv
load_dotenv()
from contextlib import contextmanager

DB2_DSN = os.getenv("DB2_DSN", "").strip()
SQLITE_PATH = os.getenv("SQLITE_PATH", "medshield_demo.db")

@contextmanager
def connection():
    if DB2_DSN:
        try:
            import ibm_db
            conn = ibm_db.connect(DB2_DSN, "", "")
            yield ("db2", conn)
            ibm_db.close(conn)
            return
        except Exception as exc:
            raise RuntimeError(f"IBM Db2 connection failed: {exc}") from exc
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield ("sqlite", conn)
        conn.commit()
    finally:
        conn.close()

def execute(sql, params=()):
    with connection() as (kind, conn):
        if kind == "db2":
            import ibm_db
            stmt = ibm_db.prepare(conn, sql)
            ibm_db.execute(stmt, tuple(params))
            return
        conn.execute(sql, tuple(params))

def rows(sql, params=()):
    with connection() as (kind, conn):
        if kind == "db2":
            import ibm_db
            stmt = ibm_db.exec_immediate(conn, sql) if not params else ibm_db.prepare(conn, sql)
            if params: ibm_db.execute(stmt, tuple(params))
            result=[]
            row=ibm_db.fetch_assoc(stmt)
            while row:
                result.append({k.lower():v for k,v in row.items()})
                row=ibm_db.fetch_assoc(stmt)
            return result
        return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

def init_db():
    statements = [
      "CREATE TABLE IF NOT EXISTS PATIENTS (PATIENT_ID VARCHAR(40) PRIMARY KEY, PATIENT_NAME VARCHAR(100), AGE INTEGER)",
      "CREATE TABLE IF NOT EXISTS MEDICATIONS (MEDICATION_ID INTEGER PRIMARY KEY, DRUG_NAME VARCHAR(100) UNIQUE)",
      "CREATE TABLE IF NOT EXISTS PATIENT_MEDICATIONS (PATIENT_ID VARCHAR(40), DRUG_NAME VARCHAR(100))",
      "CREATE TABLE IF NOT EXISTS ALLERGIES (PATIENT_ID VARCHAR(40), ALLERGEN VARCHAR(100))",
      "CREATE TABLE IF NOT EXISTS DRUG_INTERACTIONS (DRUG_A VARCHAR(100), DRUG_B VARCHAR(100), SEVERITY VARCHAR(20), DESCRIPTION VARCHAR(500))",
      "CREATE TABLE IF NOT EXISTS SAFETY_REPORTS (REPORT_ID INTEGER PRIMARY KEY, PATIENT_ID VARCHAR(40), RISK_LEVEL VARCHAR(20), FINDINGS VARCHAR(3000), CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    ]
    for s in statements:
        try: execute(s)
        except Exception as e:
            # Db2 may not support SQLite's IF NOT EXISTS syntax on all versions.
            if "already exists" not in str(e).lower() and "sql0601" not in str(e).lower(): raise
    seed_demo()

def seed_demo():
    # Fictional demo patient only; never use real patient data.
    try: execute("INSERT INTO PATIENTS (PATIENT_ID, PATIENT_NAME, AGE) VALUES (?, ?, ?)", ("DEMO-001","Alex Demo",45))
    except Exception: pass
    for a,b,sev,desc in [("warfarin","ibuprofen","HIGH","May increase bleeding risk."),("lisinopril","potassium","MODERATE","May increase potassium levels.")]:
        try: execute("INSERT INTO DRUG_INTERACTIONS (DRUG_A, DRUG_B, SEVERITY, DESCRIPTION) VALUES (?, ?, ?, ?)",(a,b,sev,desc))
        except Exception: pass
