"""Offline checks for the bootstrap SQL splitter and clinic schema."""

from pathlib import Path

from app.bootstrap import split_sql

ROOT = Path(__file__).resolve().parents[1]


def test_clinic_schema_comments_do_not_hide_create_statements():
    schema_path = ROOT / "sql" / "00_schema_clinic.sql"
    schema_text = schema_path.read_text(encoding="utf-8")
    statements = split_sql(schema_text)
    create_tables = [statement for statement in statements if statement.startswith("CREATE TABLE")]

    assert "--" in schema_text
    assert len(create_tables) == 7
    assert all("GENERATED ALWAYS AS IDENTITY" in statement for statement in create_tables)


def test_all_bootstrap_sql_creates_required_tables():
    table_names = set()
    for sql_path in (
        ROOT / "sql" / "00_schema_clinic.sql",
        ROOT / "sql" / "01_app_tables.sql",
        ROOT / "sql" / "02_consent_temporal.sql",
    ):
        for statement in split_sql(sql_path.read_text(encoding="utf-8")):
            if statement.startswith("CREATE TABLE"):
                table_names.add(statement.split()[2].strip('"').upper())

    assert {
        "PATIENT",
        "APPOINTMENT",
        "BILLING",
        "PRESCRIPTION",
        "LAB_REPORT",
        "SUPPORT_TICKET",
        "MARKETING_LIST",
        "PII_MAP",
        "RETENTION_RULES",
        "REQUESTS",
        "AUDIT_LOG",
        "CONSENT",
        "CONSENT_HISTORY",
    } <= table_names


def test_split_ignores_semicolon_inside_string():
    sql = "INSERT INTO T VALUES ('a; b');\nINSERT INTO T VALUES ('c');"

    assert split_sql(sql) == [
        "INSERT INTO T VALUES ('a; b')",
        "INSERT INTO T VALUES ('c')",
    ]


def test_split_ignores_comment_marker_inside_string():
    sql = "INSERT INTO T VALUES ('x -- y');"

    assert split_sql(sql) == ["INSERT INTO T VALUES ('x -- y')"]


def test_split_handles_escaped_quote():
    sql = "INSERT INTO T VALUES ('it''s; fine');"

    assert split_sql(sql) == ["INSERT INTO T VALUES ('it''s; fine')"]
