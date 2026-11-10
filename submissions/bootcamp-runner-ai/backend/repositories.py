from __future__ import annotations

from typing import Any

from .db import Db2Client
from .models import AttemptIn, LearningProfileIn, RecommendationIn


class Repository:
    def __init__(self, db: Db2Client) -> None:
        self.db = db

    def get_learner(self, learner_id: str) -> dict[str, Any] | None:
        rows = self.db.execute(
            "SELECT learner_id, name, email, created_at FROM learners WHERE learner_id = ?", (learner_id,)
        )
        return rows[0] if rows else None

    def get_learning_history(self, learner_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return self.db.execute(
            "SELECT id, topic, score, difficulty, questions_count, attempted_at "
            "FROM quiz_attempts WHERE learner_id = ? ORDER BY attempted_at DESC FETCH FIRST ? ROWS ONLY",
            (learner_id, limit),
        )

    def save_attempt(self, attempt: AttemptIn) -> dict[str, Any]:
        self.db.execute(
            "INSERT INTO quiz_attempts "
            "(learner_id, topic, score, difficulty, questions_count) VALUES (?, ?, ?, ?, ?)",
            (attempt.learner_id, attempt.topic, attempt.score, attempt.difficulty, attempt.questions_count),
        )
        return attempt.model_dump()

    def get_profile(self, learner_id: str) -> dict[str, Any] | None:
        rows = self.db.execute(
            "SELECT learner_id, strengths, weaknesses, preferred_difficulty, updated_at "
            "FROM learning_profiles WHERE learner_id = ?", (learner_id,)
        )
        return rows[0] if rows else None

    def save_profile(self, profile: LearningProfileIn) -> dict[str, Any]:
        self.db.execute(
            "MERGE INTO learning_profiles AS target USING "
            "(VALUES (?, ?, ?, ?)) AS source(learner_id, strengths, weaknesses, preferred_difficulty) "
            "ON target.learner_id = source.learner_id "
            "WHEN MATCHED THEN UPDATE SET strengths = source.strengths, weaknesses = source.weaknesses, "
            "preferred_difficulty = source.preferred_difficulty, updated_at = CURRENT TIMESTAMP "
            "WHEN NOT MATCHED THEN INSERT (learner_id, strengths, weaknesses, preferred_difficulty) "
            "VALUES (source.learner_id, source.strengths, source.weaknesses, source.preferred_difficulty)",
            (profile.learner_id, profile.strengths, profile.weaknesses, profile.preferred_difficulty),
        )
        return profile.model_dump()

    def save_recommendation(self, recommendation: RecommendationIn) -> dict[str, Any]:
        self.db.execute(
            "INSERT INTO ai_recommendations "
            "(learner_id, topic, recommendation, difficulty, source) VALUES (?, ?, ?, ?, ?)",
            (recommendation.learner_id, recommendation.topic, recommendation.recommendation,
             recommendation.difficulty, recommendation.source),
        )
        return recommendation.model_dump()

    def get_recommendations(self, learner_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return self.db.execute(
            "SELECT id, topic, recommendation, difficulty, source, created_at "
            "FROM ai_recommendations WHERE learner_id = ? ORDER BY created_at DESC FETCH FIRST ? ROWS ONLY",
            (learner_id, limit),
        )
