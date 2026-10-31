from __future__ import annotations

import importlib
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from .config import Db2Config, validate_schema
from .domain import GameData
from .errors import DatabaseUnavailableError, GameConflictError, GameNotFoundError
from .models import (
    AnalysisRecord,
    AnalyticsSummary,
    GameDetail,
    GameSummary,
    MoveRecord,
    OpeningStat,
    PaginatedGames,
)


TABLES = {
    "games": "CHESS_GAMES",
    "moves": "CHESS_MOVES",
    "analysis": "CHESS_GAME_ANALYSIS",
    "openings": "CHESS_OPENING_STATISTICS",
}


def _clob(value: Any) -> str:
    if hasattr(value, "read"):
        value = value.read()
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def _nullable_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _utc_datetime(value: Any) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class Db2GameRepository:
    """Synchronous Db2 gateway. FastAPI runs sync routes in its thread pool."""

    def __init__(self, config: Db2Config, driver: Any | None = None) -> None:
        self.config = Db2Config(config.dsn, config.user, config.password, validate_schema(config.schema))
        self._injected_driver = driver

    @property
    def driver(self) -> Any:
        if self._injected_driver is not None:
            return self._injected_driver
        try:
            return importlib.import_module("ibm_db")
        except ModuleNotFoundError as exc:
            raise DatabaseUnavailableError("The ibm_db runtime dependency is not installed") from exc

    def _table(self, name: str) -> str:
        return f'"{self.config.schema}"."{TABLES[name]}"'

    def _connect(self) -> Any:
        self.config.require_dsn()
        try:
            return self.driver.connect(self.config.dsn, self.config.user, self.config.password)
        except Exception as exc:
            raise DatabaseUnavailableError("Db2 connection failed") from exc

    def _close(self, connection: Any) -> None:
        try:
            self.driver.close(connection)
        except Exception:
            pass

    def _rollback(self, connection: Any) -> None:
        try:
            self.driver.rollback(connection)
        except Exception:
            pass

    def _execute(self, connection: Any, sql: str, params: tuple[Any, ...] = ()) -> Any:
        statement = self.driver.prepare(connection, sql)
        self.driver.execute(statement, params)
        return statement

    def _fetch_one(self, connection: Any, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        statement = self._execute(connection, sql, params)
        row = self.driver.fetch_assoc(statement)
        return dict(row) if row else None

    def _fetch_all(self, connection: Any, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        statement = self._execute(connection, sql, params)
        rows: list[dict[str, Any]] = []
        while row := self.driver.fetch_assoc(statement):
            rows.append(dict(row))
        return rows

    @staticmethod
    def _summary(row: dict[str, Any]) -> GameSummary:
        color = str(row["PLAYER_COLOR"]).strip()
        outcome = str(row["PLAYER_OUTCOME"]).strip()
        return GameSummary(
            game_id=UUID(str(row["GAME_ID"]).strip()),
            result=str(row["RESULT"]).strip(),
            termination=str(row["TERMINATION"]).strip(),
            player_color=None if color == "unknown" else color,
            player_outcome=None if outcome == "unknown" else outcome,
            source=str(row["SOURCE"]).strip(),
            opponent_elo=int(row["OPPONENT_ELO"]) if row.get("OPPONENT_ELO") is not None else None,
            time_control=str(row["TIME_CONTROL"]).strip(),
            played_at=_utc_datetime(row["PLAYED_AT"]),
            opening_eco=_nullable_text(row.get("OPENING_CODE")),
            opening_name=str(row["OPENING_NAME"]).strip(),
            move_count=int(row.get("MOVE_COUNT") or 0),
            created_at=_utc_datetime(row["CREATED_AT"]),
        )

    def _detail_on_connection(self, connection: Any, game_id: str) -> GameDetail | None:
        games = self._table("games")
        moves = self._table("moves")
        analysis = self._table("analysis")
        row = self._fetch_one(
            connection,
            f"""
            SELECT G.*, (SELECT COUNT(*) FROM {moves} M WHERE M.GAME_ID = G.GAME_ID) AS MOVE_COUNT
            FROM {games} G WHERE G.GAME_ID = ?
            """,
            (game_id,),
        )
        if row is None:
            return None
        move_rows = self._fetch_all(
            connection,
            f"SELECT PLY_NUMBER, SAN, UCI, FEN_AFTER FROM {moves} WHERE GAME_ID = ? ORDER BY PLY_NUMBER",
            (game_id,),
        )
        analysis_rows = self._fetch_all(
            connection,
            f"""
            SELECT PLY_NUMBER, FEN, CP, MATE, WIN_PROBABILITY, CLASSIFICATION, ENGINE, DEPTH, STATUS
            FROM {analysis} WHERE GAME_ID = ? ORDER BY PLY_NUMBER
            """,
            (game_id,),
        )
        summary = self._summary(row)
        return GameDetail(
            **summary.model_dump(),
            pgn=_clob(row["PGN"]),
            moves=[
                MoveRecord(
                    ply_number=int(move["PLY_NUMBER"]),
                    san=str(move["SAN"]),
                    uci=str(move["UCI"]),
                    fen_after=str(move["FEN_AFTER"]),
                )
                for move in move_rows
            ],
            analysis=[
                AnalysisRecord(
                    ply_number=int(item["PLY_NUMBER"]),
                    fen=str(item["FEN"]),
                    cp=int(item["CP"]) if item.get("CP") is not None else None,
                    mate=int(item["MATE"]) if item.get("MATE") is not None else None,
                    win_probability=float(item["WIN_PROBABILITY"]) if item.get("WIN_PROBABILITY") is not None else None,
                    classification=_nullable_text(item.get("CLASSIFICATION")),
                    engine=str(item["ENGINE"]),
                    depth=int(item["DEPTH"]) if item.get("DEPTH") is not None else None,
                    status=str(item["STATUS"]),
                )
                for item in analysis_rows
            ],
        )

    @staticmethod
    def _is_same(existing: GameDetail, game: GameData) -> bool:
        expected_moves = [(m.ply_number, m.san, m.uci, m.fen_after) for m in game.moves]
        stored_moves = [(m.ply_number, m.san, m.uci, m.fen_after) for m in existing.moves]
        expected_analysis = [
            (a.ply_number, a.fen, a.cp, a.mate, a.win_probability, a.classification, a.engine, a.depth, a.status)
            for a in game.analysis
        ]
        stored_analysis = [
            (a.ply_number, a.fen, a.cp, a.mate, a.win_probability, a.classification, a.engine, a.depth, a.status)
            for a in existing.analysis
        ]
        return (
            existing.pgn.strip() == game.pgn.strip()
            and existing.result == game.result
            and existing.termination == game.termination
            and (existing.player_color or "unknown") == game.player_color
            and (existing.player_outcome or "unknown") == game.player_outcome
            and existing.source == game.source
            and existing.opponent_elo == game.opponent_elo
            and existing.time_control == game.time_control
            and existing.played_at == game.played_at
            and existing.opening_eco == game.opening_code
            and existing.opening_name == game.opening_name
            and expected_moves == stored_moves
            and expected_analysis == stored_analysis
        )

    def health(self) -> bool:
        connection = self._connect()
        try:
            self._fetch_one(connection, "SELECT 1 AS OK FROM SYSIBM.SYSDUMMY1")
            return True
        except Exception as exc:
            raise DatabaseUnavailableError("Db2 health check failed") from exc
        finally:
            self._close(connection)

    def save_game(self, game: GameData) -> tuple[GameDetail, bool]:
        connection = self._connect()
        games = self._table("games")
        moves = self._table("moves")
        analysis = self._table("analysis")
        openings = self._table("openings")
        saved_at = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            self.driver.autocommit(connection, self.driver.SQL_AUTOCOMMIT_OFF)
            existing = self._detail_on_connection(connection, game.game_id)
            if existing is not None:
                if self._is_same(existing, game):
                    self.driver.commit(connection)
                    return existing, False
                raise GameConflictError("client_game_id is already used by a different game")

            self._fetch_one(
                connection,
                f"""
                SELECT GAME_ID, CREATED_AT FROM FINAL TABLE (
                    INSERT INTO {games} (
                        GAME_ID, PGN, RESULT, TERMINATION, PLAYER_COLOR, PLAYER_OUTCOME,
                        OPENING_CODE, OPENING_NAME, PLAYED_AT, OPPONENT_ELO,
                        TIME_CONTROL, SOURCE, CREATED_AT
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                )
                """,
                (
                    game.game_id, game.pgn, game.result, game.termination, game.player_color,
                    game.player_outcome, game.opening_code, game.opening_name,
                    game.played_at.astimezone(timezone.utc).replace(tzinfo=None),
                    game.opponent_elo, game.time_control, game.source, saved_at,
                ),
            )
            for move in game.moves:
                self._execute(
                    connection,
                    f"INSERT INTO {moves} (GAME_ID, PLY_NUMBER, SAN, UCI, FEN_AFTER) VALUES (?, ?, ?, ?, ?)",
                    (game.game_id, move.ply_number, move.san, move.uci, move.fen_after),
                )
            for item in game.analysis:
                self._execute(
                    connection,
                    f"""
                    INSERT INTO {analysis} (
                        GAME_ID, PLY_NUMBER, FEN, CP, MATE, WIN_PROBABILITY,
                        CLASSIFICATION, ENGINE, DEPTH, STATUS
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        game.game_id, item.ply_number, item.fen, item.cp, item.mate,
                        item.win_probability, item.classification, item.engine, item.depth, item.status,
                    ),
                )

            increments = {
                "win": (1, 0, 0, 0),
                "loss": (0, 1, 0, 0),
                "draw": (0, 0, 1, 0),
                "unknown": (0, 0, 0, 1),
            }[game.player_outcome]
            self._execute(
                connection,
                f"""
                MERGE INTO {openings} AS T
                USING (VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)) AS S (
                    OPENING_KEY, OPENING_CODE, OPENING_NAME, TOTAL_GAMES,
                    WINS, LOSSES, DRAWS, UNKNOWN_GAMES, UPDATED_AT
                ) ON T.OPENING_KEY = S.OPENING_KEY
                WHEN MATCHED THEN UPDATE SET
                    TOTAL_GAMES = T.TOTAL_GAMES + 1,
                    WINS = T.WINS + S.WINS,
                    LOSSES = T.LOSSES + S.LOSSES,
                    DRAWS = T.DRAWS + S.DRAWS,
                    UNKNOWN_GAMES = T.UNKNOWN_GAMES + S.UNKNOWN_GAMES,
                    UPDATED_AT = S.UPDATED_AT
                WHEN NOT MATCHED THEN INSERT (
                    OPENING_KEY, OPENING_CODE, OPENING_NAME, TOTAL_GAMES,
                    WINS, LOSSES, DRAWS, UNKNOWN_GAMES, UPDATED_AT
                ) VALUES (
                    S.OPENING_KEY, S.OPENING_CODE, S.OPENING_NAME, S.TOTAL_GAMES,
                    S.WINS, S.LOSSES, S.DRAWS, S.UNKNOWN_GAMES, S.UPDATED_AT
                )
                """,
                (game.opening_key, game.opening_code, game.opening_name, *increments, saved_at),
            )
            created = self._detail_on_connection(connection, game.game_id)
            if created is None:
                raise DatabaseUnavailableError("Saved game could not be read back")
            self.driver.commit(connection)
            return created, True
        except GameConflictError:
            self._rollback(connection)
            raise
        except Exception as exc:
            self._rollback(connection)
            # A concurrent retry may have committed the same UUID first.
            try:
                existing = self._detail_on_connection(connection, game.game_id)
            except Exception:
                existing = None
            if existing is not None:
                if self._is_same(existing, game):
                    return existing, False
                raise GameConflictError("client_game_id is already used by a different game") from None
            if isinstance(exc, DatabaseUnavailableError):
                raise
            raise DatabaseUnavailableError("Db2 save transaction failed") from exc
        finally:
            self._close(connection)

    def list_games(self, limit: int, offset: int) -> PaginatedGames:
        connection = self._connect()
        games = self._table("games")
        moves = self._table("moves")
        try:
            count_row = self._fetch_one(connection, f"SELECT COUNT(*) AS TOTAL FROM {games}") or {"TOTAL": 0}
            rows = self._fetch_all(
                connection,
                f"""
                SELECT G.*, (SELECT COUNT(*) FROM {moves} M WHERE M.GAME_ID = G.GAME_ID) AS MOVE_COUNT
                FROM {games} G
                ORDER BY G.PLAYED_AT DESC, G.CREATED_AT DESC, G.GAME_ID DESC
                OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
                """,
                (offset, limit),
            )
            return PaginatedGames(items=[self._summary(row) for row in rows], limit=limit, offset=offset, total=int(count_row["TOTAL"]))
        except Exception as exc:
            raise DatabaseUnavailableError("Db2 game listing failed") from exc
        finally:
            self._close(connection)

    def get_game(self, game_id: UUID | str) -> GameDetail:
        connection = self._connect()
        try:
            game = self._detail_on_connection(connection, str(game_id))
            if game is None:
                raise GameNotFoundError("Saved game was not found")
            return game
        except GameNotFoundError:
            raise
        except Exception as exc:
            raise DatabaseUnavailableError("Db2 game lookup failed") from exc
        finally:
            self._close(connection)

    def analytics_summary(self) -> AnalyticsSummary:
        connection = self._connect()
        games = self._table("games")
        openings = self._table("openings")
        try:
            totals = self._fetch_one(
                connection,
                f"""
                SELECT COUNT(*) AS TOTAL_GAMES,
                    COALESCE(SUM(CASE WHEN PLAYER_OUTCOME = 'win' THEN 1 ELSE 0 END), 0) AS WINS,
                    COALESCE(SUM(CASE WHEN PLAYER_OUTCOME = 'loss' THEN 1 ELSE 0 END), 0) AS LOSSES,
                    COALESCE(SUM(CASE WHEN PLAYER_OUTCOME = 'draw' THEN 1 ELSE 0 END), 0) AS DRAWS,
                    COALESCE(SUM(CASE WHEN PLAYER_OUTCOME = 'unknown' THEN 1 ELSE 0 END), 0) AS UNKNOWN_GAMES
                FROM {games}
                """,
            ) or {}
            opening_rows = self._fetch_all(
                connection,
                f"""
                SELECT OPENING_CODE, OPENING_NAME, TOTAL_GAMES, WINS, LOSSES, DRAWS, UNKNOWN_GAMES
                FROM {openings}
                ORDER BY TOTAL_GAMES DESC, OPENING_NAME ASC
                FETCH FIRST 10 ROWS ONLY
                """,
            )
            return AnalyticsSummary(
                total_games=int(totals.get("TOTAL_GAMES") or 0),
                wins=int(totals.get("WINS") or 0),
                losses=int(totals.get("LOSSES") or 0),
                draws=int(totals.get("DRAWS") or 0),
                unknown=int(totals.get("UNKNOWN_GAMES") or 0),
                most_played_openings=[
                    OpeningStat(
                        opening_eco=_nullable_text(row.get("OPENING_CODE")),
                        opening_name=str(row["OPENING_NAME"]),
                        total_games=int(row["TOTAL_GAMES"]),
                        wins=int(row["WINS"]),
                        losses=int(row["LOSSES"]),
                        draws=int(row["DRAWS"]),
                        unknown=int(row["UNKNOWN_GAMES"]),
                    )
                    for row in opening_rows
                ],
            )
        except Exception as exc:
            raise DatabaseUnavailableError("Db2 analytics query failed") from exc
        finally:
            self._close(connection)
