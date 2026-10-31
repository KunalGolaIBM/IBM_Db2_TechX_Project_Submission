from __future__ import annotations

from uuid import uuid4

import chess
import pytest

from backend.app.errors import InvalidGameError
from backend.app.models import AnalysisInput, SaveGameRequest
from backend.app.service import ChessService

from .conftest import FakeCoach, FakeRepository, request_payload


def test_save_parses_moves_and_is_idempotent() -> None:
    repository = FakeRepository()
    service = ChessService(repository, FakeCoach())
    request = SaveGameRequest.model_validate(request_payload())

    first = service.save_game(request)
    retry = service.save_game(request)

    assert first.created is True
    assert retry.created is False
    assert first.game.result == "1-0"
    assert first.game.termination == "checkmate"
    assert first.game.player_outcome == "win"
    assert first.game.move_count == 7
    assert first.game.moves[-1].san == "Qxf7#"


def test_analysis_fen_must_match_requested_ply() -> None:
    payload = request_payload()
    payload["analysis"] = [{
        "ply_number": 1,
        "fen": chess.STARTING_FEN,
        "cp": 20,
        "mate": None,
        "win_probability": 51.0,
        "classification": "good",
        "status": "evaluated",
        "depth": 10,
        "engine": "stockfish-18",
    }]
    service = ChessService(FakeRepository(), FakeCoach())

    with pytest.raises(InvalidGameError, match="does not match ply 1"):
        service.save_game(SaveGameRequest.model_validate(payload))


def test_valid_frontend_analysis_is_stored_by_ply() -> None:
    payload = request_payload()
    board = chess.Board()
    board.push_san("e4")
    payload["analysis"] = [
        {
            "ply_number": 0,
            "fen": chess.STARTING_FEN,
            "cp": 0,
            "mate": None,
            "win_probability": 50.0,
            "classification": "book",
            "status": "evaluated",
            "depth": 10,
            "engine": "stockfish-18-lite",
        },
        {
            "ply_number": 1,
            "fen": board.fen(),
            "cp": None,
            "mate": None,
            "win_probability": None,
            "classification": None,
            "status": "timeout",
            "depth": None,
            "engine": "stockfish-18-lite",
        },
    ]
    service = ChessService(FakeRepository(), FakeCoach())

    saved = service.save_game(SaveGameRequest.model_validate(payload)).game

    assert [item.ply_number for item in saved.analysis] == [0, 1]
    assert saved.analysis[0].status == "evaluated"
    assert saved.analysis[1].status == "timeout"


def test_result_must_match_terminal_position() -> None:
    payload = request_payload(uuid4())
    payload["result"] = "0-1"
    service = ChessService(FakeRepository(), FakeCoach())

    with pytest.raises(InvalidGameError, match="Result does not match"):
        service.save_game(SaveGameRequest.model_validate(payload))


def test_frontend_time_forfeit_is_valid_for_nonterminal_board() -> None:
    payload = request_payload()
    payload.update({
        "pgn": '[Event "Timeout"]\n[Result "*"]\n\n1. e4 *',
        "result": "0-1",
        "termination": "time_forfeit",
    })
    service = ChessService(FakeRepository(), FakeCoach())

    saved = service.save_game(SaveGameRequest.model_validate(payload)).game

    assert saved.result == "0-1"
    assert saved.termination == "time_forfeit"
    assert saved.player_outcome == "loss"


def test_nonterminal_board_cannot_be_saved_as_checkmate() -> None:
    payload = request_payload()
    payload.update({
        "pgn": '[Event "False mate"]\n[Result "1-0"]\n\n1. e4 e5 1-0',
        "result": "1-0",
        "termination": "checkmate",
    })
    service = ChessService(FakeRepository(), FakeCoach())

    with pytest.raises(InvalidGameError, match="decisive external termination"):
        service.save_game(SaveGameRequest.model_validate(payload))


def test_import_preserves_decisive_pgn_header_when_frontend_reports_unfinished() -> None:
    payload = request_payload()
    payload.update({
        "pgn": '[Event "Imported resignation"]\n[Result "1-0"]\n\n1. e4 e5 1-0',
        "result": "*",
        "termination": "unfinished",
        "player_color": None,
        "source": "imported",
    })
    service = ChessService(FakeRepository(), FakeCoach())

    saved = service.save_game(SaveGameRequest.model_validate(payload)).game

    assert saved.result == "1-0"
    assert saved.termination == "unknown"
    assert saved.player_outcome is None


def test_played_game_cannot_override_request_result_from_pgn_header() -> None:
    payload = request_payload()
    payload.update({
        "pgn": '[Event "Unverified result"]\n[Result "1-0"]\n\n1. e4 e5 1-0',
        "result": "*",
        "termination": "unfinished",
    })
    service = ChessService(FakeRepository(), FakeCoach())

    with pytest.raises(InvalidGameError, match="PGN header"):
        service.save_game(SaveGameRequest.model_validate(payload))

