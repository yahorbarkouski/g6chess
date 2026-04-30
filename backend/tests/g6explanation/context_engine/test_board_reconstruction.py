from __future__ import annotations

import pytest

from g6explanation.context_engine.board import reconstruct_board_context
from g6explanation.context_engine.exceptions import AmbiguousRequestError, InvalidRequestError
from g6explanation.context_engine.models import MoveContextRequest, PlayerLevel


def test_reconstructs_fen_and_played_move() -> None:
    request = MoveContextRequest(
        fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        played_move="e2e4",
        player_color="white",
        player_level=PlayerLevel.rating(1200),
    )

    _, _, context = reconstruct_board_context(request)

    assert context.played.uci == "e2e4"
    assert context.played.san == "e4"
    assert context.position.side_to_move == "white"
    assert context.position.fen_after.startswith("rnbqkbnr/pppppppp/8/8/4P3")


def test_rejects_player_color_that_does_not_match_side_to_move() -> None:
    request = MoveContextRequest(
        fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        played_move="e2e4",
        player_color="black",
        player_level=PlayerLevel.rating(1200),
    )

    with pytest.raises(InvalidRequestError):
        reconstruct_board_context(request)


def test_requires_ply_for_pgn_input() -> None:
    request = MoveContextRequest(
        pgn="1. e4 e5 2. Nf3",
        played_move="e2e4",
        player_color="white",
        player_level=PlayerLevel.rating(1200),
    )

    with pytest.raises(AmbiguousRequestError):
        reconstruct_board_context(request)


def test_reconstructs_pgn_move_by_ply() -> None:
    request = MoveContextRequest(
        pgn="1. e4 e5 2. Nf3",
        ply=2,
        played_move="e7e5",
        player_color="black",
        player_level=PlayerLevel.rating(1200),
    )

    board, move, context = reconstruct_board_context(request)

    assert board.fen().startswith("rnbqkbnr/pppppppp/8/8/4P3")
    assert move.uci() == "e7e5"
    assert context.played.san == "e5"
    assert context.position.side_to_move == "black"
