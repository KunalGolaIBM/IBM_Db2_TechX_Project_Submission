from __future__ import annotations

from typing import Any

import pytest

from backend.app.config import Db2Config
from backend.app.errors import DatabaseUnavailableError
from backend.app.models import SaveGameRequest
from backend.app.pgn import parse_game
from backend.app.repository import Db2GameRepository

from .conftest import detail_from_game, request_payload


class FakeDriver:
    SQL_AUTOCOMMIT_OFF = 0

    def __init__(self, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = 0

    def connect(self, dsn: str, user: str, password: str) -> object:
        return object()

    def autocommit(self, connection: object, mode: int) -> None:
        assert mode == self.SQL_AUTOCOMMIT_OFF

    def prepare(self, connection: object, sql: str) -> dict[str, Any]:
        return {"sql": sql, "rows": []}

    def execute(self, statement: dict[str, Any], params: tuple[Any, ...]) -> None:
        sql = statement["sql"]
        self.executed.append((sql, params))
        if self.fail_on and self.fail_on in sql:
            raise RuntimeError("injected Db2 failure")
        if "FINAL TABLE" in sql:
            statement["rows"] = [{"GAME_ID": params[0], "CREATED_AT": "2026-10-31 10:01:00"}]

    def fetch_assoc(self, statement: dict[str, Any]) -> dict[str, Any] | None:
        return statement["rows"].pop(0) if statement["rows"] else None

    def commit(self, connection: object) -> None:
        self.commits += 1

    def rollback(self, connection: object) -> None:
        self.rollbacks += 1

    def close(self, connection: object) -> None:
        self.closed += 1


class SaveRepository(Db2GameRepository):
    def __init__(self, driver: FakeDriver, return_created: bool = True) -> None:
        super().__init__(Db2Config("dsn", "user", "password", "CHESS"), driver)
        self.return_created = return_created
        self.detail_calls = 0
        self.created_detail = None

    def _detail_on_connection(self, connection: object, game_id: str):
        self.detail_calls += 1
        if self.return_created and self.detail_calls > 1:
            return self.created_detail
        return None


def test_save_uses_parameterized_sql_final_table_and_one_commit() -> None:
    game = parse_game(SaveGameRequest.model_validate(request_payload()))
    driver = FakeDriver()
    repository = SaveRepository(driver)
    repository.created_detail = detail_from_game(game)

    saved, created = repository.save_game(game)

    assert created is True and saved.game_id == repository.created_detail.game_id
    assert driver.commits == 1
    assert driver.rollbacks == 0
    assert driver.closed == 1
    sql = "\n".join(statement for statement, _ in driver.executed)
    assert "FINAL TABLE" in sql
    assert "MERGE INTO" in sql
    assert game.pgn not in sql
    assert all("?" in statement for statement, _ in driver.executed)
    assert any(params and params[0] == game.game_id for _, params in driver.executed)


def test_idempotent_retry_does_not_insert_or_increment_projection() -> None:
    game = parse_game(SaveGameRequest.model_validate(request_payload()))
    driver = FakeDriver()
    repository = SaveRepository(driver)
    repository.created_detail = detail_from_game(game)
    repository.detail_calls = 1

    saved, created = repository.save_game(game)

    assert created is False and saved.game_id == repository.created_detail.game_id
    assert driver.executed == []
    assert driver.commits == 1
    assert driver.rollbacks == 0


def test_save_rolls_back_every_table_on_child_insert_failure() -> None:
    game = parse_game(SaveGameRequest.model_validate(request_payload()))
    driver = FakeDriver(fail_on="CHESS_MOVES")
    repository = SaveRepository(driver, return_created=False)

    with pytest.raises(DatabaseUnavailableError, match="save transaction failed"):
        repository.save_game(game)

    assert driver.commits == 0
    assert driver.rollbacks == 1
    assert driver.closed == 1


def test_save_rolls_back_when_transaction_cannot_be_read_back() -> None:
    game = parse_game(SaveGameRequest.model_validate(request_payload()))
    driver = FakeDriver()
    repository = SaveRepository(driver, return_created=False)

    with pytest.raises(DatabaseUnavailableError, match="could not be read back"):
        repository.save_game(game)

    assert driver.commits == 0
    assert driver.rollbacks == 1
    assert driver.closed == 1


def test_schema_identifier_is_validated_before_sql_interpolation() -> None:
    with pytest.raises(ValueError, match="valid unquoted Db2 identifier"):
        Db2GameRepository(Db2Config("dsn", "", "", "CHESS; DROP TABLE X"), FakeDriver())

