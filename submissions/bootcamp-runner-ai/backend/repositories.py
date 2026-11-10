from __future__ import annotations

from typing import Any

from .db import Db2Client
from .models import (
    AchievementIn, CharacterUnlockIn, GameSessionIn, MissionIn, PlayerProfileIn, ScoreIn,
)


class Repository:
    def __init__(self, db: Db2Client) -> None:
        self.db = db

    def save_profile(self, profile: PlayerProfileIn) -> dict[str, Any]:
        self.db.execute(
            "MERGE INTO player_profiles AS target USING "
            "(VALUES (?, ?, ?, ?, ?, ?)) AS source(player_id, display_name, email, strengths, growth_areas, preferred_difficulty) "
            "ON target.player_id = source.player_id "
            "WHEN MATCHED THEN UPDATE SET display_name=source.display_name, email=source.email, strengths=source.strengths, "
            "growth_areas=source.growth_areas, preferred_difficulty=source.preferred_difficulty, updated_at=CURRENT TIMESTAMP "
            "WHEN NOT MATCHED THEN INSERT (player_id, display_name, email, strengths, growth_areas, preferred_difficulty) "
            "VALUES (source.player_id, source.display_name, source.email, source.strengths, source.growth_areas, source.preferred_difficulty)",
            (profile.player_id, profile.display_name, profile.email, profile.strengths,
             profile.growth_areas, profile.preferred_difficulty),
        )
        return profile.model_dump()

    def get_profile(self, player_id: str) -> dict[str, Any] | None:
        rows = self.db.execute(
            "SELECT player_id, display_name, email, strengths, growth_areas, preferred_difficulty, created_at, updated_at "
            "FROM player_profiles WHERE player_id = ?", (player_id,))
        return rows[0] if rows else None

    def create_session(self, session: GameSessionIn) -> dict[str, Any]:
        self.db.execute(
            "INSERT INTO game_sessions (player_id, mode, difficulty) VALUES (?, ?, ?)",
            (session.player_id, session.mode, session.difficulty))
        return session.model_dump()

    def save_score(self, score: ScoreIn) -> dict[str, Any]:
        self.db.execute(
            "INSERT INTO game_scores (session_id, player_id, score, points, rounds_completed) VALUES (?, ?, ?, ?, ?)",
            (score.session_id, score.player_id, score.score, score.points, score.rounds_completed))
        return score.model_dump()

    def list_scores(self, player_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return self.db.execute(
            "SELECT id, session_id, score, points, rounds_completed, created_at FROM game_scores "
            "WHERE player_id = ? ORDER BY created_at DESC FETCH FIRST ? ROWS ONLY", (player_id, limit))

    def unlock_character(self, item: CharacterUnlockIn) -> dict[str, Any]:
        self.db.execute(
            "MERGE INTO character_unlocks AS target USING (VALUES (?, ?)) AS source(player_id, character_key) "
            "ON target.player_id=source.player_id AND target.character_key=source.character_key "
            "WHEN NOT MATCHED THEN INSERT (player_id, character_key) VALUES (source.player_id, source.character_key)",
            (item.player_id, item.character_key))
        return item.model_dump()

    def list_characters(self, player_id: str) -> list[dict[str, Any]]:
        return self.db.execute("SELECT character_key, unlocked_at FROM character_unlocks WHERE player_id = ?", (player_id,))

    def save_achievement(self, item: AchievementIn) -> dict[str, Any]:
        self.db.execute(
            "MERGE INTO achievements AS target USING (VALUES (?, ?, ?, ?)) AS source(player_id, achievement_key, title, description) "
            "ON target.player_id=source.player_id AND target.achievement_key=source.achievement_key "
            "WHEN NOT MATCHED THEN INSERT (player_id, achievement_key, title, description) VALUES "
            "(source.player_id, source.achievement_key, source.title, source.description)",
            (item.player_id, item.achievement_key, item.title, item.description))
        return item.model_dump()

    def list_achievements(self, player_id: str) -> list[dict[str, Any]]:
        return self.db.execute("SELECT achievement_key, title, description, unlocked_at FROM achievements WHERE player_id = ?", (player_id,))

    def save_mission(self, item: MissionIn) -> dict[str, Any]:
        self.db.execute(
            "MERGE INTO player_missions AS target USING (VALUES (?, ?, ?, ?, ?)) AS source(player_id, mission_key, title, description, status) "
            "ON target.player_id=source.player_id AND target.mission_key=source.mission_key "
            "WHEN MATCHED THEN UPDATE SET status=source.status, title=source.title, description=source.description "
            "WHEN NOT MATCHED THEN INSERT (player_id, mission_key, title, description, status) VALUES "
            "(source.player_id, source.mission_key, source.title, source.description, source.status)",
            (item.player_id, item.mission_key, item.title, item.description, item.status))
        return item.model_dump()

    def list_missions(self, player_id: str) -> list[dict[str, Any]]:
        return self.db.execute("SELECT mission_key, title, description, status, updated_at FROM player_missions WHERE player_id = ?", (player_id,))

    def leaderboard(self, limit: int = 20) -> list[dict[str, Any]]:
        return self.db.execute(
            "SELECT player_id, SUM(points) AS points, AVG(score) AS average_score FROM game_scores "
            "GROUP BY player_id ORDER BY points DESC FETCH FIRST ? ROWS ONLY", (limit,))

    def save_assistant_output(self, player_id: str, objective: str, output: str, difficulty: str, source: str) -> dict[str, Any]:
        self.db.execute(
            "INSERT INTO assistant_challenges (player_id, objective, challenge, difficulty, source) VALUES (?, ?, ?, ?, ?)",
            (player_id, objective, output, difficulty, source))
        return {"player_id": player_id, "objective": objective, "challenge": output, "difficulty": difficulty, "source": source}
