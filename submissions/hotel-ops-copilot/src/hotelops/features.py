"""Which IBM Db2 features the project uses, read live from the Db2 catalog (SYSCAT), not from the README.

``inventory`` runs one catalog query per feature and returns the objects that implement it, so the app's
"Db2 features" tab and ``verify.py`` show what is really deployed in the database right now.
"""
from __future__ import annotations

from hotelops.config import SCHEMA
from hotelops.db import Db2, Db2Error

# (feature, area, catalog query returning one column NAME, live check that proves it at run time)
FEATURES: list[tuple[str, str, str, str]] = [
    ("Native VECTOR columns", "AI",
     "SELECT TABNAME || '.' || COLNAME FROM SYSCAT.COLUMNS WHERE TABSCHEMA = ? AND TYPENAME = 'VECTOR'",
     "checks 3-4"),
    ("IBM langchain-db2 vector store", "AI",
     "SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TABNAME = 'POLICY_KB'", "check 5"),
    ("System-period temporal tables (time travel)", "Data",
     "SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TEMPORALTYPE IN ('S', 'B')", "check 6"),
    ("Bitemporal table (BUSINESS_TIME + SYSTEM_TIME)", "Data",
     "SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TEMPORALTYPE = 'B'", "check 7"),
    ("Materialized query table (MQT)", "Data",
     "SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TYPE = 'S'", "check 8"),
    ("Adaptive row compression", "Data",
     "SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND ROWCOMPMODE = 'A'", "check 31"),
    ("Semantic layer: views + catalog comments", "AI",
     "SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TYPE = 'V' AND REMARKS IS NOT NULL", "check 10"),
    ("SQL PL stored procedures (guardrails)", "Governance",
     "SELECT ROUTINENAME FROM SYSCAT.ROUTINES WHERE ROUTINESCHEMA = ? AND ROUTINETYPE = 'P'", "checks 17, 22"),
    ("JSON check constraint (JSON_EXISTS)", "Governance",
     "SELECT TABNAME || '.' || CONSTNAME FROM SYSCAT.CHECKS WHERE TABSCHEMA = ? AND TEXT LIKE '%JSON_EXISTS%'",
     "check 20"),
    ("Triggers (SHA-256 hash chain)", "Governance",
     "SELECT TRIGNAME FROM SYSCAT.TRIGGERS WHERE TRIGSCHEMA = ?", "checks 26-27"),
    ("Composite foreign keys (hotel consistency)", "Governance",
     "SELECT TABNAME || '.' || CONSTNAME FROM SYSCAT.REFERENCES WHERE TABSCHEMA = ? AND COLCOUNT > 1 "
     "AND FK_COLNAMES LIKE '%PROPERTY_ID%'", "check 14"),
    ("Roles and least-privilege grants", "Security",
     "SELECT DISTINCT TABNAME FROM SYSCAT.TABAUTH WHERE TABSCHEMA = ? AND GRANTEE = 'HOTELOPS_AGENT'", "check 11"),
    ("RCAC column masks (PII)", "Security",
     "SELECT CONTROLNAME FROM SYSCAT.CONTROLS WHERE TABSCHEMA = ? AND CONTROLTYPE = 'C'", "check 12"),
    ("RCAC row permissions (consent, hotel isolation)", "Security",
     "SELECT CONTROLNAME FROM SYSCAT.CONTROLS WHERE TABSCHEMA = ? AND CONTROLTYPE = 'R' "
     "AND CONTROLNAME NOT LIKE 'SYS_DEFAULT%'", "checks 13-14"),
    ("Label-based access control (LBAC)", "Security",
     "SELECT P.SECPOLICYNAME || ': ' || L.SECLABELNAME FROM SYSCAT.SECURITYPOLICIES P JOIN SYSCAT.SECURITYLABELS L "
     "ON L.SECPOLICYID = P.SECPOLICYID WHERE ? IS NOT NULL", "check 32"),
    ("Workload management thresholds (AI login)", "Security",
     "SELECT THRESHOLDNAME FROM SYSCAT.THRESHOLDS WHERE THRESHOLDNAME LIKE 'HOTELOPS_AGENT_%' AND ? IS NOT NULL",
     "check 15"),
    ("Event monitor (threshold violations)", "Security",
     "SELECT EVMONNAME FROM SYSCAT.EVENTMONITORS WHERE EVMONNAME LIKE 'HOTELOPS_%' AND ? IS NOT NULL", "check 15"),
    ("EXPLAIN plan tables (cost guard)", "Security",
     "SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = 'SYSTOOLS' AND TABNAME = 'EXPLAIN_STATEMENT' "
     "AND ? IS NOT NULL", "check 16"),
]


def inventory(db: Db2) -> list[dict]:
    """One row per Db2 feature: how many catalog objects implement it, a few names, and the live proof."""
    rows = []
    for feature, area, sql, proof in FEATURES:
        try:
            names = sorted({str(next(iter(r.values()))).strip() for r in db.query(sql, (SCHEMA,))})
        except Db2Error as exc:
            names = [f"error: {str(exc)[:60]}"]
        rows.append({"Area": area, "Db2 feature": feature, "Objects": len(names),
                     "In the database": ", ".join(names[:6]) + (" …" if len(names) > 6 else ""),
                     "Proved live by": proof})
    return rows
