"""SQL validation gate — the fail-closed security policy (offline, sqlglot).

Category coverage mirrors M1 requirement §7:
valid SELECT · INSERT/UPDATE/DELETE/DROP rejection · multi-statement ·
malformed · catalog deny-list · complexity/row limits.
"""

from __future__ import annotations

import pytest

from app.adapters.sql_validator.sqlglot_validator import SqlGlotValidator, resolve_dialect
from app.security.sql_policy import SqlPolicy


@pytest.fixture()
def validator() -> SqlGlotValidator:
    return SqlGlotValidator()


# -- accepted ---------------------------------------------------------------
def test_valid_select_accepted(validator):
    result = validator.validate(
        "SELECT SERVER_ID, HOSTNAME FROM DEMO_SERVERS "
        "WHERE ENVIRONMENT = 'prod' FETCH FIRST 10 ROWS ONLY"
    )
    assert result.valid is True
    assert result.statement_type == "Select"
    assert result.violations == []
    assert result.normalized_sql


def test_valid_select_with_join_accepted(validator):
    result = validator.validate(
        "SELECT s.HOSTNAME, COUNT(i.INCIDENT_ID) AS CNT "
        "FROM DEMO_SERVERS s LEFT JOIN DEMO_INCIDENTS i ON s.SERVER_ID = i.SERVER_ID "
        "GROUP BY s.HOSTNAME FETCH FIRST 10 ROWS ONLY"
    )
    assert result.valid is True


def test_valid_cte_accepted(validator):
    result = validator.validate(
        "WITH TOP AS (SELECT UPTIME_PCT FROM DEMO_SERVERS) "
        "SELECT * FROM TOP FETCH FIRST 5 ROWS ONLY"
    )
    assert result.valid is True


def test_valid_select_without_row_limit_warns(validator):
    result = validator.validate("SELECT * FROM DEMO_SERVERS")
    assert result.valid is True
    assert any(w.code == "missing_row_limit" for w in result.warnings)


# -- DML / DDL rejection ------------------------------------------------------
@pytest.mark.parametrize(
    "sql,expected_code",
    [
        ("INSERT INTO DEMO_SERVERS (SERVER_ID) VALUES (9)", "statement_not_allowed"),
        ("UPDATE DEMO_SERVERS SET UPTIME_PCT = 0", "statement_not_allowed"),
        ("DELETE FROM DEMO_INCIDENTS", "statement_not_allowed"),
        ("DROP TABLE APP.DEMO_SERVERS", "statement_not_allowed"),
        ("CREATE TABLE X (A INT)", "statement_not_allowed"),
        ("ALTER TABLE DEMO_SERVERS ADD COLUMN X INT", "statement_not_allowed"),
        ("TRUNCATE TABLE DEMO_SERVERS IMMEDIATE", "statement_not_allowed"),
        ("GRANT DBADM ON DATABASE TO USER X", "statement_not_allowed"),
        ("MERGE INTO DEMO_SERVERS AS T USING DEMO_INCIDENTS AS S ON 1=1 "
         "WHEN MATCHED THEN DELETE", "statement_not_allowed"),
    ],
)
def test_dml_ddl_rejected(validator, sql, expected_code):
    result = validator.validate(sql)
    assert result.valid is False
    assert any(v.code == expected_code for v in result.violations)


def test_select_into_rejected(validator):
    result = validator.validate("SELECT COUNT(*) INTO :n FROM DEMO_SERVERS")
    assert result.valid is False


# -- single statement / parse gate ---------------------------------------------
def test_multiple_statements_rejected(validator):
    result = validator.validate(
        "SELECT * FROM DEMO_SERVERS; DROP TABLE DEMO_SERVERS"
    )
    assert result.valid is False
    assert any(v.code == "multiple_statements" for v in result.violations)


def test_malformed_sql_fails_closed(validator):
    result = validator.validate("SELEC * FRM table")
    assert result.valid is False
    # Unparsable input must never be treated as valid.
    assert result.statement_type is None or not result.valid


def test_empty_sql_rejected(validator):
    assert validator.validate("").valid is False
    assert validator.validate("   ").valid is False


def test_null_byte_rejected(validator):
    assert validator.validate("SELECT 1\x00").valid is False


def test_control_characters_rejected(validator):
    assert validator.validate("SELECT \x01 1 FROM DEMO_SERVERS").valid is False


def test_over_length_rejected(validator):
    sql = "SELECT " + "A" * 6000 + " FROM DEMO_SERVERS"
    result = validator.validate(sql)
    assert result.valid is False
    assert any(v.code == "max_length_exceeded" for v in result.violations)


# -- catalog deny-list ----------------------------------------------------------
@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM SYSCAT.TABLES",
        "SELECT * FROM SYSIBM.SYSTABLES",
        "SELECT * FROM SYSIBMADM.SNAPDB",
        "SELECT * FROM SYSTOOLS.ADMIN_TASKS",
        "SELECT * FROM db2inst1.SYSCAT.TABLES",
    ],
)
def test_restricted_catalog_access_rejected(validator, sql):
    result = validator.validate(sql)
    assert result.valid is False


def test_denied_function_rejected(validator):
    result = validator.validate("SELECT ADMIN_CMD('db2look') FROM SYSIBM.SYSDUMMY1")
    assert result.valid is False


# -- complexity / row limits ------------------------------------------------------
def test_too_many_joins_rejected():
    policy = SqlPolicy(max_joins=1)
    small = SqlGlotValidator(policy)
    sql = (
        "SELECT * FROM DEMO_SERVERS A "
        "JOIN DEMO_INCIDENTS B ON A.SERVER_ID = B.SERVER_ID "
        "JOIN DEMO_SERVERS C ON B.SERVER_ID = C.SERVER_ID"
    )
    result = small.validate(sql)
    assert result.valid is False
    assert any(v.code == "too_many_joins" for v in result.violations)


def test_in_list_limit_enforced():
    policy = SqlPolicy(max_in_list=3)
    small = SqlGlotValidator(policy)
    result = small.validate("SELECT * FROM DEMO_SERVERS WHERE SERVER_ID IN (1,2,3,4,5)")
    assert result.valid is False
    assert any(v.code == "in_list_too_large" for v in result.violations)


def test_subquery_limit_enforced():
    policy = SqlPolicy(max_subqueries=1)
    small = SqlGlotValidator(policy)
    sql = (
        "SELECT * FROM DEMO_SERVERS WHERE SERVER_ID IN "
        "(SELECT SERVER_ID FROM DEMO_INCIDENTS WHERE SEVERITY IN "
        "(SELECT SEVERITY FROM DEMO_INCIDENTS WHERE SEVERITY > 1))"
    )
    result = small.validate(sql)
    assert result.valid is False
    assert any(v.code == "too_many_subqueries" for v in result.violations)


def test_applied_policy_echoed(validator):
    result = validator.validate("SELECT * FROM DEMO_SERVERS FETCH FIRST 10 ROWS ONLY")
    assert result.policy.max_rows == 100
    assert result.policy.timeout_ms == 10000
    assert result.policy.enforce_row_limit is True


def test_db2_dialect_resolution():
    dialect_key, source = resolve_dialect()
    assert "db2" in (dialect_key, source)  # plugin present or generic fallback
    assert source in ("db2-sqlglot-dialect", "sqlglot", "db2", "sqlglot-generic")
