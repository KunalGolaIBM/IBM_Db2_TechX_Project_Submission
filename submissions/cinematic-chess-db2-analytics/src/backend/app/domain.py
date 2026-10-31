from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class MoveData:
    ply_number: int
    san: str
    uci: str
    fen_after: str


@dataclass(frozen=True)
class AnalysisData:
    ply_number: int
    fen: str
    cp: int | None
    mate: int | None
    win_probability: float | None
    classification: str | None
    engine: str
    depth: int | None
    status: str


@dataclass(frozen=True)
class GameData:
    game_id: str
    pgn: str
    result: str
    termination: str
    player_color: Literal["white", "black", "unknown"]
    player_outcome: Literal["win", "loss", "draw", "unknown"]
    source: str
    opponent_elo: int | None
    time_control: str
    played_at: datetime
    opening_code: str | None
    opening_name: str
    moves: tuple[MoveData, ...]
    analysis: tuple[AnalysisData, ...]

    @property
    def opening_key(self) -> str:
        return f"{self.opening_code or ''}|{self.opening_name}"
