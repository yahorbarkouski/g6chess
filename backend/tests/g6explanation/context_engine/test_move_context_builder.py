from __future__ import annotations

import chess
import pytest

from g6explanation.context_engine import MoveContextBuilder
from g6explanation.context_engine.contracts import (
    EngineAnalysis,
    EngineAnalysisBudget,
    EngineLine,
    HumanMoveLikelihood,
    MoveContextRequest,
    PlayedMoveFacts,
    PlayerLevel,
    Score,
    Wdl,
)
from g6explanation.context_engine.exceptions import AnalysisError
from g6explanation.context_engine.move_quality import calculate_significance, classify_quality
from tests.g6explanation.context_engine.helpers import (
    StaticAnalysisProvider,
    StaticHumanLikelihoodProvider,
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
    human = StaticHumanLikelihoodProvider(
        {
            "e2e4": HumanMoveLikelihood(player_level_probability=0.02, plus_400_probability=0.12),
            "g1f3": HumanMoveLikelihood(player_level_probability=0.32, plus_400_probability=0.40),
            "g2g4": HumanMoveLikelihood(player_level_probability=0.25, plus_400_probability=0.08),
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

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis), human).build(request)

    assert result.evidence.quality.label == "mistake"
    assert result.evidence.significance.label == "critical"
    assert result.evidence.significance.score == 0.73
    assert result.llm_context.significance.label == "critical"
    assert result.llm_context.best_or_key_move is not None
    assert result.llm_context.best_or_key_move.move == "Nf3"
    assert result.llm_context.best_or_key_move.practicality == "practical_try"
    assert (
        result.llm_context.best_or_key_move.recommendation_policy == "use_as_practical_alternative"
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
    human = StaticHumanLikelihoodProvider(
        {
            "e2e4": HumanMoveLikelihood(player_level_probability=0.015, plus_400_probability=0.10),
            "a2a3": HumanMoveLikelihood(player_level_probability=0.20, plus_400_probability=0.02),
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

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis), human).build(request)

    assert result.evidence.quality.label == "blunder"
    assert result.llm_context.best_or_key_move is not None
    assert result.llm_context.best_or_key_move.move == "e4"
    assert result.llm_context.best_or_key_move.recommendation_policy == "explain_as_hidden_resource"
    assert result.llm_context.best_or_key_move.findability in {"very_hard", "engine_like"}
    assert result.llm_context.human_note is not None


def test_low_significance_when_best_move_is_only_slightly_better() -> None:
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

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis)).build(request)

    assert result.evidence.quality.label == "best"
    assert result.evidence.significance.label == "low"
    assert result.evidence.significance.score == 0.05


def test_critical_significance_when_best_move_is_much_better_than_second_best() -> None:
    board = chess.Board()
    engine_analysis = analysis(
        board,
        played_uci="e2e4",
        top_scores=[("e2e4", 300), ("d2d4", -60)],
        played_score=300,
        after_reply_uci="e7e5",
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="e2e4",
        player_color="white",
        player_level=PlayerLevel.rating(1200),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis)).build(request)

    assert result.evidence.quality.label == "best"
    assert result.evidence.significance.label == "critical"
    assert result.evidence.significance.score == 1.0


def test_human_probability_does_not_change_objective_quality() -> None:
    board = chess.Board()
    engine_analysis = analysis(
        board,
        played_uci="g2g4",
        top_scores=[("e2e4", 80)],
        played_score=-140,
        after_reply_uci="e7e5",
    )
    human = StaticHumanLikelihoodProvider(
        {
            "g2g4": HumanMoveLikelihood(player_level_probability=0.45),
            "e2e4": HumanMoveLikelihood(player_level_probability=0.08),
        }
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="g2g4",
        player_color="white",
        player_level=PlayerLevel.rating(1000),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis), human).build(request)
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

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis)).build(request)

    assert result.evidence.position.side_to_move == "black"
    assert result.evidence.quality.label == "mistake"
    assert result.evidence.quality.score_delta_cp_player_pov == -260


def test_mate_scores_are_classified_without_centipawn_delta() -> None:
    analysis_with_mate = EngineAnalysis(
        engine_version="static-test-engine",
        analysis_budget=EngineAnalysisBudget(kind="static", value=1),
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
        PlayedMoveFacts(uci="a2a3", san="a3", legal=True, is_check=False, is_capture=False),
    )

    assert quality.label == "missed_win"
    assert quality.score_delta_cp_player_pov is None
    assert "forced mate" in quality.severity_text


def test_mate_transition_sets_significance_to_critical() -> None:
    analysis_with_mate = EngineAnalysis(
        engine_version="static-test-engine",
        analysis_budget=EngineAnalysisBudget(kind="static", value=1),
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

    significance = calculate_significance(
        analysis_with_mate,
        PlayedMoveFacts(uci="a2a3", san="a3", legal=True, is_check=False, is_capture=False),
    )

    assert significance.label == "critical"
    assert significance.score == 1.0


def test_wdl_loss_can_make_quality_worse_than_centipawns() -> None:
    engine_analysis = EngineAnalysis(
        engine_version="static-test-engine",
        analysis_budget=EngineAnalysisBudget(kind="static", value=1),
        top_lines=[
            EngineLine(
                move_uci="e2e4",
                move_san="e4",
                score=Score.cp(100),
                rank=1,
                wdl=Wdl(win=400, draw=500, loss=100),
                pv_uci=["e2e4"],
                pv_san=["e4"],
            )
        ],
        played_line=EngineLine(
            move_uci="d2d4",
            move_san="d4",
            score=Score.cp(90),
            rank=None,
            wdl=Wdl(win=100, draw=600, loss=300),
            pv_uci=["d2d4"],
            pv_san=["d4"],
        ),
    )

    quality = classify_quality(
        engine_analysis,
        PlayedMoveFacts(uci="d2d4", san="d4", legal=True, is_check=False, is_capture=False),
    )

    assert quality.score_loss_vs_best_cp == 10
    assert quality.wdl_expected_score_loss == 250
    assert quality.wdl_delta_player_pov == Wdl(win=-300, draw=100, loss=200)
    assert quality.label == "blunder"


def test_wdl_gap_can_make_significance_critical_without_centipawn_gap() -> None:
    engine_analysis = EngineAnalysis(
        engine_version="static-test-engine",
        analysis_budget=EngineAnalysisBudget(kind="static", value=1),
        top_lines=[
            EngineLine(
                move_uci="e2e4",
                move_san="e4",
                score=Score.cp(0),
                rank=1,
                wdl=Wdl(win=500, draw=300, loss=200),
                pv_uci=["e2e4"],
                pv_san=["e4"],
            )
        ],
        played_line=EngineLine(
            move_uci="a2a3",
            move_san="a3",
            score=Score.cp(0),
            rank=None,
            wdl=Wdl(win=300, draw=300, loss=400),
            pv_uci=["a2a3"],
            pv_san=["a3"],
        ),
    )

    significance = calculate_significance(
        engine_analysis,
        PlayedMoveFacts(uci="a2a3", san="a3", legal=True, is_check=False, is_capture=False),
    )

    assert significance.label == "critical"
    assert significance.score == 1.0


@pytest.mark.parametrize(
    ("probability", "expected"),
    [
        (0.30, "obvious"),
        (0.12, "findable"),
        (0.04, "hard"),
        (0.01, "very_hard"),
        (0.009, "engine_like"),
    ],
)
def test_findability_probability_thresholds(probability: float, expected: str) -> None:
    board = chess.Board()
    engine_analysis = analysis(
        board,
        played_uci="g2g4",
        top_scores=[("e2e4", 100)],
        played_score=-100,
    )
    human = StaticHumanLikelihoodProvider(
        {"e2e4": HumanMoveLikelihood(player_level_probability=probability)}
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="g2g4",
        player_color="white",
        player_level=PlayerLevel.rating(1000),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis), human).build(request)
    candidate = next(
        candidate for candidate in result.evidence.candidates if candidate.uci == "e2e4"
    )

    assert candidate.time_adjusted_findability == expected


def test_low_time_worsens_findability_without_changing_quality() -> None:
    board = chess.Board()
    engine_analysis = analysis(
        board,
        played_uci="g2g4",
        top_scores=[("e2e4", 100)],
        played_score=-100,
    )
    human = StaticHumanLikelihoodProvider(
        {"e2e4": HumanMoveLikelihood(player_level_probability=0.12)}
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="g2g4",
        player_color="white",
        player_level=PlayerLevel.rating(1000),
        clock_before_seconds=20,
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis), human).build(request)
    candidate = next(
        candidate for candidate in result.evidence.candidates if candidate.uci == "e2e4"
    )

    assert candidate.time_adjusted_findability == "hard"
    assert result.evidence.quality.label == "mistake"


def test_plus_400_probability_marks_teachable_skill_gap() -> None:
    board = chess.Board()
    engine_analysis = analysis(
        board,
        played_uci="g2g4",
        top_scores=[("e2e4", 100)],
        played_score=-100,
    )
    human = StaticHumanLikelihoodProvider(
        {
            "e2e4": HumanMoveLikelihood(
                player_level_probability=0.03,
                plus_400_probability=0.20,
            )
        }
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="g2g4",
        player_color="white",
        player_level=PlayerLevel.rating(1000),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis), human).build(request)
    candidate = next(
        candidate for candidate in result.evidence.candidates if candidate.uci == "e2e4"
    )

    assert candidate.teachable_skill_gap is True
    assert candidate.recommendation_policy == "explain_as_hidden_resource"
    assert result.llm_context.human_note is not None


def test_unknown_human_evidence_stays_unknown_findability() -> None:
    board = chess.Board()
    engine_analysis = analysis(
        board,
        played_uci="g2g4",
        top_scores=[("e2e4", 100)],
        played_score=-100,
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="g2g4",
        player_color="white",
        player_level=PlayerLevel.rating(1000),
    )

    result = MoveContextBuilder(StaticAnalysisProvider(engine_analysis)).build(request)
    candidate = next(
        candidate for candidate in result.evidence.candidates if candidate.uci == "e2e4"
    )

    assert candidate.time_adjusted_findability == "unknown"
    assert candidate.findability_source == "unknown"


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

    engine = MoveContextBuilder(StaticAnalysisProvider(engine_analysis))

    with pytest.raises(AnalysisError, match="does not match requested move"):
        engine.build(request)


def test_rejects_engine_line_with_illegal_pv_move() -> None:
    board = chess.Board()
    engine_analysis = EngineAnalysis(
        engine_version="static-test-engine",
        analysis_budget=EngineAnalysisBudget(kind="static", value=1),
        top_lines=[
            EngineLine(
                move_uci="e2e4",
                move_san="e4",
                score=Score.cp(10),
                rank=1,
                pv_uci=["e2e4", "e2e4"],
                pv_san=["e4", "e4"],
            )
        ],
        played_line=EngineLine(
            move_uci="g2g4",
            move_san="g4",
            score=Score.cp(-100),
            rank=None,
            pv_uci=["g2g4"],
            pv_san=["g4"],
        ),
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="g2g4",
        player_color="white",
        player_level=PlayerLevel.rating(1200),
    )

    engine = MoveContextBuilder(StaticAnalysisProvider(engine_analysis))

    with pytest.raises(AnalysisError, match="PV move e2e4 is illegal"):
        engine.build(request)
