from __future__ import annotations

import chess

from g6explanation.context_engine import MoveContextBuilder
from g6explanation.context_engine.contracts import (
    ContextResult,
    HumanMoveLikelihood,
    MoveContextRequest,
    PlayerLevel,
)
from tests.g6explanation.context_engine.helpers import (
    StaticAnalysisProvider,
    StaticHumanLikelihoodProvider,
    analysis,
)


def mistake_context_with_practical_alternative() -> ContextResult:
    board = chess.Board()
    engine_analysis = analysis(
        board,
        played_uci="g2g4",
        top_scores=[("e2e4", 40), ("g1f3", 25)],
        played_score=-180,
        after_reply_uci="e7e5",
    )
    human = StaticHumanLikelihoodProvider(
        {
            "e2e4": HumanMoveLikelihood(
                player_level_probability=0.02,
                plus_400_probability=0.12,
            ),
            "g1f3": HumanMoveLikelihood(
                player_level_probability=0.32,
                plus_400_probability=0.40,
            ),
            "g2g4": HumanMoveLikelihood(
                player_level_probability=0.25,
                plus_400_probability=0.08,
            ),
        }
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="g2g4",
        player_color="white",
        player_level=PlayerLevel.rating(1250, "lichess"),
        time_control="blitz",
        clock_before_seconds=80,
    )
    return MoveContextBuilder(StaticAnalysisProvider(engine_analysis), human).build(request)


def hard_engine_best_context() -> ContextResult:
    board = chess.Board()
    engine_analysis = analysis(
        board,
        played_uci="a2a3",
        top_scores=[("e2e4", 300), ("d2d4", 210)],
        played_score=-60,
        after_reply_uci="e7e5",
    )
    human = StaticHumanLikelihoodProvider(
        {
            "e2e4": HumanMoveLikelihood(
                player_level_probability=0.015,
                plus_400_probability=0.10,
            ),
            "a2a3": HumanMoveLikelihood(
                player_level_probability=0.20,
                plus_400_probability=0.02,
            ),
        }
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="a2a3",
        player_color="white",
        player_level=PlayerLevel.rating(900, "lichess"),
        time_control="blitz",
        clock_before_seconds=20,
    )
    return MoveContextBuilder(StaticAnalysisProvider(engine_analysis), human).build(request)


def best_context() -> ContextResult:
    board = chess.Board()
    engine_analysis = analysis(
        board,
        played_uci="e2e4",
        top_scores=[("e2e4", 40), ("d2d4", 25)],
        played_score=40,
        after_reply_uci="e7e5",
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="e2e4",
        player_color="white",
        player_level=PlayerLevel.rating(1200),
    )
    return MoveContextBuilder(StaticAnalysisProvider(engine_analysis)).build(request)
