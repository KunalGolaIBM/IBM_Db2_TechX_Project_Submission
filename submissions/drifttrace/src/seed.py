"""Idempotent schema + SYNTHETIC fixture loader. Never drops tables or clears cases.

Run: python src/seed.py
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from db import connect, execute, query

SCHEMA_FILE = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"

# All data below is SYNTHETIC, authored for this demo. Customers are fictional.
INSTRUMENTS = [
    ("CAL-017", "Digital caliper 0-150 mm (synthetic)", datetime(2026, 11, 2, 8, 0), "VER-017-1102"),
    ("CAL-018", "Digital caliper 0-150 mm (synthetic)", datetime(2026, 11, 2, 8, 0), "VER-018-1102"),
]
LOTS = [
    ("L-101", "Spacer SP-25 (synthetic)", 60),
    ("L-102", "Spacer SP-25 (synthetic)", 30),
    ("L-103", "Spacer SP-25 (synthetic)", 20),
    ("L-104", "Spacer SP-25 (synthetic)", 25),
    ("L-105", "Spacer SP-25 (synthetic)", 15),
    ("L-106", "Spacer SP-25 (synthetic)", 10),
]
_LO, _HI = Decimal("24.950"), Decimal("25.050")
INSPECTIONS = [
    ("I-101", "CAL-017", "L-101", datetime(2026, 11, 3, 12, 0), Decimal("25.040")),
    ("I-102", "CAL-017", "L-102", datetime(2026, 11, 4, 12, 0), Decimal("25.000")),
    ("I-103", "CAL-017", "L-103", datetime(2026, 11, 5, 12, 0), Decimal("24.960")),
    ("I-104", "CAL-017", "L-104", datetime(2026, 11, 1, 12, 0), Decimal("25.040")),
    ("I-105", "CAL-018", "L-105", datetime(2026, 11, 4, 12, 0), Decimal("25.040")),
    ("I-106", "CAL-017", "L-106", None, Decimal("25.040")),
]
SHIPMENTS = [
    ("S-101", "L-101", "Atlas Cycles (fictional)", 40, datetime(2026, 11, 6, 9, 0)),
    ("S-102", "L-102", "Harbor Fixtures (fictional)", 30, datetime(2026, 11, 6, 9, 0)),
    ("S-103", "L-104", "Atlas Cycles (fictional)", 25, datetime(2026, 11, 3, 9, 0)),
    ("S-104", "L-105", "Harbor Fixtures (fictional)", 15, datetime(2026, 11, 6, 9, 0)),
    ("S-105", "L-106", "Cedar Works (fictional)", 10, datetime(2026, 11, 6, 9, 0)),
]


CATALOG = {
    "TABLE": "SELECT 1 FROM SYSCAT.TABLES WHERE TABSCHEMA = CURRENT SCHEMA AND TABNAME = ?",
    "INDEX": "SELECT 1 FROM SYSCAT.INDEXES WHERE INDSCHEMA = CURRENT SCHEMA AND INDNAME = ?",
    "VIEW": "SELECT 1 FROM SYSCAT.VIEWS WHERE VIEWSCHEMA = CURRENT SCHEMA AND VIEWNAME = ?",
    "TRIGGER": "SELECT 1 FROM SYSCAT.TRIGGERS WHERE TRIGSCHEMA = CURRENT SCHEMA AND TRIGNAME = ?",
}

# Least-privilege grants for the application user (DB2_UID). Operational tables are
# read-only to the app; investigation tables are insert + select only (no UPDATE/DELETE).
APP_GRANTS = [
    "GRANT CONNECT ON DATABASE TO USER {u}",
    "GRANT SELECT ON DT_INSTRUMENTS TO USER {u}",
    "GRANT SELECT ON DT_LOTS TO USER {u}",
    "GRANT SELECT ON DT_INSPECTIONS TO USER {u}",
    "GRANT SELECT ON DT_SHIPMENTS TO USER {u}",
    "GRANT SELECT ON DT_LOT_EXPOSURE_V TO USER {u}",
    "GRANT SELECT, INSERT ON DT_CASES TO USER {u}",
    "GRANT SELECT, INSERT ON DT_FINDINGS TO USER {u}",
    "GRANT SELECT, INSERT ON DT_AUDIT TO USER {u}",
    "GRANT SELECT, INSERT ON DT_REVIEW_EVENTS TO USER {u}",
]


FIXTURE_TABLES = frozenset({"DT_INSTRUMENTS", "DT_LOTS", "DT_INSPECTIONS", "DT_SHIPMENTS"})
COUNT_TABLES = ("DT_INSTRUMENTS", "DT_LOTS", "DT_INSPECTIONS", "DT_SHIPMENTS", "DT_CASES", "DT_FINDINGS", "DT_AUDIT", "DT_REVIEW_EVENTS")
FIXTURE_COLUMNS = frozenset({"ID", "NAME", "LAST_VERIFIED_AT", "VERIFICATION_REF", "PRODUCT_NAME", "PRODUCED_QUANTITY",
                             "INSTRUMENT_ID", "LOT_ID", "MEASURED_AT", "FUNCTION_CODE", "UNIT", "RECORDED_VALUE",
                             "LOWER_LIMIT", "UPPER_LIMIT", "ORIGINAL_DECISION", "CUSTOMER_NAME", "SHIPPED_QUANTITY", "SHIPPED_AT"})


def _exists(conn, kind: str, name: str) -> bool:
    return bool(query(conn, CATALOG[kind], (name,)))


def grant_app_user(conn, app_uid: str) -> list[str]:
    u = app_uid.strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,29}", u):  # identifier allowlist (cannot be bound as ?)
        raise ValueError("Invalid application user name")
    done = []
    for g in APP_GRANTS:
        execute(conn, g.format(u=u))
        done.append(g.split(" TO ")[0])
    return done


def apply_schema(conn) -> list[str]:
    created = []
    text = "\n".join(l for l in SCHEMA_FILE.read_text().splitlines() if not l.strip().startswith("--"))
    for stmt in (s.strip() for s in text.split(";")):
        if not stmt:
            continue
        m = re.match(r"CREATE\s+(TABLE|INDEX|VIEW|TRIGGER)\s+(\w+)", stmt, re.I)
        if not m:
            raise ValueError(f"Unexpected schema statement: {stmt[:60]}")
        kind, name = m.group(1).upper(), m.group(2).upper()
        if not _exists(conn, kind, name):
            execute(conn, stmt)  # constant DDL from repository file; no user input
            created.append(f"{kind} {name}")
    return created


def _insert_missing(conn, table: str, cols: list[str], rows: list[tuple]) -> int:
    if table not in FIXTURE_TABLES:  # identifier allowlist; identifiers cannot be bound as '?'
        raise ValueError(f"Table not allowlisted: {table}")
    if any(c not in FIXTURE_COLUMNS for c in cols):
        raise ValueError("Column not allowlisted")
    n = 0
    placeholders = ",".join("?" for _ in cols)
    for row in rows:
        if query(conn, f"SELECT 1 FROM {table} WHERE ID = ?", (row[0],)):  # nosec B608 - allowlisted identifier
            continue
        execute(conn, f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})", row)  # nosec B608 - allowlisted identifiers
        n += 1
    return n


def seed() -> dict:
    from config import get_settings
    settings = get_settings()
    with connect(admin=True) as conn:
        created = apply_schema(conn)
        granted = []
        if settings.admin_uid and settings.uid and settings.uid.upper() != settings.admin_uid.upper():
            granted = grant_app_user(conn, settings.uid)
        inserted = {
            "DT_INSTRUMENTS": _insert_missing(conn, "DT_INSTRUMENTS", ["ID", "NAME", "LAST_VERIFIED_AT", "VERIFICATION_REF"], INSTRUMENTS),
            "DT_LOTS": _insert_missing(conn, "DT_LOTS", ["ID", "PRODUCT_NAME", "PRODUCED_QUANTITY"], LOTS),
            "DT_INSPECTIONS": _insert_missing(
                conn,
                "DT_INSPECTIONS",
                ["ID", "INSTRUMENT_ID", "LOT_ID", "MEASURED_AT", "FUNCTION_CODE", "UNIT", "RECORDED_VALUE", "LOWER_LIMIT", "UPPER_LIMIT", "ORIGINAL_DECISION"],
                [(i, ins, lot, at, "external_diameter", "mm", v, _LO, _HI, "ACCEPTED") for i, ins, lot, at, v in INSPECTIONS],
            ),
            "DT_SHIPMENTS": _insert_missing(conn, "DT_SHIPMENTS", ["ID", "LOT_ID", "CUSTOMER_NAME", "SHIPPED_QUANTITY", "SHIPPED_AT"], SHIPMENTS),
        }
        counts = {t: query(conn, f"SELECT COUNT(*) AS N FROM {t}")[0]["N"]  # nosec B608 - constant table names
                  for t in COUNT_TABLES}
    return {"created": created, "inserted": inserted, "counts": counts, "granted_to_app_user": bool(granted)}


if __name__ == "__main__":
    result = seed()
    print("Created objects:", result["created"] or "none (already present)")
    print("Inserted rows:", result["inserted"])
    print("Row counts:", result["counts"])
    print("Least-privilege grants applied to app user:", result["granted_to_app_user"])
    sys.exit(0)
