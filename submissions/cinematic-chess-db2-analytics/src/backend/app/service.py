from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .domain import GameData
from .models import (
    AnalyticsSummary,
    CoachingResponse,
    GameDetail,
    PaginatedGames,
    SaveGameRequest,
    SaveGameResponse,
)
from .pgn import parse_game


class GameRepository(Protocol):
    def health(self) -> bool: ...
    def save_game(self, game: GameData) -> tuple[GameDetail, bool]: ...
    def list_games(self, limit: int, offset: int) -> PaginatedGames: ...
    def get_game(self, game_id: UUID | str) -> GameDetail: ...
    def analytics_summary(self) -> AnalyticsSummary: ...


class Coach(Protocol):
    def generate(self, summary: AnalyticsSummary, game: GameDetail | None) -> CoachingResponse: ...


class ChessService:
    def __init__(self, repository: GameRepository, coach: Coach) -> None:
        self.repository = repository
        self.coach = coach

    def health(self) -> bool:
        return self.repository.health()

    def save_game(self, request: SaveGameRequest) -> SaveGameResponse:
        game, created = self.repository.save_game(parse_game(request))
        return SaveGameResponse(created=created, game=game)

    def list_games(self, limit: int, offset: int) -> PaginatedGames:
        return self.repository.list_games(limit, offset)

    def get_game(self, game_id: UUID) -> GameDetail:
        return self.repository.get_game(game_id)

    def analytics_summary(self) -> AnalyticsSummary:
        return self.repository.analytics_summary()

    def coaching(self, game_id: UUID | None) -> CoachingResponse:
        # Db2 facts are always loaded before any optional LLM is called.
        summary = self.repository.analytics_summary()
        game = self.repository.get_game(game_id) if game_id else None
        return self.coach.generate(summary, game)

