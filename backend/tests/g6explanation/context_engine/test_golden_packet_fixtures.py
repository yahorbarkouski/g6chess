from __future__ import annotations

import chess
import pytest

from g6explanation.context_engine import MoveContextBuilder
from g6explanation.context_engine.contracts import ColorName, MoveContextRequest, PlayerLevel
from tests.g6explanation.context_engine.helpers import StaticAnalysisProvider, analysis


@pytest.mark.parametrize(
    ("fen", "played_uci", "player_color"),
    [
        (chess.Board().fen(), "e2e4", "white"),
        (
            "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            "e7e5",
            "black",
        ),
        ("4k3/P7/8/8/8/8/8/4K3 w - - 0 1", "a7a8q", "white"),
        (
            "rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3",
            "e5d6",
            "white",
        ),
        ("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", "e1g1", "white"),
        ("8/8/8/8/8/4K3/8/7k w - - 0 1", "e3e4", "white"),
        (
            "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 2 3",
            "c4f7",
            "white",
        ),
    ],
)
def test_golden_packet_fixtures_cover_chess_state_edges(
    fen: str,
    played_uci: str,
    player_color: ColorName,
) -> None:
    board = chess.Board(fen)
    engine_analysis = analysis(
        board,
        played_uci=played_uci,
        top_scores=[(played_uci, 50)],
        played_score=50,
    )
    request = MoveContextRequest(
        fen_before=fen,
        played_move=played_uci,
        player_color=player_color,
        player_level=PlayerLevel.rating(1200),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis)).build(request)
    board_after = board.copy(stack=False)
    board_after.push(chess.Move.from_uci(played_uci))

    assert result.evidence.context_version == "move_context.v1"
    assert result.evidence.played.uci == played_uci
    assert result.evidence.played.legal is True
    assert result.evidence.position.fen_after == board_after.fen()
    assert result.evidence.to_dict()["quality"]["label"] == "best"
