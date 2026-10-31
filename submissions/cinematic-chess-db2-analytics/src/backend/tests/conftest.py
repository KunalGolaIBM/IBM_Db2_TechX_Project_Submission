from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from backend.app.config import Db2Config, Settings
from backend.app.domain import GameData
from backend.app.errors import CoachingDisabledError, GameConflictError, GameNotFoundError
from backend.app.models import (
    AnalysisRecord,
    AnalyticsSummary,
    CoachingResponse,
    GameDetail,
    GameSummary,
    MoveRecord,
    OpeningStat,
    PaginatedGames,
)


def request_payload(game_id: UUID | None = None) -> dict:
    return {
        "client_game_id": str(game_id or uuid4()),
        "pgn": '[Event "Test"]\n[Result "1-0"]\n\n1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0',
        "result": "1-0",
        "termination": "checkmate",
        "player_color": "white",
        "source": "played",
        "opponent_elo": 1200,
        "time_control": "5 min",
        "played_at": "2026-10-31T10:00:00Z",
        "opening_eco": "C20",
        "opening_name": "King's Pawn Game",
        "analysis": [],
    }


def detail_from_game(game: GameData) -> GameDetail:
    created_at = datetime(2026, 10, 31, 10, 1, 0, tzinfo=timezone.utc)
    return GameDetail(
        game_id=UUID(game.game_id),
        pgn=game.pgn,
        result=game.result,
        termination=game.termination,
        player_color=None if game.player_color == "unknown" else game.player_color,
        player_outcome=None if game.player_outcome == "unknown" else game.player_outcome,
        source=game.source,
        opponent_elo=game.opponent_elo,
        time_control=game.time_control,
        played_at=game.played_at,
        opening_eco=game.opening_code,
        opening_name=game.opening_name,
        move_count=len(game.moves),
        created_at=created_at,
        moves=[MoveRecord(**vars(move)) for move in game.moves],
        analysis=[AnalysisRecord(**vars(item)) for item in game.analysis],
    )


class FakeRepository:
    def __init__(self) -> None:
        self.games: dict[str, tuple[GameData, GameDetail]] = {}

    def health(self) -> bool:
        return True

    def save_game(self, game: GameData) -> tuple[GameDetail, bool]:
        existing = self.games.get(game.game_id)
        if existing:
            if existing[0] != game:
                raise GameConflictError("different game")
            return existing[1], False
        detail = detail_from_game(game)
        self.games[game.game_id] = (game, detail)
        return detail, True

    def list_games(self, limit: int, offset: int) -> PaginatedGames:
        details = [value[1] for value in self.games.values()]
        items = [GameSummary(**detail.model_dump(exclude={"pgn", "moves", "analysis"})) for detail in details[offset:offset + limit]]
        return PaginatedGames(items=items, limit=limit, offset=offset, total=len(details))

    def get_game(self, game_id: UUID | str) -> GameDetail:
        try:
            return self.games[str(game_id)][1]
        except KeyError as exc:
            raise GameNotFoundError("not found") from exc

    def analytics_summary(self) -> AnalyticsSummary:
        details = [value[1] for value in self.games.values()]
        wins = sum(item.player_outcome == "win" for item in details)
        losses = sum(item.player_outcome == "loss" for item in details)
        draws = sum(item.player_outcome == "draw" for item in details)
        unknown = len(details) - wins - losses - draws
        by_opening: dict[tuple[str | None, str], list[GameDetail]] = {}
        for item in details:
            by_opening.setdefault((item.opening_eco, item.opening_name), []).append(item)
        openings = [
            OpeningStat(
                opening_eco=key[0], opening_name=key[1], total_games=len(values),
                wins=sum(item.player_outcome == "win" for item in values),
                losses=sum(item.player_outcome == "loss" for item in values),
                draws=sum(item.player_outcome == "draw" for item in values),
                unknown=sum(item.player_outcome is None for item in values),
            )
            for key, values in by_opening.items()
        ]
        return AnalyticsSummary(total_games=len(details), wins=wins, losses=losses, draws=draws, unknown=unknown, most_played_openings=openings)


class FakeCoach:
    def generate(self, summary: AnalyticsSummary, game: GameDetail | None) -> CoachingResponse:
        return CoachingResponse(provider="fake", model="deterministic", advice=f"Reviewed {summary.total_games} games.")


class DisabledCoach:
    def generate(self, summary: AnalyticsSummary, game: GameDetail | None) -> CoachingResponse:
        raise CoachingDisabledError("AI coaching is disabled")


@pytest.fixture
def settings() -> Settings:
    return Settings(
        db2=Db2Config(dsn="unused-in-fake", user="", password="", schema="CHESS"),
        cors_origins=("http://localhost:5173",),
        coach_provider="disabled",
        coach_model="llama3.2",
        ollama_base_url="http://localhost:11434",
        openai_api_key="",
    )

