from __future__ import annotations

import chess
import pytest

from g6explanation.context_engine import MoveContextEngine
from g6explanation.context_engine.exceptions import AnalysisError
from g6explanation.context_engine.heuristics import classify_quality
from g6explanation.context_engine.models import (
    EngineAnalysis,
    EngineLine,
    HumanMoveStats,
    MoveContextRequest,
    MoveFacts,
    PlayerLevel,
    Score,
)
from tests.g6explanation.context_engine.helpers import (
    StaticAnalyzer,
    StaticHumanProvider,
    analysis,
)


def test_uses_practical_alternative_when_engine_best_is_hard_and_close() -> None:
    board = chess.Board()
    engine_analysis = analysis(
        board,
        played_uci="g2g4",
        top_scores=[("e2e4", 40), ("g1f3", 25)],
        played_score=-180,
        after_reply_uci="e7e5",
    )
    human = StaticHumanProvider(
        {
            "e2e4": HumanMoveStats(player_level_probability=0.02, plus_400_probability=0.12),
            "g1f3": HumanMoveStats(player_level_probability=0.32, plus_400_probability=0.40),
            "g2g4": HumanMoveStats(player_level_probability=0.25, plus_400_probability=0.08),
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

    result = MoveContextEngine(StaticAnalyzer(engine_analysis), human).build(request)

    assert result.evidence.quality.label == "mistake"
    assert result.llm_context.best_or_key_move is not None
    assert result.llm_context.best_or_key_move["move"] == "Nf3"
    assert result.llm_context.best_or_key_move["practicality"] == "practical_try"
    assert (
        result.llm_context.best_or_key_move["recommendation_policy"]
        == "use_as_practical_alternative"
    )


def test_caveats_hard_engine_best_instead_of_presenting_it_as_obvious() -> None:
    board = chess.Board()
    engine_analysis = analysis(
        board,
        played_uci="a2a3",
        top_scores=[("e2e4", 300), ("d2d4", 210)],
        played_score=-60,
        after_reply_uci="e7e5",
    )
    human = StaticHumanProvider(
        {
            "e2e4": HumanMoveStats(player_level_probability=0.015, plus_400_probability=0.10),
            "a2a3": HumanMoveStats(player_level_probability=0.20, plus_400_probability=0.02),
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

    result = MoveContextEngine(StaticAnalyzer(engine_analysis), human).build(request)

    assert result.evidence.quality.label == "blunder"
    assert result.llm_context.best_or_key_move is not None
    assert result.llm_context.best_or_key_move["move"] == "e4"
    assert result.llm_context.best_or_key_move["recommendation_policy"] == "mention_with_caveat"
    assert result.llm_context.best_or_key_move["findability"] in {"very_hard", "engine_like"}
    assert result.llm_context.human_note is not None


def test_human_probability_does_not_change_objective_quality() -> None:
    board = chess.Board()
    engine_analysis = analysis(
        board,
        played_uci="g2g4",
        top_scores=[("e2e4", 80)],
        played_score=-140,
        after_reply_uci="e7e5",
    )
    human = StaticHumanProvider(
        {
            "g2g4": HumanMoveStats(player_level_probability=0.45),
            "e2e4": HumanMoveStats(player_level_probability=0.08),
        }
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="g2g4",
        player_color="white",
        player_level=PlayerLevel.rating(1000),
    )

    result = MoveContextEngine(StaticAnalyzer(engine_analysis), human).build(request)
    played_candidate = next(
        candidate for candidate in result.evidence.candidates if "played_move" in candidate.roles
    )

    assert played_candidate.time_adjusted_findability == "obvious"
    assert result.evidence.quality.label == "mistake"


def test_normalizes_black_player_scores_from_black_perspective() -> None:
    board = chess.Board("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1")
    engine_analysis = analysis(
        board,
        played_uci="g7g5",
        top_scores=[("c7c5", 60)],
        played_score=-200,
        after_reply_uci="d2d4",
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="g7g5",
        player_color="black",
        player_level=PlayerLevel.rating(1300),
    )

    result = MoveContextEngine(StaticAnalyzer(engine_analysis)).build(request)

    assert result.evidence.position.side_to_move == "black"
    assert result.evidence.quality.label == "mistake"
    assert result.evidence.quality.score_delta_cp_player_pov == -260


def test_mate_scores_are_classified_without_centipawn_delta() -> None:
    analysis_with_mate = EngineAnalysis(
        engine_version="static-test-engine",
        analysis_budget={"kind": "static", "value": 1},
        top_lines=[
            EngineLine(
                move_uci="e2e4",
                move_san="e4",
                score=Score.mate(mate_in=3, mate_for="player"),
                rank=1,
            )
        ],
        played_line=EngineLine(
            move_uci="a2a3",
            move_san="a3",
            score=Score.cp(20),
            rank=None,
        ),
    )
    quality = classify_quality(
        analysis_with_mate,
        MoveFacts(uci="a2a3", san="a3", legal=True, is_check=False, is_capture=False),
    )

    assert quality.label == "missed_win"
    assert quality.score_delta_cp_player_pov is None
    assert "forced mate" in quality.severity_text


def test_rejects_analyzer_that_returns_different_played_move() -> None:
    board = chess.Board()
    engine_analysis = analysis(
        board,
        played_uci="a2a3",
        top_scores=[("e2e4", 50)],
        played_score=-20,
        after_reply_uci="e7e5",
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="g2g4",
        player_color="white",
        player_level=PlayerLevel.rating(1200),
    )

    engine = MoveContextEngine(StaticAnalyzer(engine_analysis))

    with pytest.raises(AnalysisError, match="does not match requested move"):
        engine.build(request)
