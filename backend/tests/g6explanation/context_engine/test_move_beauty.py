from __future__ import annotations

import chess

from g6explanation.context_engine import MoveContextBuilder
from g6explanation.context_engine.contracts import (
    EngineAnalysis,
    EngineAnalysisBudget,
    EngineLine,
    HumanMoveLikelihood,
    MoveContextRequest,
    PlayerLevel,
    Score,
    Wdl,
)
from tests.g6explanation.context_engine.helpers import (
    StaticAnalysisProvider,
    StaticHumanLikelihoodProvider,
    analysis,
    pv_san,
)


def test_routine_best_opening_move_has_low_beauty() -> None:
    board = chess.Board()
    engine_analysis = analysis(
        board,
        played_uci="e2e4",
        top_scores=[("e2e4", 40), ("d2d4", 25)],
        played_score=40,
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="e2e4",
        player_color="white",
        player_level=PlayerLevel.rating(1200),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis)).build(request)

    assert result.evidence.beauty.label == "low"
    assert result.evidence.beauty.score == 0.08
    assert result.llm_context.beauty.label == "low"


def test_bad_move_has_zero_beauty_even_when_it_is_unusual() -> None:
    board = chess.Board()
    engine_analysis = analysis(
        board,
        played_uci="g2g4",
        top_scores=[("e2e4", 300)],
        played_score=-120,
    )
    human = StaticHumanLikelihoodProvider(
        {"g2g4": HumanMoveLikelihood(player_level_probability=0.01)}
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="g2g4",
        player_color="white",
        player_level=PlayerLevel.rating(1200),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis), human).build(request)

    assert result.evidence.quality.label == "blunder"
    assert result.evidence.beauty.label == "low"
    assert result.evidence.beauty.score == 0.0


def test_quiet_queen_sacrifice_resource_can_be_brilliant() -> None:
    board = chess.Board("r3r1k1/pp3pbp/1qp3p1/2B5/2BP2b1/Q1n2N2/P4PPP/3R1K1R b - - 3 17")
    played_pv = ["g4e6", "c5b6", "e6c4", "f1g1", "c3e2"]
    engine_analysis = EngineAnalysis(
        engine_version="static-test-engine",
        analysis_budget=EngineAnalysisBudget(kind="static", value=1, multipv=2),
        top_lines=[
            _line(board, "g4e6", Score.cp(225), rank=1, pv_uci=played_pv),
            _line(board, "c3b5", Score.cp(-101), rank=2),
        ],
        played_line=_line(board, "g4e6", Score.cp(229), rank=None, pv_uci=played_pv),
    )
    human = StaticHumanLikelihoodProvider(
        {"g4e6": HumanMoveLikelihood(player_level_probability=0.02)}
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="g4e6",
        player_color="black",
        player_level=PlayerLevel.rating(2400),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis), human).build(request)

    assert result.evidence.quality.label == "best"
    assert result.evidence.significance.label == "critical"
    assert result.evidence.beauty.label == "brilliant"
    assert result.evidence.beauty.score == 0.88


def test_sacrificial_forcing_move_can_be_beautiful_without_being_critical() -> None:
    board = chess.Board("b2r3r/k4p1p/p2q1np1/NppP4/3p1Q2/P4PPB/1PP4P/1K1RR3 w - - 1 24")
    played_pv = ["d1d4", "c5d4", "e1e7", "a7b6", "f4d4", "b6a5"]
    engine_analysis = EngineAnalysis(
        engine_version="static-test-engine",
        analysis_budget=EngineAnalysisBudget(kind="static", value=1, multipv=2),
        top_lines=[
            _line(board, "d1d4", Score.cp(-30), rank=1, pv_uci=played_pv),
            _line(board, "a5c6", Score.cp(-200), rank=2),
        ],
        played_line=_line(board, "d1d4", Score.cp(-30), rank=None, pv_uci=played_pv),
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="d1d4",
        player_color="white",
        player_level=PlayerLevel.rating(2800),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis)).build(request)

    assert result.evidence.significance.label == "high"
    assert result.evidence.beauty.label == "beautiful"
    assert result.evidence.beauty.score == 0.58


def _line(
    board: chess.Board,
    uci: str,
    score: Score,
    rank: int | None,
    pv_uci: list[str] | None = None,
) -> EngineLine:
    move = chess.Move.from_uci(uci)
    assert move in board.legal_moves
    full_pv_uci = pv_uci or [uci]
    return EngineLine(
        move_uci=uci,
        move_san=board.san(move),
        score=score,
        rank=rank,
        wdl=Wdl(win=500, draw=400, loss=100),
        pv_uci=full_pv_uci,
        pv_san=pv_san(board, full_pv_uci),
    )
