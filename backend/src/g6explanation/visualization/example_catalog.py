"""Test-derived examples for the context visualization API."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import chess

from g6explanation.context_engine import MoveContextBuilder
from g6explanation.context_engine.contracts import (
    ColorName,
    ContextResult,
    EngineAnalysis,
    EngineAnalysisBudget,
    EngineLine,
    HumanMoveLikelihood,
    MoveContextRequest,
    PlayerLevel,
    Score,
    Wdl,
)
from g6explanation.visualization.contracts import (
    VisualizationExample,
    VisualizationMove,
    VisualizationMoveContext,
)


def visualization_examples() -> list[VisualizationExample]:
    """Return the frozen set of examples used by the visualization frontend."""

    return list(_examples())


def find_visualization_example(example_id: str) -> VisualizationExample | None:
    """Find one visualization example by ID."""

    return next((example for example in _examples() if example.id == example_id), None)


@lru_cache(maxsize=1)
def _examples() -> tuple[VisualizationExample, ...]:
    return (
        _practical_alternative_example(),
        _hard_resource_example(),
        _quiet_queen_sacrifice_example(),
    )


def _practical_alternative_example() -> VisualizationExample:
    board = chess.Board()
    engine_analysis = _analysis(
        board,
        played_uci="g2g4",
        top_scores=[("e2e4", 40), ("g1f3", 25)],
        played_score=-180,
        after_reply_uci="e7e5",
    )
    human = _StaticHumanLikelihoodProvider(
        {
            "e2e4": HumanMoveLikelihood(player_level_probability=0.02, plus_400_probability=0.12),
            "g1f3": HumanMoveLikelihood(player_level_probability=0.32, plus_400_probability=0.40),
            "g2g4": HumanMoveLikelihood(player_level_probability=0.25, plus_400_probability=0.08),
        }
    )
    first_context = MoveContextBuilder(_StaticAnalysisProvider(engine_analysis), human).build(
        MoveContextRequest(
            fen_before=board.fen(),
            played_move="g2g4",
            player_color="white",
            player_level=PlayerLevel.rating(1250, "lichess"),
            time_control="blitz",
            clock_before_seconds=80,
        )
    )
    reply_board = board.copy(stack=False)
    reply_board.push(chess.Move.from_uci("g2g4"))
    contexts = {
        1: first_context,
        2: _routine_context(reply_board, "e7e5", "black", PlayerLevel.rating(1250, "lichess")),
    }
    return _build_example(
        example_id="practical-alternative-g4",
        title="Practical alternative after 1.g4",
        summary=(
            "The test case where the engine best move is not the most teachable recommendation."
        ),
        source_test="test_uses_practical_alternative_when_engine_best_is_hard_and_close",
        initial_fen=board.fen(),
        line_uci=["g2g4", "e7e5"],
        orientation="white",
        player_level="1250 lichess",
        tags=["mistake", "findability", "practical alternative"],
        contexts=contexts,
    )


def _hard_resource_example() -> VisualizationExample:
    board = chess.Board()
    engine_analysis = _analysis(
        board,
        played_uci="a2a3",
        top_scores=[("e2e4", 300), ("d2d4", 210)],
        played_score=-60,
        after_reply_uci="e7e5",
    )
    human = _StaticHumanLikelihoodProvider(
        {
            "e2e4": HumanMoveLikelihood(player_level_probability=0.015, plus_400_probability=0.10),
            "a2a3": HumanMoveLikelihood(player_level_probability=0.20, plus_400_probability=0.02),
        }
    )
    first_context = MoveContextBuilder(_StaticAnalysisProvider(engine_analysis), human).build(
        MoveContextRequest(
            fen_before=board.fen(),
            played_move="a2a3",
            player_color="white",
            player_level=PlayerLevel.rating(900, "lichess"),
            time_control="blitz",
            clock_before_seconds=20,
        )
    )
    reply_board = board.copy(stack=False)
    reply_board.push(chess.Move.from_uci("a2a3"))
    contexts = {
        1: first_context,
        2: _routine_context(reply_board, "e7e5", "black", PlayerLevel.rating(900, "lichess")),
    }
    return _build_example(
        example_id="hard-resource-a3",
        title="Hard resource after 1.a3",
        summary="The test case that caveats a strong engine move instead of calling it obvious.",
        source_test="test_caveats_hard_engine_best_instead_of_presenting_it_as_obvious",
        initial_fen=board.fen(),
        line_uci=["a2a3", "e7e5"],
        orientation="white",
        player_level="900 lichess",
        tags=["blunder", "hidden resource", "low time"],
        contexts=contexts,
    )


def _quiet_queen_sacrifice_example() -> VisualizationExample:
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
    human = _StaticHumanLikelihoodProvider(
        {"g4e6": HumanMoveLikelihood(player_level_probability=0.02)}
    )
    first_context = MoveContextBuilder(_StaticAnalysisProvider(engine_analysis), human).build(
        MoveContextRequest(
            fen_before=board.fen(),
            played_move="g4e6",
            player_color="black",
            player_level=PlayerLevel.rating(2400),
            time_control="classical",
        )
    )

    contexts: dict[int, ContextResult] = {1: first_context}
    replay = board.copy(stack=False)
    for ply, move_uci in enumerate(played_pv, start=1):
        if ply > 1:
            contexts[ply] = _routine_context(
                replay,
                move_uci,
                _color_name(replay.turn),
                PlayerLevel.rating(2400),
            )
        replay.push(chess.Move.from_uci(move_uci))

    return _build_example(
        example_id="quiet-queen-sacrifice",
        title="Quiet queen sacrifice resource",
        summary="The beauty test case where a sound, hard-to-find resource becomes brilliant.",
        source_test="test_quiet_queen_sacrifice_resource_can_be_brilliant",
        initial_fen=board.fen(),
        line_uci=played_pv,
        orientation="black",
        player_level="2400",
        tags=["best", "brilliant", "sacrifice"],
        contexts=contexts,
    )


def _build_example(
    *,
    example_id: str,
    title: str,
    summary: str,
    source_test: str,
    initial_fen: str,
    line_uci: list[str],
    orientation: ColorName,
    player_level: str,
    tags: list[str],
    contexts: dict[int, ContextResult],
) -> VisualizationExample:
    board = chess.Board(initial_fen)
    moves: list[VisualizationMove] = []
    for ply, move_uci in enumerate(line_uci, start=1):
        move = chess.Move.from_uci(move_uci)
        if move not in board.legal_moves:
            raise ValueError(f"Visualization line move {move_uci} is illegal at ply {ply}.")
        fen_before = board.fen()
        san = board.san(move)
        player_color = _color_name(board.turn)
        board.push(move)
        moves.append(
            VisualizationMove(
                ply=ply,
                uci=move_uci,
                san=san,
                fen_before=fen_before,
                fen_after=board.fen(),
                player_color=player_color,
                has_context=ply in contexts,
            )
        )

    return VisualizationExample(
        id=example_id,
        title=title,
        summary=summary,
        source_test=source_test,
        initial_fen=initial_fen,
        orientation=orientation,
        player_level=player_level,
        tags=tags,
        moves=moves,
        contexts=[
            VisualizationMoveContext(ply=ply, result=result)
            for ply, result in sorted(contexts.items())
        ],
    )


def _routine_context(
    board: chess.Board,
    played_uci: str,
    player_color: ColorName,
    player_level: PlayerLevel,
) -> ContextResult:
    top_scores = [(played_uci, 60)]
    alternative = _first_legal_uci_except(board, played_uci)
    if alternative is not None:
        top_scores.append((alternative, 30))
    after_reply = _first_legal_after(board, played_uci)
    engine_analysis = _analysis(
        board,
        played_uci=played_uci,
        top_scores=top_scores,
        played_score=60,
        after_reply_uci=after_reply,
    )
    return MoveContextBuilder(_StaticAnalysisProvider(engine_analysis)).build(
        MoveContextRequest(
            fen_before=board.fen(),
            played_move=played_uci,
            player_color=player_color,
            player_level=player_level,
        )
    )


def _analysis(
    board: chess.Board,
    played_uci: str,
    top_scores: list[tuple[str, int]],
    played_score: int,
    after_reply_uci: str | None = None,
    played_pv_uci: list[str] | None = None,
) -> EngineAnalysis:
    played_move = chess.Move.from_uci(played_uci)
    after_board = board.copy(stack=False)
    after_board.push(played_move)
    return EngineAnalysis(
        engine_version="static-test-engine",
        analysis_budget=EngineAnalysisBudget(kind="static", value=1, multipv=len(top_scores)),
        top_lines=[
            _line(board, move_uci, Score.cp(score), rank=index + 1)
            for index, (move_uci, score) in enumerate(top_scores)
        ],
        played_line=_line(
            board,
            played_uci,
            Score.cp(played_score),
            rank=None,
            pv_uci=played_pv_uci,
        ),
        after_line=_line(after_board, after_reply_uci, Score.cp(played_score), rank=1)
        if after_reply_uci
        else None,
    )


def _line(
    board: chess.Board,
    uci: str,
    score: Score,
    rank: int | None,
    pv_uci: list[str] | None = None,
) -> EngineLine:
    move = chess.Move.from_uci(uci)
    if move not in board.legal_moves:
        raise ValueError(f"Engine line move {uci} is illegal in {board.fen()}.")
    full_pv_uci = pv_uci or [uci]
    return EngineLine(
        move_uci=uci,
        move_san=board.san(move),
        score=score,
        rank=rank,
        wdl=Wdl(win=500, draw=400, loss=100),
        pv_uci=full_pv_uci,
        pv_san=_pv_san(board, full_pv_uci),
    )


def _pv_san(board: chess.Board, pv_uci: list[str]) -> list[str]:
    replay = board.copy(stack=False)
    san_moves: list[str] = []
    for uci in pv_uci:
        move = chess.Move.from_uci(uci)
        if move not in replay.legal_moves:
            raise ValueError(f"PV move {uci} is illegal in {replay.fen()}.")
        san_moves.append(replay.san(move))
        replay.push(move)
    return san_moves


def _first_legal_uci_except(board: chess.Board, skipped_uci: str) -> str | None:
    return next((move.uci() for move in board.legal_moves if move.uci() != skipped_uci), None)


def _first_legal_after(board: chess.Board, played_uci: str) -> str | None:
    after_board = board.copy(stack=False)
    after_board.push(chess.Move.from_uci(played_uci))
    return next((move.uci() for move in after_board.legal_moves), None)


def _color_name(color: chess.Color) -> ColorName:
    return "white" if color == chess.WHITE else "black"


@dataclass(frozen=True)
class _StaticAnalysisProvider:
    engine_analysis: EngineAnalysis

    def analyze(
        self, board: chess.Board, played_move: chess.Move, player_color: ColorName
    ) -> EngineAnalysis:
        return self.engine_analysis


@dataclass(frozen=True)
class _StaticHumanLikelihoodProvider:
    stats: dict[str, HumanMoveLikelihood]

    def likelihoods(
        self,
        board: chess.Board,
        candidate_moves: list[chess.Move],
        request: MoveContextRequest,
    ) -> dict[str, HumanMoveLikelihood]:
        return {
            move.uci(): self.stats[move.uci()]
            for move in candidate_moves
            if move.uci() in self.stats
        }
