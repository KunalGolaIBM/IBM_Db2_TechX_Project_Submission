"""Database-independent tests for FK-safe retention actions."""

import re
from pathlib import Path

from app import erasure

ROOT = Path(__file__).resolve().parents[1]


def test_seeded_retention_rules_preserve_billing_foreign_keys():
    sql = (ROOT / "sql" / "01_app_tables.sql").read_text(encoding="utf-8")
    values = sql.split("MERGE INTO RETENTION_RULES", 1)[1]
    actions = dict(re.findall(r"\('([^']+)'\s*,\s*'([^']+)'", values))

    assert actions["PATIENT"] == "ANONYMISE"
    assert actions["APPOINTMENT"] == "ANONYMISE"
    assert actions["BILLING"] == "RETAIN"


def test_bootstrap_seed_data_is_idempotent():
    sql = (ROOT / "sql" / "01_app_tables.sql").read_text(encoding="utf-8")

    assert "WHERE NOT EXISTS" in sql
    assert "WHEN NOT MATCHED THEN" in sql


def test_plan_anonymises_referenced_records_and_retains_billing(monkeypatch):
    tables = ["PRESCRIPTION", "LAB_REPORT", "BILLING", "APPOINTMENT", "PATIENT"]
    monkeypatch.setattr(erasure.discovery, "delete_order", lambda *_: tables)
    monkeypatch.setattr(
        erasure.discovery,
        "fk_column_to_root",
        lambda _schema, table, _root: "ID" if table == "PATIENT" else "PATIENT_ID",
    )
    monkeypatch.setattr(erasure, "count_rows", lambda *_: 1)
    monkeypatch.setattr(
        erasure,
        "get_pii_columns",
        lambda table: {
            "PATIENT": ["FULL_NM", "CUST_MAIL_ID"],
            "APPOINTMENT": ["DOCTOR_NM", "REASON"],
        }.get(table, []),
    )
    monkeypatch.setattr(erasure, "is_nullable", lambda *_: True)

    steps = erasure.plan(123, schema="DB2INST1")
    by_table = {step.table: step for step in steps}

    for table in ("PATIENT", "APPOINTMENT"):
        assert by_table[table].action == "ANONYMISE"
        assert by_table[table].sql.startswith("UPDATE ")
        assert "DELETE" not in by_table[table].sql

    assert by_table["BILLING"].action == "RETAIN"
    assert by_table["BILLING"].sql is None
