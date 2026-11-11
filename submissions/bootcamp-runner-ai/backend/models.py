from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Difficulty = Literal["easy", "medium", "hard"]


class PlayerProfileIn(BaseModel):
    player_id: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    strengths: str = Field(default="", max_length=4000)
    growth_areas: str = Field(default="", max_length=4000)
    preferred_difficulty: Difficulty = "medium"


class PlayerProfile(PlayerProfileIn):
    created_at: datetime | None = None
    updated_at: datetime | None = None


class GameSessionIn(BaseModel):
    player_id: str = Field(min_length=1, max_length=128)
    mode: str = Field(default="career", min_length=1, max_length=80)
    difficulty: Difficulty = "medium"


class ScoreIn(BaseModel):
    session_id: int = Field(gt=0)
    player_id: str = Field(min_length=1, max_length=128)
    score: int = Field(ge=0)


class CharacterUnlockIn(BaseModel):
    player_id: str = Field(min_length=1, max_length=128)
    character_key: str = Field(min_length=1, max_length=80)


class AchievementIn(BaseModel):
    player_id: str = Field(min_length=1, max_length=128)
    achievement_key: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)


class MissionIn(BaseModel):
    player_id: str = Field(min_length=1, max_length=128)
    mission_key: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    status: Literal["available", "active", "completed"] = "available"


class AssistantRequest(BaseModel):
    player_id: str = Field(min_length=1, max_length=128)
    objective: str = Field(min_length=1, max_length=2000)
    requested_difficulty: Difficulty | None = None


class AdaptiveChallengeRequest(AssistantRequest):
    pass
