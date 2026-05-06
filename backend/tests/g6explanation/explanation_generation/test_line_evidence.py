from __future__ import annotations

import chess

from g6explanation.context_engine import MoveContextBuilder
from g6explanation.context_engine.contracts import (
    ContextResult,
    EngineAnalysis,
    EngineAnalysisBudget,
    MoveContextRequest,
    PlayerLevel,
)
from g6explanation.explanation_generation.contracts import (
    MAX_LINE_CARD_PLIES,
    ExplanationLineEvidence,
)
from g6explanation.explanation_generation.line_evidence import build_line_evidence
from tests.g6explanation.context_engine.helpers import (
    StaticAnalysisProvider,
    engine_line,
    hung_rook_time_scramble_context,
    na4_tactical_objection_context,
)
from tests.g6explanation.explanation_generation.helpers import (
    mistake_context_with_practical_alternative,
)


def test_line_evidence_keeps_full_verified_played_line_horizon() -> None:
    context = _long_played_line_context()

    played_line = _line_by_id(context, "played-line")

    assert played_line.moves == [
        "g4",
        "e5",
        "f3",
        "d5",
        "e3",
        "Nf6",
        "Bg2",
        "Bd6",
        "Ne2",
        "O-O",
        "O-O",
        "c6",
        "Nbc3",
        "Re8",
        "d3",
        "Nbd7",
    ]
    assert len(played_line.moves) == MAX_LINE_CARD_PLIES


def test_line_evidence_uses_full_top_line_for_better_line() -> None:
    context = _long_better_line_context()

    better_line = _line_by_id(context, "better-line")

    assert better_line.moves == [
        "e4",
        "e5",
        "Nf3",
        "Nc6",
        "Bb5",
        "a6",
        "Ba4",
        "Nf6",
        "O-O",
        "Be7",
        "Re1",
        "b5",
        "Bb3",
        "d6",
        "c3",
        "O-O",
    ]
    assert len(better_line.moves) == MAX_LINE_CARD_PLIES
    assert better_line.title == "How the alternative works"
    assert "better idea" not in better_line.why


def test_line_evidence_why_is_plain_language_not_line_notation() -> None:
    context = mistake_context_with_practical_alternative()

    played_line = _line_by_id(context, "played-line")

    assert context.llm_context.main_point not in played_line.why
    assert all(move not in played_line.why for move in played_line.moves)
    assert played_line.title == "How the mistake gets punished"


def test_line_evidence_adds_objection_line_for_apparently_capturable_tactic() -> None:
    context = na4_tactical_objection_context()

    objection_line = _line_by_id(context, "objection-line")

    assert objection_line.role == "objection_line"
    assert objection_line.moves == ["Na4", "Nxa4", "Nxe4"]
    assert objection_line.title == "Why the capture fails"
    assert all(move not in objection_line.why for move in objection_line.moves)
    assert "not simply free" in objection_line.why


def test_line_evidence_skips_played_line_when_bad_move_simply_hangs_piece() -> None:
    context = hung_rook_time_scramble_context()

    line_ids = {line.id for line in build_line_evidence(context)}

    assert "played-line" not in line_ids


def _line_by_id(context: ContextResult, line_id: str) -> ExplanationLineEvidence:
    return next(line for line in build_line_evidence(context) if line.id == line_id)


def _long_played_line_context() -> ContextResult:
    board = chess.Board()
    played_pv_uci = [
        "g2g4",
        "e7e5",
        "f2f3",
        "d7d5",
        "e2e3",
        "g8f6",
        "f1g2",
        "f8d6",
        "g1e2",
        "e8g8",
        "e1g1",
        "c7c6",
        "b1c3",
        "f8e8",
        "d2d3",
        "b8d7",
    ]
    analysis = EngineAnalysis(
        engine_version="static-test-engine",
        analysis_budget=EngineAnalysisBudget(kind="static", value=1, multipv=1),
        top_lines=[engine_line(board, "e2e4", 40, rank=1)],
        played_line=engine_line(board, "g2g4", -180, rank=None, pv_uci=played_pv_uci),
        after_line=engine_line(_board_after(board, "g2g4"), "e7e5", -180, rank=1),
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="g2g4",
        player_color="white",
        player_level=PlayerLevel.rating(1250, "lichess"),
    )
    return MoveContextBuilder(StaticAnalysisProvider(analysis)).build(request)


def _long_better_line_context() -> ContextResult:
    board = chess.Board()
    best_pv_uci = [
        "e2e4",
        "e7e5",
        "g1f3",
        "b8c6",
        "f1b5",
        "a7a6",
        "b5a4",
        "g8f6",
        "e1g1",
        "f8e7",
        "f1e1",
        "b7b5",
        "a4b3",
        "d7d6",
        "c2c3",
        "e8g8",
    ]
    analysis = EngineAnalysis(
        engine_version="static-test-engine",
        analysis_budget=EngineAnalysisBudget(kind="static", value=1, multipv=1),
        top_lines=[engine_line(board, "e2e4", 40, rank=1, pv_uci=best_pv_uci)],
        played_line=engine_line(board, "g2g4", -180, rank=None),
        after_line=engine_line(_board_after(board, "g2g4"), "e7e5", -180, rank=1),
    )
    request = MoveContextRequest(
        fen_before=board.fen(),
        played_move="g2g4",
        player_color="white",
        player_level=PlayerLevel.rating(1250, "lichess"),
    )
    return MoveContextBuilder(StaticAnalysisProvider(analysis)).build(request)


def _board_after(board: chess.Board, uci: str) -> chess.Board:
    after = board.copy(stack=False)
    after.push(chess.Move.from_uci(uci))
    return after
