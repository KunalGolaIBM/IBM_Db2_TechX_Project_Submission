from __future__ import annotations

import io
from datetime import timezone

import chess
import chess.pgn

from .domain import AnalysisData, GameData, MoveData
from .errors import InvalidGameError
from .models import SaveGameRequest


OPENINGS: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6"), "B90", "Sicilian Defense: Najdorf Variation"),
    (("e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Bxc6"), "C68", "Ruy Lopez: Exchange Variation"),
    (("e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "c3"), "C53", "Italian Game: Giuoco Pianissimo"),
    (("d4", "Nf6", "c4", "g6", "Nc3", "Bg7", "e4", "d6"), "E90", "King's Indian Defense"),
    (("e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6"), "C55", "Two Knights Defense"),
    (("d4", "d5", "Nf3", "Nf6", "Bf4"), "D02", "Queen's Pawn Game: London System"),
    (("d4", "Nf6", "c4", "e6", "g3"), "E00", "Queen's Pawn Game: Catalan Opening"),
    (("e4", "e5", "Nf3", "Nc6", "Bc4"), "C50", "Italian Game"),
    (("e4", "e5", "Nf3", "Nc6", "Bb5"), "C60", "Ruy Lopez"),
    (("d4", "d5", "c4", "dxc4"), "D20", "Queen's Gambit Accepted"),
    (("d4", "d5", "c4", "e6"), "D30", "Queen's Gambit Declined"),
    (("d4", "Nf6", "c4", "g6"), "E60", "King's Indian Defense"),
    (("e4", "c5", "Nf3", "Nc6"), "B30", "Sicilian Defense: Old Sicilian"),
    (("e4", "e5", "Nf3"), "C44", "King's Pawn Game: King's Knight Opening"),
    (("d4", "d5", "c4"), "D06", "Queen's Gambit"),
    (("e4", "e5"), "C20", "King's Pawn Game"),
    (("e4", "d5"), "B01", "Scandinavian Defense"),
    (("e4", "c6"), "B10", "Caro-Kann Defense"),
    (("e4", "c5"), "B20", "Sicilian Defense"),
    (("e4", "e6"), "C00", "French Defense"),
    (("e4",), "B00", "King's Pawn Game"),
    (("d4",), "D00", "Queen's Pawn Game"),
)

VALID_TERMINATIONS = {
    "checkmate", "stalemate", "insufficient_material", "threefold_repetition",
    "fivefold_repetition", "fifty_move_rule", "seventy_five_moves", "timeout",
    "time_forfeit", "repetition", "resignation", "abandonment", "agreement",
    "draw", "unknown", "unterminated", "unfinished",
}

TERMINATION_MAP = {
    chess.Termination.CHECKMATE: "checkmate",
    chess.Termination.STALEMATE: "stalemate",
    chess.Termination.INSUFFICIENT_MATERIAL: "insufficient_material",
    chess.Termination.THREEFOLD_REPETITION: "repetition",
    chess.Termination.FIVEFOLD_REPETITION: "repetition",
    chess.Termination.FIFTY_MOVES: "fifty_move_rule",
    chess.Termination.SEVENTYFIVE_MOVES: "fifty_move_rule",
}


def _normalize_termination(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized not in VALID_TERMINATIONS:
        raise InvalidGameError(f"Unsupported termination: {value}")
    return normalized


def _player_outcome(result: str, player_color: str) -> str:
    if player_color == "unknown" or result == "*":
        return "unknown"
    if result == "1/2-1/2":
        return "draw"
    player_won = (player_color == "white" and result == "1-0") or (player_color == "black" and result == "0-1")
    return "win" if player_won else "loss"


def _derive_opening(game: chess.pgn.Game, sans: tuple[str, ...], request: SaveGameRequest) -> tuple[str | None, str]:
    for sequence, code, name in OPENINGS:
        if sans[: len(sequence)] == sequence:
            return code, name
    header_code = game.headers.get("ECO", "").strip().upper()
    header_name = game.headers.get("Opening", "").strip()
    if header_name:
        if len(header_code) > 16 or len(header_name) > 255:
            raise InvalidGameError("PGN opening metadata is too long")
        return header_code or request.opening_eco, header_name
    return request.opening_eco, request.opening_name


def _canonical_result(game: chess.pgn.Game, board: chess.Board, requested: str, source: str) -> tuple[str, str]:
    outcome = board.outcome(claim_draw=False)
    if outcome is not None:
        derived_result = outcome.result()
        if requested != derived_result:
            raise InvalidGameError("Result does not match the PGN final position")
        return derived_result, TERMINATION_MAP.get(outcome.termination, "unknown")
    header_result = game.headers.get("Result", "*")
    if header_result not in {"1-0", "0-1", "1/2-1/2", "*"}:
        raise InvalidGameError("PGN contains an invalid result header")
    if source == "imported" and requested == "*" and header_result in {"1-0", "0-1"}:
        return header_result, "unknown"
    if header_result != "*" and header_result != requested:
        raise InvalidGameError("Result does not match the PGN header")
    return requested, ""


def _validate_nonautomatic_result(board: chess.Board, result: str, termination: str, source: str) -> None:
    if result == "*":
        if termination not in {"unfinished", "unterminated", "unknown"}:
            raise InvalidGameError("An unfinished game cannot have a terminal reason")
        return
    if result in {"1-0", "0-1"}:
        if source == "imported" and termination == "unknown":
            return
        if termination not in {"time_forfeit", "timeout", "resignation", "abandonment"}:
            raise InvalidGameError("A nonterminal position needs a decisive external termination")
        return
    if termination == "repetition":
        if not board.can_claim_threefold_repetition():
            raise InvalidGameError("The final position cannot claim repetition")
        return
    if termination == "fifty_move_rule":
        if not board.can_claim_fifty_moves():
            raise InvalidGameError("The final position cannot claim the fifty-move rule")
        return
    if termination not in {"agreement", "draw", "unknown"}:
        raise InvalidGameError("A nonterminal draw needs an agreement or claimable draw reason")


def parse_game(request: SaveGameRequest) -> GameData:
    stream = io.StringIO(request.pgn)
    try:
        game = chess.pgn.read_game(stream)
    except (ValueError, UnicodeError) as exc:
        raise InvalidGameError("PGN could not be parsed") from exc
    if game is None:
        raise InvalidGameError("PGN does not contain a game")
    if game.errors:
        raise InvalidGameError("PGN contains illegal or malformed moves")
    try:
        if chess.pgn.read_game(stream) is not None:
            raise InvalidGameError("Only one PGN game may be saved per request")
    except InvalidGameError:
        raise
    except Exception as exc:
        raise InvalidGameError("PGN contains trailing malformed content") from exc

    board = game.board()
    moves: list[MoveData] = []
    sans: list[str] = []
    positions = [board.fen()]
    for ply_number, node in enumerate(game.mainline(), start=1):
        move = node.move
        san = board.san(move)
        sans.append(san)
        board.push(move)
        fen_after = board.fen()
        positions.append(fen_after)
        moves.append(MoveData(ply_number=ply_number, san=san, uci=move.uci(), fen_after=fen_after))

    result, derived_termination = _canonical_result(game, board, request.result, request.source)
    termination = derived_termination or _normalize_termination(request.termination)
    if not derived_termination:
        _validate_nonautomatic_result(board, result, termination, request.source)
    player_color = request.player_color or "unknown"
    opening_code, opening_name = _derive_opening(game, tuple(sans), request)

    analysis: list[AnalysisData] = []
    seen_plies: set[int] = set()
    for item in request.analysis:
        if item.ply_number in seen_plies:
            raise InvalidGameError(f"Duplicate analysis for ply {item.ply_number}")
        if item.ply_number >= len(positions):
            raise InvalidGameError(f"Analysis ply {item.ply_number} is outside this game")
        try:
            normalized_fen = chess.Board(item.fen).fen()
        except ValueError as exc:
            raise InvalidGameError(f"Analysis ply {item.ply_number} has invalid FEN") from exc
        if normalized_fen != positions[item.ply_number]:
            raise InvalidGameError(f"Analysis FEN does not match ply {item.ply_number}")
        if item.status == "evaluated" and item.cp is None and item.mate is None:
            raise InvalidGameError(f"Successful analysis at ply {item.ply_number} needs cp or mate")
        if item.status != "evaluated" and (item.cp is not None or item.mate is not None):
            raise InvalidGameError(f"Failed analysis at ply {item.ply_number} cannot carry an evaluation")
        seen_plies.add(item.ply_number)
        analysis.append(AnalysisData(
            ply_number=item.ply_number, fen=normalized_fen, cp=item.cp, mate=item.mate,
            win_probability=round(item.win_probability, 2) if item.win_probability is not None else None,
            classification=item.classification,
            engine=item.engine, depth=item.depth, status=item.status,
        ))

    game.headers["Result"] = result
    game.headers["Termination"] = termination
    if opening_code:
        game.headers["ECO"] = opening_code
    game.headers["Opening"] = opening_name
    canonical_pgn = game.accept(chess.pgn.StringExporter(headers=True, variations=False, comments=False)).strip()
    played_at = request.played_at
    if played_at.tzinfo is None:
        raise InvalidGameError("played_at must include a timezone")
    played_at = played_at.astimezone(timezone.utc)

    return GameData(
        game_id=str(request.client_game_id), pgn=canonical_pgn, result=result,
        termination=termination, player_color=player_color,
        player_outcome=_player_outcome(result, player_color), source=request.source,
        opponent_elo=request.opponent_elo, time_control=request.time_control,
        played_at=played_at, opening_code=opening_code, opening_name=opening_name,
        moves=tuple(moves), analysis=tuple(sorted(analysis, key=lambda value: value.ply_number)),
    )
