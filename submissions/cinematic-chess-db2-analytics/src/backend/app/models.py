from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


CanonicalResult = Literal["1-0", "0-1", "1/2-1/2", "*"]
PlayerColor = Literal["white", "black"]
GameSource = Literal["played", "imported"]
AnalysisStatus = Literal["evaluated", "timeout", "error"]


class AnalysisInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ply_number: int = Field(ge=0)
    fen: str = Field(min_length=1, max_length=120)
    cp: int | None = Field(default=None, ge=-100_000, le=100_000)
    mate: int | None = Field(default=None, ge=-1_000, le=1_000)
    win_probability: float | None = Field(default=None, ge=0, le=100)
    classification: str | None = Field(default=None, max_length=32)
    status: AnalysisStatus = "evaluated"
    depth: int | None = Field(default=None, ge=1, le=1_000)
    engine: str = Field(default="stockfish", min_length=1, max_length=64)

    @field_validator("classification")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("engine")
    @classmethod
    def strip_engine(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("engine must not be blank")
        return value


class SaveGameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_game_id: UUID
    pgn: str = Field(min_length=1, max_length=1_000_000)
    result: CanonicalResult
    termination: str = Field(min_length=1, max_length=32)
    player_color: PlayerColor | None = None
    source: GameSource
    opponent_elo: int | None = Field(default=None, ge=100, le=4_000)
    time_control: str = Field(min_length=1, max_length=32)
    played_at: datetime
    opening_eco: str | None = Field(default=None, max_length=8)
    opening_name: str = Field(min_length=1, max_length=255)
    analysis: list[AnalysisInput] = Field(default_factory=list, max_length=1_000)

    @field_validator("opening_eco")
    @classmethod
    def strip_optional_value(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("termination", "time_control", "opening_name")
    @classmethod
    def strip_required_value(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value


class MoveRecord(BaseModel):
    ply_number: int
    san: str
    uci: str
    fen_after: str


class AnalysisRecord(AnalysisInput):
    pass


class GameSummary(BaseModel):
    game_id: UUID
    result: CanonicalResult
    termination: str
    player_color: PlayerColor | None
    player_outcome: Literal["win", "loss", "draw"] | None
    source: GameSource
    opponent_elo: int | None
    time_control: str
    played_at: datetime
    opening_eco: str | None
    opening_name: str
    move_count: int
    created_at: datetime


class GameDetail(GameSummary):
    pgn: str
    moves: list[MoveRecord]
    analysis: list[AnalysisRecord]


class SaveGameResponse(BaseModel):
    created: bool
    game: GameDetail


class PaginatedGames(BaseModel):
    items: list[GameSummary]
    limit: int
    offset: int
    total: int


class OpeningStat(BaseModel):
    opening_eco: str | None
    opening_name: str
    total_games: int
    wins: int
    losses: int
    draws: int
    unknown: int


class AnalyticsSummary(BaseModel):
    total_games: int
    wins: int
    losses: int
    draws: int
    unknown: int
    most_played_openings: list[OpeningStat]


class CoachingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    game_id: UUID | None = None


class CoachingResponse(BaseModel):
    provider: str
    model: str
    advice: str


class HealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    database: Literal["ok", "unavailable"]
    coaching_enabled: bool = False
    llm_provider: str | None = None


class ErrorBody(BaseModel):
    code: str
    detail: str


class ErrorResponse(BaseModel):
    error: ErrorBody

