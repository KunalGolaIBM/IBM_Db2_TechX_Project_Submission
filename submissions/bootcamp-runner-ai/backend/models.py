from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class AttemptIn(BaseModel):
    learner_id: str = Field(min_length=1, max_length=128)
    topic: str = Field(min_length=1, max_length=200)
    score: float = Field(ge=0, le=100)
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    questions_count: int = Field(default=1, ge=1, le=500)


class Attempt(AttemptIn):
    id: int
    attempted_at: datetime | None = None


class RecommendationIn(BaseModel):
    learner_id: str = Field(min_length=1, max_length=128)
    topic: str = Field(min_length=1, max_length=200)
    recommendation: str = Field(min_length=1, max_length=4000)
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    source: str = Field(default="agent", max_length=40)


class LearningProfileIn(BaseModel):
    learner_id: str = Field(min_length=1, max_length=128)
    strengths: str = Field(default="", max_length=4000)
    weaknesses: str = Field(default="", max_length=4000)
    preferred_difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")


class AdaptiveSessionIn(BaseModel):
    learner_id: str = Field(min_length=1, max_length=128)
    topic: str = Field(min_length=1, max_length=200)
    requested_difficulty: str | None = Field(default=None, pattern="^(easy|medium|hard)$")
