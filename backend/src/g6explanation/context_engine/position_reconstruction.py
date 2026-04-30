"""Position reconstruction for a single move."""

from __future__ import annotations

import io

import chess
import chess.pgn

from g6explanation.context_engine.contracts import (
    ColorName,
    MoveContextRequest,
    PlayedMoveFacts,
    PositionContext,
    ReconstructedMoveContext,
)
from g6explanation.context_engine.exceptions import AmbiguousRequestError, InvalidRequestError


def color_name(color: chess.Color) -> ColorName:
    return "white" if color == chess.WHITE else "black"


def chess_color(name: ColorName) -> chess.Color:
    return chess.WHITE if name == "white" else chess.BLACK


def reconstruct_move_context(
    request: MoveContextRequest,
) -> tuple[chess.Board, chess.Move, ReconstructedMoveContext]:
    """Return board before the move, parsed move, and serializable move context."""

    if request.fen_before and request.pgn:
        raise InvalidRequestError("Provide either fen_before or pgn, not both.")
    if request.fen_before:
        board = _board_from_fen(request.fen_before)
        move = _parse_requested_move(board, request.played_move)
    elif request.pgn:
        board, move = _board_and_move_from_pgn(request)
    else:
        raise InvalidRequestError("Either fen_before or pgn is required.")

    if color_name(board.turn) != request.player_color:
        side_to_move = color_name(board.turn)
        raise InvalidRequestError(
            f"player_color={request.player_color} does not match side to move={side_to_move}."
        )
    if move not in board.legal_moves:
        raise InvalidRequestError(f"played_move={move.uci()} is not legal in the position.")

    san = board.san(move)
    is_check = board.gives_check(move)
    is_capture = board.is_capture(move)
    board_after = board.copy(stack=False)
    board_after.push(move)

    played = PlayedMoveFacts(
        uci=move.uci(),
        san=san,
        legal=True,
        is_check=is_check,
        is_capture=is_capture,
        promotion=chess.piece_symbol(move.promotion).upper() if move.promotion else None,
    )
    position = PositionContext(
        fen_before=board.fen(),
        fen_after=board_after.fen(),
        side_to_move=color_name(board.turn),
        move_number=board.fullmove_number,
        ply=board.ply(),
        phase=_phase(board),
        legal_moves_uci=[legal.uci() for legal in board.legal_moves],
        previous_move_uci=board.peek().uci() if board.move_stack else None,
    )
    return board, move, ReconstructedMoveContext(position=position, played=played)


def _board_from_fen(fen: str) -> chess.Board:
    try:
        return chess.Board(fen)
    except ValueError as exc:
        raise InvalidRequestError(f"Invalid FEN: {exc}") from exc


def _parse_requested_move(board: chess.Board, played_move: str | None) -> chess.Move:
    if not played_move:
        raise AmbiguousRequestError("played_move is required with fen_before.")

    try:
        move = chess.Move.from_uci(played_move)
    except ValueError:
        try:
            return board.parse_san(played_move)
        except ValueError as exc:
            raise InvalidRequestError(f"Could not parse played_move={played_move!r}.") from exc

    if move not in board.legal_moves:
        raise InvalidRequestError(f"played_move={played_move!r} is not legal in the position.")
    return move


def _board_and_move_from_pgn(request: MoveContextRequest) -> tuple[chess.Board, chess.Move]:
    game = chess.pgn.read_game(io.StringIO(request.pgn or ""))
    if game is None:
        raise InvalidRequestError("PGN could not be parsed.")

    moves = list(game.mainline_moves())
    if request.ply is None:
        raise AmbiguousRequestError("ply is required when using PGN input.")
    if request.ply < 1 or request.ply > len(moves):
        raise InvalidRequestError(f"ply={request.ply} is outside the PGN mainline.")

    board = game.board()
    for move in moves[: request.ply - 1]:
        board.push(move)

    move = moves[request.ply - 1]
    if request.played_move:
        parsed = _parse_requested_move(board, request.played_move)
        if parsed != move:
            expected_move = move.uci()
            raise InvalidRequestError(
                f"played_move={parsed.uci()} does not match "
                f"PGN move at ply {request.ply}: {expected_move}."
            )
    return board, move


def _phase(board: chess.Board) -> str:
    non_king_pieces = len(board.piece_map()) - 2
    if non_king_pieces <= 10:
        return "endgame"
    if board.fullmove_number <= 10:
        return "opening"
    return "middlegame"
