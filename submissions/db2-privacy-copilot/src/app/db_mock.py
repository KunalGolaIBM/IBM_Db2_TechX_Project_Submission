"""
Mock database layer for running the app without a live Db2 instance.

Activated automatically when ibm_db is unavailable (e.g., Docker not running,
Windows Application Control blocking the DLL, or IBM Db2 client not installed).

All data is in-memory and resets on restart — for demo/development only.
"""
from __future__ import annotations

import json
import hashlib
from datetime import datetime, date
from typing import Any, Optional
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# In-memory "database" tables
# ---------------------------------------------------------------------------

_DB: dict[str, list[dict]] = {
    "PATIENT": [
        {"ID": 1, "FULL_NM": "Aryan Sharma", "CUST_MAIL_ID": "aryan@example.com",
         "PHONE_NO": 9876543210, "DOB": "1990-05-15", "GOVT_ID": "ABCDE1234F"},
        {"ID": 2, "FULL_NM": "Priya Mehta", "CUST_MAIL_ID": "priya@example.com",
         "PHONE_NO": 9123456780, "DOB": "1985-08-22", "GOVT_ID": "FGHIJ5678K"},
        {"ID": 3, "FULL_NM": "Rahul Gupta", "CUST_MAIL_ID": "rahul@example.com",
         "PHONE_NO": 8899001122, "DOB": "1978-12-01", "GOVT_ID": "KLMNO9012L"},
    ],
    "APPOINTMENT": [
        {"ID": 1, "PATIENT_ID": 1, "APPT_DATE": "2026-01-10", "DOCTOR_NM": "Dr. Smith"},
        {"ID": 2, "PATIENT_ID": 2, "APPT_DATE": "2026-02-14", "DOCTOR_NM": "Dr. Jones"},
        {"ID": 3, "PATIENT_ID": 1, "APPT_DATE": "2026-03-05", "DOCTOR_NM": "Dr. Patel"},
    ],
    "PRESCRIPTION": [
        {"ID": 1, "PATIENT_ID": 1, "DRUG_NM": "Amoxicillin", "DOSAGE": "500mg"},
        {"ID": 2, "PATIENT_ID": 2, "DRUG_NM": "Metformin", "DOSAGE": "1000mg"},
    ],
    "LAB_REPORT": [
        {"ID": 1, "PATIENT_ID": 1, "TEST_NM": "CBC", "RESULT_VAL": "Normal"},
        {"ID": 2, "PATIENT_ID": 3, "TEST_NM": "HbA1c", "RESULT_VAL": "6.2"},
    ],
    "PII_MAP": [],
    "REQUESTS": [],
    "AUDIT_LOG": [],
    "CONSENT": [
        {"ID": 1, "PATIENT_ID": 1, "PURPOSE": "TREATMENT", "GRANTED": "Y",
         "BUS_START": "2026-01-01", "BUS_END": "9999-12-30"},
        {"ID": 2, "PATIENT_ID": 2, "PURPOSE": "RESEARCH", "GRANTED": "Y",
         "BUS_START": "2026-01-01", "BUS_END": "2026-12-31"},
    ],
    "CONSENT_HISTORY": [],
    "RETENTION_RULES": [
        {"TABNAME": "PATIENT",      "ACTION": "ANONYMISE", "REASON": "Identity data",            "VERIFIED": "Y"},
        {"TABNAME": "APPOINTMENT",  "ACTION": "ANONYMISE", "REASON": "Retained for billing",     "VERIFIED": "N"},
        {"TABNAME": "BILLING",      "ACTION": "RETAIN",    "REASON": "Financial records",       "VERIFIED": "N"},
        {"TABNAME": "PRESCRIPTION", "ACTION": "ERASE",     "REASON": "Health data",             "VERIFIED": "N"},
        {"TABNAME": "LAB_REPORT",   "ACTION": "ERASE",     "REASON": "Health data",             "VERIFIED": "N"},
        {"TABNAME": "SUPPORT_TICKET", "ACTION": "ANONYMISE", "REASON": "Retain anonymous statistics", "VERIFIED": "N"},
        {"TABNAME": "MARKETING_LIST", "ACTION": "ERASE",   "REASON": "Consent withdrawn",       "VERIFIED": "N"},
    ],
    "_SYSCAT_COLUMNS": [
        # (TABNAME, COLNAME, TYPENAME, LENGTH, NULLS)
        ("PATIENT",      "ID",           "INTEGER",  4,   "N"),
        ("PATIENT",      "FULL_NM",      "VARCHAR",  100, "Y"),
        ("PATIENT",      "CUST_MAIL_ID", "VARCHAR",  150, "Y"),
        ("PATIENT",      "PHONE_NO",     "BIGINT",   8,   "Y"),
        ("PATIENT",      "DOB",          "DATE",     4,   "Y"),
        ("PATIENT",      "GOVT_ID",      "VARCHAR",  20,  "Y"),
        ("APPOINTMENT",  "ID",           "INTEGER",  4,   "N"),
        ("APPOINTMENT",  "PATIENT_ID",   "INTEGER",  4,   "N"),
        ("APPOINTMENT",  "APPT_DATE",    "DATE",     4,   "Y"),
        ("APPOINTMENT",  "DOCTOR_NM",    "VARCHAR",  100, "Y"),
        ("PRESCRIPTION", "ID",           "INTEGER",  4,   "N"),
        ("PRESCRIPTION", "PATIENT_ID",   "INTEGER",  4,   "N"),
        ("PRESCRIPTION", "DRUG_NM",      "VARCHAR",  100, "Y"),
        ("PRESCRIPTION", "DOSAGE",       "VARCHAR",  50,  "Y"),
        ("LAB_REPORT",   "ID",           "INTEGER",  4,   "N"),
        ("LAB_REPORT",   "PATIENT_ID",   "INTEGER",  4,   "N"),
        ("LAB_REPORT",   "TEST_NM",      "VARCHAR",  100, "Y"),
        ("LAB_REPORT",   "RESULT_VAL",   "VARCHAR",  200, "Y"),
    ],
    "_SYSCAT_TABLES": [
        ("PATIENT", "T"), ("APPOINTMENT", "T"), ("PRESCRIPTION", "T"), ("LAB_REPORT", "T"),
    ],
    "_SYSCAT_REFERENCES": [
        # (CHILD, PARENT, FK_COLS, PK_COLS)
        ("APPOINTMENT",  "PATIENT", "PATIENT_ID", "ID"),
        ("PRESCRIPTION", "PATIENT", "PATIENT_ID", "ID"),
        ("LAB_REPORT",   "PATIENT", "PATIENT_ID", "ID"),
    ],
}

_id_counters: dict[str, int] = {
    "AUDIT_LOG": 1, "REQUESTS": 1, "CONSENT": 10, "PII_MAP": 1,
}

# ---------------------------------------------------------------------------
# Query router — maps SQL prefixes to in-memory data
# ---------------------------------------------------------------------------

def _mock_query(sql: str, params: tuple = ()) -> Optional[list[tuple]]:
    """Route SQL to mock data. Very simplified — handles known query shapes."""
    sql_up = sql.strip().upper()

    # --- SYSCAT.COLUMNS ---
    if "SYSCAT.COLUMNS" in sql_up:
        schema = params[0].upper() if params else "DB2INST1"
        if schema != "DB2INST1":
            return []
        return _DB["_SYSCAT_COLUMNS"]

    # --- SYSCAT.TABLES ---
    if "SYSCAT.TABLES" in sql_up:
        schema = params[0].upper() if params else "DB2INST1"
        if schema != "DB2INST1":
            return []
        return _DB["_SYSCAT_TABLES"]

    # --- SYSCAT.REFERENCES ---
    if "SYSCAT.REFERENCES" in sql_up:
        if "TABNAME" in sql_up and "REFTABNAME" in sql_up and len(params) == 3:
            # fk_column_to_root(schema, child, parent)
            _, child, parent = params
            for row in _DB["_SYSCAT_REFERENCES"]:
                if row[0].upper() == child.upper() and row[1].upper() == parent.upper():
                    return [(row[2],)]
            return []
        return _DB["_SYSCAT_REFERENCES"]

    # --- SYSCAT.KEYCOLUSE (primary key lookup) ---
    if "SYSCAT.KEYCOLUSE" in sql_up:
        return [("ID",)]

    # --- SYSIBMADM.ENV_INST_INFO ---
    if "ENV_INST_INFO" in sql_up:
        return [("SQL12012",)]

    # --- SYSIBM.SYSDUMMY1 ---
    if "SYSDUMMY1" in sql_up:
        return [(1,)]

    # --- RETENTION_RULES ---
    if "RETENTION_RULES" in sql_up and sql_up.startswith("SELECT"):
        return [
            (r["TABNAME"], r["ACTION"], r["REASON"], r["VERIFIED"])
            for r in _DB["RETENTION_RULES"]
        ]

    # --- PII_MAP ---
    if "PII_MAP" in sql_up and sql_up.startswith("SELECT"):
        if params:
            table = params[0].upper()
            rows = [r for r in _DB["PII_MAP"] if r.get("TABNAME", "").upper() == table]
            return [(r["COLNAME"],) for r in rows if r.get("LABEL", "") != "NOT_PII"]
        return [(r["TABNAME"], r["COLNAME"], r["LABEL"], r["CONFIDENCE"], r["METHOD"])
                for r in _DB["PII_MAP"]]

    # --- CONSENT ---
    if "FROM CONSENT" in sql_up and sql_up.startswith("SELECT"):
        pid = params[0] if params else None
        rows = [r for r in _DB["CONSENT"] if pid is None or r["PATIENT_ID"] == pid]
        return [
            (r["PATIENT_ID"], r["PURPOSE"], r["GRANTED"], r["BUS_START"], r["BUS_END"])
            for r in rows
        ]

    # --- CONSENT_HISTORY ---
    if "CONSENT_HISTORY" in sql_up:
        return []

    # --- REQUESTS count/list ---
    if "FROM REQUESTS" in sql_up:
        if "COUNT(*)" in sql_up:
            pending = [r for r in _DB["REQUESTS"] if r.get("STATUS") == "PENDING_APPROVAL"]
            return [(len(pending),)]
        rows = _DB["REQUESTS"]
        if params:
            rows = [r for r in rows if r.get("STATUS") == params[0]]
        return [
            (r["ID"], r.get("REQUEST_TYPE","ERASURE"), r["SUBJECT_ID"],
             r["STATUS"], r.get("RECEIVED_AT","2026-11-10"), r.get("DUE_AT","2026-12-10"))
            for r in rows
        ]

    # --- AUDIT_LOG ---
    if "FROM AUDIT_LOG" in sql_up:
        if "FETCH FIRST 1 ROW ONLY" in sql_up:
            rows = _DB["AUDIT_LOG"]
            return [(rows[-1]["HASH"],)] if rows else []
        rows = _DB["AUDIT_LOG"]
        if params:
            col = "ACTION" if "ACTION = ?" in sql_up else "SUBJECT"
            rows = [r for r in rows if str(r.get(col, "")) == str(params[0])]
        return [
            (r["ID"], r["ACTOR"], r["ACTION"], r.get("SUBJECT"),
             r.get("DETAIL","{}"), r["PREV_HASH"], r["HASH"], r.get("CREATED_AT", datetime.now()))
            for r in rows
        ]

    # --- PATIENT ---
    if "FROM PATIENT" in sql_up:
        if "COUNT(*)" in sql_up:
            return [(len(_DB["PATIENT"]),)]
        if "FETCH FIRST 1 ROW ONLY" in sql_up:
            return [(_DB["PATIENT"][0]["ID"],)] if _DB["PATIENT"] else []
        pid = params[0] if params else None
        rows = [p for p in _DB["PATIENT"] if pid is None or p["ID"] == pid]
        return [(r["ID"],) for r in rows]

    # Column value sampling
    for tname in ["PATIENT", "APPOINTMENT", "PRESCRIPTION", "LAB_REPORT"]:
        if f'FROM "DB2INST1"."{tname}"' in sql_up or f"FROM DB2INST1.{tname}" in sql_up:
            col_match = None
            import re
            m = re.search(r'SELECT\s+"?(\w+)"?\s+FROM', sql_up)
            if m:
                col_match = m.group(1)
            rows = _DB.get(tname, [])
            if col_match and rows:
                return [(r.get(col_match),) for r in rows if r.get(col_match) is not None]
            return []

    # Default: return empty
    return []


def _mock_execute(sql: str, params: tuple = ()) -> int:
    """Handle INSERT/UPDATE/DELETE on mock tables."""
    sql_up = sql.strip().upper()

    # INSERT AUDIT_LOG
    if "INSERT INTO AUDIT_LOG" in sql_up:
        new_id = _id_counters["AUDIT_LOG"]
        _id_counters["AUDIT_LOG"] += 1
        _DB["AUDIT_LOG"].append({
            "ID": new_id,
            "ACTOR": params[0] if params else "system",
            "ACTION": params[1] if len(params) > 1 else "ACTION",
            "SUBJECT": params[2] if len(params) > 2 else None,
            "DETAIL": params[3] if len(params) > 3 else "{}",
            "PREV_HASH": params[4] if len(params) > 4 else "GENESIS",
            "HASH": params[5] if len(params) > 5 else "0" * 64,
            "CREATED_AT": datetime.now(),
        })
        return 1

    # INSERT REQUESTS
    if "INSERT INTO REQUESTS" in sql_up:
        new_id = _id_counters["REQUESTS"]
        _id_counters["REQUESTS"] += 1
        _DB["REQUESTS"].append({
            "ID": new_id,
            "REQUEST_TYPE": "ERASURE",
            "SUBJECT_ID": params[0] if params else 0,
            "STATUS": "PENDING_APPROVAL",
            "RECEIVED_AT": datetime.now().isoformat(),
            "DUE_AT": params[1] if len(params) > 1 else "",
            "PLAN_JSON": params[2] if len(params) > 2 else None,
            "PLAN_HASH": params[3] if len(params) > 3 else "",
        })
        return 1

    # INSERT/MERGE PII_MAP
    if "PII_MAP" in sql_up and ("INSERT" in sql_up or "MERGE" in sql_up):
        tabname = params[0] if params else ""
        colname = params[1] if len(params) > 1 else ""
        # Upsert
        existing = [r for r in _DB["PII_MAP"]
                    if r["TABNAME"] == tabname and r["COLNAME"] == colname]
        if existing:
            existing[0].update({
                "LABEL": params[2] if len(params) > 2 else "NOT_PII",
                "CONFIDENCE": params[3] if len(params) > 3 else 0.5,
                "METHOD": params[4] if len(params) > 4 else "DEFAULT",
            })
        else:
            _DB["PII_MAP"].append({
                "TABNAME": tabname, "COLNAME": colname,
                "LABEL": params[2] if len(params) > 2 else "NOT_PII",
                "CONFIDENCE": params[3] if len(params) > 3 else 0.5,
                "METHOD": params[4] if len(params) > 4 else "DEFAULT",
            })
        return 1

    # INSERT CONSENT
    if "INSERT INTO CONSENT" in sql_up:
        new_id = _id_counters["CONSENT"]
        _id_counters["CONSENT"] += 1
        _DB["CONSENT"].append({
            "ID": new_id,
            "PATIENT_ID": params[0] if params else 0,
            "PURPOSE": params[1] if len(params) > 1 else "",
            "GRANTED": params[2] if len(params) > 2 else "Y",
            "BUS_START": params[3] if len(params) > 3 else date.today().isoformat(),
            "BUS_END": params[4] if len(params) > 4 else "9999-12-30",
        })
        return 1

    # UPDATE CONSENT (withdraw)
    if "UPDATE CONSENT" in sql_up:
        pid = params[2] if len(params) > 2 else None
        purpose = params[3] if len(params) > 3 else None
        effective = params[1] if len(params) > 1 else date.today().isoformat()
        count = 0
        for r in _DB["CONSENT"]:
            if (pid is None or r["PATIENT_ID"] == pid) and \
               (purpose is None or r["PURPOSE"] == purpose):
                r["BUS_END"] = effective
                count += 1
        return count

    # UPDATE REQUESTS
    if "UPDATE REQUESTS" in sql_up:
        return 1

    # DELETE (erasure)
    if sql_up.startswith("DELETE"):
        return 0  # Mock: nothing to delete in demo

    return 0


# ---------------------------------------------------------------------------
# Mock connection class
# ---------------------------------------------------------------------------

class _MockCursor:
    def __init__(self):
        self.rowcount = 0
        self._last_insert_id = None
        self.description = None
        self._results = []
        self._idx = 0

    def execute(self, sql: str, params: tuple = ()):
        sql_up = sql.strip().upper()
        if sql_up.startswith("SELECT") or sql_up.startswith("VALUES"):
            if "IDENTITY_VAL_LOCAL" in sql_up:
                # Return last inserted audit log ID
                self._results = [(_id_counters["AUDIT_LOG"] - 1,)]
                self.description = [("ID",)]
            else:
                self._results = _mock_query(sql, params) or []
                self.description = [("COL",)] if self._results else None
            self._idx = 0
        else:
            self.rowcount = _mock_execute(sql, params)
            self.description = None

    def fetchall(self):
        return self._results

    def fetchone(self):
        if self._results:
            return self._results[0]
        return None

    def close(self):
        pass


class _MockConnection:
    def __init__(self):
        self._autocommit = True

    def cursor(self):
        return _MockCursor()

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass

    def set_autocommit(self, val: bool):
        self._autocommit = val


# ---------------------------------------------------------------------------
# Public API — drop-in replacements for app.db functions
# ---------------------------------------------------------------------------

def conn() -> _MockConnection:
    return _MockConnection()


def query(sql: str, params: tuple = ()) -> Optional[list[tuple]]:
    return _mock_query(sql, params)


def execute(sql: str, params: tuple = ()) -> int:
    return _mock_execute(sql, params)


def check_db2_version() -> str:
    return "SQL12012 (MOCK)"


def run_sql_file(filepath: str) -> None:
    print(f"[MOCK] Skipping SQL file: {filepath}")


MOCK_MODE = True
