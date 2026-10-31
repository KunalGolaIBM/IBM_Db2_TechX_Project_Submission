from __future__ import annotations

import os

import pytest

from backend.app.config import Db2Config, load_environment, validate_schema
from backend.app.repository import Db2GameRepository


pytestmark = pytest.mark.db2


def live_config() -> Db2Config:
    load_environment()
    dsn = os.getenv("DB2_TEST_DSN", "").strip()
    if not dsn:
        pytest.skip("DB2_TEST_DSN is not set; live IBM Db2 tests are opt-in")
    return Db2Config(
        dsn=dsn,
        user=os.getenv("DB2_TEST_USER", ""),
        password=os.getenv("DB2_TEST_PASSWORD", ""),
        schema=validate_schema(os.getenv("DB2_TEST_SCHEMA", "CHESS_TEST")),
    )


def test_live_db2_connection() -> None:
    assert Db2GameRepository(live_config()).health() is True


def test_live_db2_schema_contains_exactly_the_four_chess_tables() -> None:
    config = live_config()
    try:
        import ibm_db
    except ModuleNotFoundError as exc:
        pytest.fail(f"ibm_db must be installed for live tests: {exc}")
    connection = ibm_db.connect(config.dsn, config.user, config.password)
    try:
        statement = ibm_db.prepare(
            connection,
            "SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TABNAME LIKE 'CHESS!_%' ESCAPE '!' ORDER BY TABNAME",
        )
        ibm_db.execute(statement, (config.schema,))
        names = []
        while row := ibm_db.fetch_assoc(statement):
            names.append(row["TABNAME"])
        assert names == ["CHESS_GAMES", "CHESS_GAME_ANALYSIS", "CHESS_MOVES", "CHESS_OPENING_STATISTICS"]
    finally:
        ibm_db.close(connection)
