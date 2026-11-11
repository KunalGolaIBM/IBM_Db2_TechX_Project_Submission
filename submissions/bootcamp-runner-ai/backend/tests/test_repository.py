import pytest

from backend.models import GameSessionIn, PlayerProfileIn, ScoreIn
from backend.repositories import Repository, SessionOwnershipError


class FakeDb:
    def __init__(self):
        self.calls = []
    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return []


class SessionDb(FakeDb):
    def execute_insert_and_get_identity(self, sql, params=()):
        self.calls.append((sql, params))
        return 42

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "FROM game_sessions" in sql:
            return [{"OWNS_SESSION": 1}]
        return []


def test_repository_uses_placeholders():
    db = FakeDb()
    Repository(db).list_scores("x' OR 1=1 --", 5)
    assert "x' OR 1=1" not in db.calls[0][0]
    assert db.calls[0][1] == ("x' OR 1=1 --", 5)


def test_create_session_returns_generated_identity_id():
    db = SessionDb()
    result = Repository(db).create_session(GameSessionIn(player_id="player-1"))
    assert result["session_id"] == 42
    assert "INSERT INTO game_sessions" in db.calls[0][0]


def test_save_profile_uses_typed_merge_markers_and_returns_profile():
    db = FakeDb()
    profile = PlayerProfileIn(
        player_id="player-1",
        display_name="Runner",
        email="runner@example.test",
    )

    result = Repository(db).save_profile(profile)

    assert result == profile.model_dump()
    sql, params = db.calls[0]
    assert "CAST(? AS VARCHAR(128))" in sql
    assert "CAST(? AS VARCHAR(320))" in sql
    assert params == (
        "player-1", "Runner", "runner@example.test", "", "", "medium"
    )


def test_save_profile_supports_creation_and_update_calls():
    db = FakeDb()
    repository = Repository(db)
    created = PlayerProfileIn(
        player_id="player-1",
        display_name="Runner",
        email="runner@example.test",
    )
    updated = created.model_copy(update={"display_name": "Fast Runner"})

    assert repository.save_profile(created) == created.model_dump()
    assert repository.save_profile(updated) == updated.model_dump()

    assert len(db.calls) == 2
    assert db.calls[0][1][0] == db.calls[1][1][0] == "player-1"
    assert db.calls[1][1][1] == "Fast Runner"


def test_save_score_rejects_session_owned_by_another_player():
    db = FakeDb()
    score = ScoreIn(session_id=42, player_id="player-2", score=101)
    with pytest.raises(SessionOwnershipError):
        Repository(db).save_score(score)
    assert len(db.calls) == 1
    assert "FROM game_sessions" in db.calls[0][0]


def test_save_score_accepts_arcade_score_above_100():
    db = SessionDb()
    score = ScoreIn(session_id=42, player_id="player-1", score=101)
    result = Repository(db).save_score(score)
    assert result["score"] == 101
    assert db.calls[-1][1] == (42, "player-1", 101)
